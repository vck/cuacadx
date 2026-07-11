#!/usr/bin/env python3
import json
import os
import re
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pandas as pd

HOST = "0.0.0.0"
PORT = 8765
ERA5_DIR = Path("data/era5")

TRANSFORMS = {
    "t2m": lambda v: round(v - 273.15, 2),
    "d2m": lambda v: round(v - 273.15, 2),
    "u10": lambda v: round(v, 2),
    "v10": lambda v: round(v, 2),
    "sp": lambda v: round(v / 100, 2),
    "msl": lambda v: round(v / 100, 2),
    "tp": lambda v: round(v, 5),
}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>CUACADX — Kaltim Weather</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:system-ui,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0}
  #map{width:100vw;height:100vh}
  .panel{position:fixed;top:16px;left:16px;z-index:1000;background:rgba(15,23,42,.92);border:1px solid #334155;border-radius:12px;padding:20px;min-width:240px;backdrop-filter:blur(8px)}
  .panel h1{font-size:16px;font-weight:600;margin-bottom:2px}
  .panel .sub{font-size:11px;color:#94a3b8;margin-bottom:12px}
  .panel label{font-size:11px;font-weight:500;color:#94a3b8;display:block;margin-bottom:2px}
  .panel select{width:100%;padding:7px 10px;border-radius:6px;border:1px solid #334155;background:#1e293b;color:#e2e8f0;font-size:13px;cursor:pointer;margin-bottom:8px}
  .panel select:focus{outline:none;border-color:#3b82f6}
  .info{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);z-index:1000;background:rgba(15,23,42,.88);border:1px solid #334155;border-radius:8px;padding:8px 16px;font-size:12px;color:#94a3b8;backdrop-filter:blur(8px);text-align:center;white-space:nowrap}
  .legend{position:fixed;bottom:80px;right:16px;z-index:1000;background:rgba(15,23,42,.88);border:1px solid #334155;border-radius:8px;padding:12px;font-size:11px;backdrop-filter:blur(8px);min-width:150px}
  .legend-item{display:flex;align-items:center;gap:6px;margin:2px 0}
  .legend-swatch{width:14px;height:14px;border-radius:3px;flex-shrink:0}
  .legend-label{color:#cbd5e1}
  .badge{display:inline-block;font-size:10px;padding:2px 6px;border-radius:4px;font-weight:500;margin-left:6px}
  .badge-era5{background:#1e3a5f;color:#60a5fa}
  .badge-gfs{background:#3b1f3b;color:#c084fc}
</style>
</head>
<body>
<div id="map"></div>

<div class="panel">
  <h1>CUACADX</h1>
  <div class="sub">Regional Weather · Kalimantan Timur</div>

  <label>Source</label>
  <select id="srcSelect">
    <option value="era5">ERA5 Reanalysis <span class="badge badge-era5">Jan 2024</span></option>
    <option value="gfs_today">GFS Forecast <span class="badge badge-gfs">Today +7d</span></option>
  </select>

  <label>Variable</label>
  <select id="varSelect">
    <option value="t2m">Temperature (2m) °C</option>
    <option value="d2m">Dewpoint (2m) °C</option>
    <option value="u10">U Wind (10m) m/s</option>
    <option value="v10">V Wind (10m) m/s</option>
    <option value="sp">Surface Pressure hPa</option>
    <option value="msl">MSL Pressure hPa</option>
    <option value="tp">Precipitation m</option>
  </select>

  <label>Timestamp <span id="tsCount"></span></label>
  <select id="timeSelect"></select>
</div>

<div class="legend" id="legend"></div>
<div class="info" id="info">Loading...</div>

<script>
const map = L.map('map').setView([0.5, 117.0], 7);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:10,minZoom:5}).addTo(map);

let cache = {};
let markers = L.layerGroup().addTo(map);

function getColor(val, varKey) {
  if (varKey === 't2m') return val < 22 ? '#0000ff' : val < 24 ? '#0088ff' : val < 26 ? '#00ccff' : val < 28 ? '#00ff88' : val < 30 ? '#88ff00' : val < 32 ? '#ffcc00' : '#ff3300';
  if (varKey === 'd2m') return val < 20 ? '#1a3a5c' : val < 22 ? '#2d5a8a' : val < 24 ? '#4a8bc2' : val < 26 ? '#7ab8e0' : '#b0d8f0';
  if (varKey === 'sp' || varKey === 'msl') return val < 1005 ? '#800026' : val < 1008 ? '#bd0026' : val < 1010 ? '#e31a1c' : val < 1012 ? '#fc4e2a' : val < 1014 ? '#fd8d3c' : val < 1016 ? '#feb24c' : '#ffffcc';
  if (varKey === 'tp') return val < 0.001 ? '#ffffff' : val < 0.002 ? '#c6dbef' : val < 0.005 ? '#6baed6' : val < 0.01 ? '#3182bd' : val < 0.02 ? '#08519c' : '#002952';
  const abs = Math.abs(val);
  return abs < 1 ? '#c8e6c9' : abs < 3 ? '#81c784' : abs < 5 ? '#4caf50' : abs < 8 ? '#388e3c' : '#1b5e20';
}

function buildLegend(varKey) {
  const el = document.getElementById('legend');
  const m = {t2m:'Temp (°C)',d2m:'Dewpt (°C)',u10:'Wind (m/s)',v10:'Wind (m/s)',sp:'Pres (hPa)',msl:'MSLP (hPa)',tp:'Precip (m)'};
  if (varKey === 't2m') el.innerHTML = '<b>'+m[varKey]+'</b><div class="legend-item"><span class="legend-swatch" style="background:#0000ff"></span><span class="legend-label">&lt;22</span></div><div class="legend-item"><span class="legend-swatch" style="background:#0088ff"></span><span class="legend-label">22-24</span></div><div class="legend-item"><span class="legend-swatch" style="background:#00ccff"></span><span class="legend-label">24-26</span></div><div class="legend-item"><span class="legend-swatch" style="background:#00ff88"></span><span class="legend-label">26-28</span></div><div class="legend-item"><span class="legend-swatch" style="background:#88ff00"></span><span class="legend-label">28-30</span></div><div class="legend-item"><span class="legend-swatch" style="background:#ffcc00"></span><span class="legend-label">30-32</span></div><div class="legend-item"><span class="legend-swatch" style="background:#ff3300"></span><span class="legend-label">&gt;32</span></div>';
  else if (varKey === 'sp' || varKey === 'msl') el.innerHTML = '<b>'+m[varKey]+'</b><div class="legend-item"><span class="legend-swatch" style="background:#800026"></span><span class="legend-label">&lt;1005</span></div><div class="legend-item"><span class="legend-swatch" style="background:#bd0026"></span><span class="legend-label">1005-1008</span></div><div class="legend-item"><span class="legend-swatch" style="background:#e31a1c"></span><span class="legend-label">1008-1010</span></div><div class="legend-item"><span class="legend-swatch" style="background:#fc4e2a"></span><span class="legend-label">1010-1012</span></div><div class="legend-item"><span class="legend-swatch" style="background:#fd8d3c"></span><span class="legend-label">1012-1014</span></div><div class="legend-item"><span class="legend-swatch" style="background:#feb24c"></span><span class="legend-label">1014-1016</span></div><div class="legend-item"><span class="legend-swatch" style="background:#ffffcc"></span><span class="legend-label">&gt;1016</span></div>';
  else if (varKey === 'tp') el.innerHTML = '<b>'+m[varKey]+'</b><div class="legend-item"><span class="legend-swatch" style="background:#ffffff"></span><span class="legend-label">&lt;0.001</span></div><div class="legend-item"><span class="legend-swatch" style="background:#c6dbef"></span><span class="legend-label">0.001-0.002</span></div><div class="legend-item"><span class="legend-swatch" style="background:#6baed6"></span><span class="legend-label">0.002-0.005</span></div><div class="legend-item"><span class="legend-swatch" style="background:#3182bd"></span><span class="legend-label">0.005-0.01</span></div><div class="legend-item"><span class="legend-swatch" style="background:#08519c"></span><span class="legend-label">0.01-0.02</span></div><div class="legend-item"><span class="legend-swatch" style="background:#002952"></span><span class="legend-label">&gt;0.02</span></div>';
  else el.innerHTML = '<b>'+m[varKey]+'</b><div class="legend-item"><span class="legend-swatch" style="background:#c8e6c9"></span><span class="legend-label">0-1</span></div><div class="legend-item"><span class="legend-swatch" style="background:#81c784"></span><span class="legend-label">1-3</span></div><div class="legend-item"><span class="legend-swatch" style="background:#4caf50"></span><span class="legend-label">3-5</span></div><div class="legend-item"><span class="legend-swatch" style="background:#388e3c"></span><span class="legend-label">5-8</span></div><div class="legend-item"><span class="legend-swatch" style="background:#1b5e20"></span><span class="legend-label">&gt;8</span></div>';
}

function renderMap(src, varKey, tsIdx) {
  const d = cache[src]?.[varKey];
  if (!d) { document.getElementById('info').textContent = 'No data for ' + src + '/' + varKey; return; }
  const ts = d.timestamps[tsIdx];
  const points = d.frames[tsIdx];
  if (!points) return;
  const label = src === 'era5' ? 'ERA5' : 'GFS';
  document.getElementById('info').textContent = label + ' · ' + varKey + ' · ' + ts + ' · ' + points.length + ' pts';
  markers.clearLayers();
  points.forEach(p => {
    L.circleMarker([p.lat, p.lon], {
      radius: 6, color: '#1e293b', fillColor: getColor(p.v, varKey), fillOpacity: 0.85, weight: 0.5
    }).addTo(markers).bindPopup('<b>'+p.v.toFixed(1)+'</b>');
  });
  buildLegend(varKey);
}

async function loadSource(src) {
  if (cache[src]) return;
  cache[src] = {};
  for (const v of ['t2m','d2m','u10','v10','sp','msl','tp']) {
    const resp = await fetch('/data/' + src + '/' + v);
    if (!resp.ok) continue;
    cache[src][v] = await resp.json();
  }
}

async function switchSource() {
  const src = document.getElementById('srcSelect').value;
  document.getElementById('info').textContent = 'Loading ' + src + '...';
  await loadSource(src);
  const sel = document.getElementById('timeSelect');
  sel.innerHTML = '';
  const varKey = document.getElementById('varSelect').value;
  const d = cache[src]?.[varKey];
  if (!d || !d.timestamps) { document.getElementById('info').textContent = 'No data'; return; }
  d.timestamps.forEach((t,i) => {
    const opt = document.createElement('option');
    opt.value = i; opt.textContent = t;
    sel.appendChild(opt);
  });
  document.getElementById('tsCount').textContent = '(' + d.timestamps.length + ')';
  renderMap(src, varKey, 0);
}

document.getElementById('srcSelect').addEventListener('change', switchSource);
document.getElementById('varSelect').addEventListener('change', () => {
  renderMap(document.getElementById('srcSelect').value, document.getElementById('varSelect').value, 0);
});
document.getElementById('timeSelect').addEventListener('change', e => {
  renderMap(document.getElementById('srcSelect').value, document.getElementById('varSelect').value, parseInt(e.target.value));
});

switchSource();
</script>
</body>
</html>"""


def load_era5(parquet_path: str, var_label: str, transform_fn=None):
    df = pd.read_parquet(parquet_path)
    val_col = var_label
    if transform_fn:
        df["v"] = df[val_col].apply(transform_fn)
    else:
        df["v"] = df[val_col]
    timestamps = sorted(df["valid_time"].unique())
    frames = []
    for ts in timestamps:
        slice_df = df[df["valid_time"] == ts][["lat", "lon", "v"]]
        frames.append(slice_df.to_dict(orient="records"))
    return {"timestamps": [str(t) for t in timestamps], "frames": frames}


def find_latest_gfs_dir() -> Path | None:
    gfs_root = Path("data/gfs")
    if not gfs_root.exists():
        return None
    for date_dir in sorted(gfs_root.iterdir(), reverse=True):
        if date_dir.is_dir():
            for cycle_dir in sorted(date_dir.iterdir(), reverse=True):
                if cycle_dir.is_dir() and list(cycle_dir.glob("*.parquet")):
                    return cycle_dir
    return None


def load_gfs(gfs_dir: Path) -> dict:
    by_var = {}
    for pf in sorted(gfs_dir.glob("*.parquet")):
        m = re.match(r"(\w+)_(\d+)\.parquet", pf.name)
        if not m:
            continue
        var, fh = m.group(1), int(m.group(2))
        try:
            df = pd.read_parquet(pf)
        except Exception:
            continue
        if df.empty:
            continue
        transform = TRANSFORMS.get(var, lambda v: v)
        df["v"] = df["value"].apply(transform)
        ts = df["valid_time"].iloc[0]
        ts_str = f"+{fh:03d}h {ts}"
        points = df[["lat", "lon", "v"]].to_dict(orient="records")
        if var not in by_var:
            by_var[var] = {"timestamps": [], "frames": []}
        by_var[var]["timestamps"].append(ts_str)
        by_var[var]["frames"].append(points)
    return by_var


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        path = self.path

        m = re.match(r"^/data/era5/(\w+)$", path)
        if m:
            var = m.group(1)
            p = ERA5_DIR / "2024" / "01" / f"{var}.parquet"
            if p.exists():
                return self._json(load_era5(str(p), var, TRANSFORMS.get(var)))

        m = re.match(r"^/data/gfs_today/(\w+)$", path)
        if m:
            var = m.group(1)
            gfs_dir = find_latest_gfs_dir()
            if gfs_dir:
                cache_key = f"gfs_{gfs_dir.name}"
                if not hasattr(self.server, "_gfs_cache"):
                    self.server._gfs_cache = {}
                if cache_key not in self.server._gfs_cache:
                    self.server._gfs_cache[cache_key] = load_gfs(gfs_dir)
                data = self.server._gfs_cache[cache_key].get(var)
                if data:
                    return self._json(data)

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
            return

        self.send_response(404)
        self.end_headers()

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


if __name__ == "__main__":
    print(f"CUACADX viz — http://localhost:{PORT}")
    print(f"  ERA5: {ERA5_DIR / '2024' / '01'}")
    gfs_dir = find_latest_gfs_dir()
    if gfs_dir:
        print(f"  GFS:  {gfs_dir}")
    HTTPServer((HOST, PORT), Handler).serve_forever()
