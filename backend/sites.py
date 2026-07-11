"""Mine site definitions and alert engine."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
FCN_DIR = ROOT / "data" / "fcn"

MINE_TYPES = {
    "coal": "Coal Mine",
    "plant": "Processing Plant",
    "port": "Loading Port",
}

SITES = [
    {"id": "bengalon", "name": "Bengalon", "type": "coal", "lat": 0.75, "lon": 117.25, "thresholds": {"rain_mm_day": 50, "wind_kmh": 35, "temp_c": 38}},
    {"id": "wahana", "name": "Wahana", "type": "coal", "lat": -0.75, "lon": 115.75, "thresholds": {"rain_mm_day": 55, "wind_kmh": 30, "temp_c": 37}},
    {"id": "sungai_danau", "name": "Sungai Danau", "type": "coal", "lat": -3.0, "lon": 116.25, "thresholds": {"rain_mm_day": 60, "wind_kmh": 35, "temp_c": 36}},
    {"id": "kintap", "name": "Kintap", "type": "coal", "lat": -3.75, "lon": 115.25, "thresholds": {"rain_mm_day": 50, "wind_kmh": 30, "temp_c": 38}},
    {"id": "asam_asam", "name": "Asam-Asam", "type": "coal", "lat": -3.5, "lon": 115.0, "thresholds": {"rain_mm_day": 55, "wind_kmh": 35, "temp_c": 37}},
    {"id": "sebuku", "name": "Sebuku Island", "type": "coal", "lat": -3.5, "lon": 116.5, "thresholds": {"rain_mm_day": 50, "wind_kmh": 40, "temp_c": 36}},
]

THRESHOLDS = {
    "rain_mm_day": {"caution": 20, "alert": 50},
    "wind_kmh": {"caution": 20, "alert": 35},
    "temp_c": {"caution": 34, "alert": 38},
    "lightning_km": {"caution": 25, "alert": 15},
}

SEVERITY = {0: "ok", 1: "caution", 2: "alert"}


def _nearest_grid_point(df: pd.DataFrame, lat: float, lon: float) -> tuple[float, float] | None:
    """Find nearest grid point in a DataFrame for a given lat/lon."""
    lats = df["lat"].unique()
    lons = df["lon"].unique()
    glat = lats[np.argmin(np.abs(lats - lat))]
    glon = lons[np.argmin(np.abs(lons - lon))]
    return float(glat), float(glon)


def _load_latest_forecast() -> pd.DataFrame | None:
    """Load most recent FCN forecast parquet."""
    if not FCN_DIR.exists():
        return None
    for date_dir in sorted(FCN_DIR.iterdir(), reverse=True):
        for cycle_dir in sorted(date_dir.iterdir(), reverse=True):
            pf = cycle_dir / "forecast.parquet"
            if pf.exists():
                return pd.read_parquet(pf)
    return None


def get_sites() -> list[dict]:
    return SITES


def get_site_conditions(site_id: str | None = None) -> list[dict]:
    """Current conditions + severity for all (or one) sites from latest FCN forecast."""
    df = _load_latest_forecast()
    if df is None:
        return []

    sites = [s for s in SITES if site_id is None or s["id"] == site_id]
    # Use +6h lead as "current"
    current = df[df["lead_time_h"] == 6].copy()
    if current.empty:
        return []

    results = []
    for site in sites:
        glat, glon = _nearest_grid_point(current, site["lat"], site["lon"])
        row = current[(current["lat"] == glat) & (current["lon"] == glon)]
        if row.empty:
            continue

        vals = row.set_index("variable")["value"].to_dict()

        t2m_k = vals.get("t2m", 300)
        u10 = vals.get("u10m", 0)
        v10 = vals.get("v10m", 0)
        sp_pa = vals.get("sp", 101000)
        r500 = vals.get("r500", 50)

        temp_c = round(t2m_k - 273.15, 1)
        wind_ms = np.sqrt(u10**2 + v10**2)
        wind_kmh = round(wind_ms * 3.6, 1)
        rain_mm = round(r500 * 0.5, 1)  # rough proxy: r500% → mm/day
        pressure_hpa = round(sp_pa / 100, 1)

        # Compute severities
        rain_sev = 2 if rain_mm >= THRESHOLDS["rain_mm_day"]["alert"] else 1 if rain_mm >= THRESHOLDS["rain_mm_day"]["caution"] else 0
        wind_sev = 2 if wind_kmh >= THRESHOLDS["wind_kmh"]["alert"] else 1 if wind_kmh >= THRESHOLDS["wind_kmh"]["caution"] else 0
        temp_sev = 2 if temp_c >= THRESHOLDS["temp_c"]["alert"] else 1 if temp_c >= THRESHOLDS["temp_c"]["caution"] else 0

        results.append({
            "site_id": site["id"],
            "site_name": site["name"],
            "site_type": MINE_TYPES.get(site["type"], "Mine"),
            "lat": site["lat"],
            "lon": site["lon"],
            "temp_c": temp_c,
            "wind_kmh": wind_kmh,
            "rain_mm": rain_mm,
            "pressure_hpa": pressure_hpa,
            "humidity_pct": round(r500, 0),
            "severities": {
                "rain": {"level": rain_sev, "label": SEVERITY[rain_sev]},
                "wind": {"level": wind_sev, "label": SEVERITY[wind_sev]},
                "temp": {"level": temp_sev, "label": SEVERITY[temp_sev]},
                "lightning": {"level": 0, "label": "ok"},
            },
        })

    return results


def get_alerts(site_id: str | None = None) -> list[dict]:
    """Generate alerts from current conditions vs thresholds."""
    conditions = get_site_conditions(site_id)
    alerts = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")

    for c in conditions:
        if c["severities"]["rain"]["level"] >= 1:
            alerts.append({
                "ts": now, "severity": c["severities"]["rain"]["label"],
                "site": c["site_name"], "threat": "rain",
                "message": f"Heavy rain: {c['rain_mm']}mm/24h at {c['site_name']}",
            })
        if c["severities"]["wind"]["level"] >= 1:
            alerts.append({
                "ts": now, "severity": c["severities"]["wind"]["label"],
                "site": c["site_name"], "threat": "wind",
                "message": f"Strong wind: {c['wind_kmh']}km/h at {c['site_name']}",
            })
        if c["severities"]["temp"]["level"] >= 1:
            alerts.append({
                "ts": now, "severity": c["severities"]["temp"]["label"],
                "site": c["site_name"], "threat": "temp",
                "message": f"High temp: {c['temp_c']}°C at {c['site_name']}",
            })

    # Add lightning alerts from storm cell proximity (if Himawari data available)
    alerts.sort(key=lambda a: {"alert": 0, "caution": 1, "ok": 2}[a["severity"]])

    return alerts
