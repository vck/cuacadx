import logging
import ssl
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import certifi
import numpy as np
import pandas as pd
import torch
import xarray as xr

from earth2studio.models.auto.package import Package
from earth2studio.models.px.fcn import FCN, VARIABLES

from ..config import KALIMANTAN_BBOX, PROJECT_ROOT

logger = logging.getLogger(__name__)

MODEL_DIR = PROJECT_ROOT / "models" / "fourcastnet"
DATA_DIR = PROJECT_ROOT / "data" / "fcn"

GFS_BASE = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"

# GFS parameter mapping (param_name, level_desc, level_key_for_url)
SURFACE_VARS = {
    "u10m": ("UGRD", "10 m above ground", "10_m_above_ground"),
    "v10m": ("VGRD", "10 m above ground", "10_m_above_ground"),
    "t2m": ("TMP", "2 m above ground", "2_m_above_ground"),
    "sp": ("PRES", "surface", "surface"),
    "msl": ("PRMSL", "mean sea level", "mean_sea_level"),
    "u100m": ("UGRD", "100 m above ground", "100_m_above_ground"),
    "v100m": ("VGRD", "100 m above ground", "100_m_above_ground"),
}

PRESSURE_VARS = {
    "t850": ("TMP", "850_mb"), "u1000": ("UGRD", "1000_mb"), "v1000": ("VGRD", "1000_mb"),
    "z1000": ("HGT", "1000_mb"), "u850": ("UGRD", "850_mb"), "v850": ("VGRD", "850_mb"),
    "z850": ("HGT", "850_mb"), "u500": ("UGRD", "500_mb"), "v500": ("VGRD", "500_mb"),
    "z500": ("HGT", "500_mb"), "t500": ("TMP", "500_mb"), "z50": ("HGT", "50_mb"),
    "r500": ("RH", "500_mb"), "r850": ("RH", "850_mb"),
    "u250": ("UGRD", "250_mb"), "v250": ("VGRD", "250_mb"), "z250": ("HGT", "250_mb"),
    "t250": ("TMP", "250_mb"),
}

TCWV_PARAM = ("PWAT", None, None)  # single-level, no level key needed

_model = None


def _now():
    return datetime.now(timezone.utc)


def _latest_cycle() -> tuple[str, str]:
    now = _now()
    h = now.hour
    cycle = max(0, (h // 6) * 6)
    return now.strftime("%Y%m%d"), f"{cycle:02d}"


def _gfs_url(param: str, level_key: str | None, date: str, cycle: str) -> str:
    url = f"{GFS_BASE}?dir=/gfs.{date}/{cycle}/atmos&file=gfs.t{cycle}z.pgrb2.0p25.f000&var_{param}=on"
    if level_key:
        url += f"&lev_{level_key}=on"
    url += "&subregion=&toplat=90&leftlon=0&rightlon=360&bottomlat=-90"
    return url


def _download_grib(url: str, dest: Path, retries: int = 3) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        return True
    ctx = ssl.create_default_context(cafile=certifi.where())
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cuacadx/0.2"})
            with urllib.request.urlopen(req, context=ctx, timeout=180) as resp:
                with open(dest, "wb") as f:
                    f.write(resp.read())
            if dest.stat().st_size > 100:
                return True
            dest.unlink()
        except Exception as e:
            wait = (attempt + 1) * 5
            logger.warning(f"GFS retry {attempt+1}/{retries} after {wait}s: {e}")
            time.sleep(wait)
    return False


def _extract_grib_field(path: Path) -> np.ndarray | None:
    try:
        ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"errors": "ignore"})
        field = None
        for var in ds.data_vars:
            arr = ds[var].values.squeeze()
            if arr.ndim == 2:
                field = arr.astype(np.float32)
                break
        ds.close()
        return field
    except Exception as e:
        logger.warning(f"GRIB parse failed {path.name}: {e}")
        return None


def load_model() -> FCN:
    global _model
    if _model is not None:
        return _model
    pkg = Package(str(MODEL_DIR.resolve()))
    _model = FCN.load_model(pkg)
    _model.eval()
    logger.info(f"Model: {sum(p.numel() for p in _model.parameters()):,} params, {type(_model.model).__name__}")
    return _model


def download_ic(date: str, cycle: str) -> torch.Tensor | None:
    """Download all 26 GFS vars, extract, regrid, build [1,1,26,720,1440] tensor (float32)."""
    out_path = DATA_DIR / date / cycle / "ic.npy"
    if out_path.exists():
        logger.info(f"  Using cached IC: {out_path}")
        arr = np.load(out_path).astype(np.float32)
        return torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)

    tmp = DATA_DIR / date / cycle / "gribs"
    tmp.mkdir(parents=True, exist_ok=True)

    fields: dict[str, np.ndarray] = {}

    def _grab(fcn_var: str, param: str, level_key: str | None):
        dest = tmp / f"{fcn_var}.grib2"
        if dest.exists() and dest.stat().st_size > 100:
            field = _extract_grib_field(dest)
            if field is not None and field.shape == (721, 1440):
                fields[fcn_var] = field[:-1, :].copy()
                return
        url = _gfs_url(param, level_key, date, cycle)
        if not _download_grib(url, dest):
            raise RuntimeError(f"Failed to download {fcn_var}")
        field = _extract_grib_field(dest)
        if field is None or field.shape != (721, 1440):
            raise RuntimeError(f"Bad {fcn_var}: {field.shape if field is not None else None}")
        fields[fcn_var] = field[:-1, :].copy()

    for v, (p, _, lk) in SURFACE_VARS.items():
        logger.info(f"  GFS: {v}")
        _grab(v, p, lk)
        time.sleep(2)
    for v, (p, lk) in PRESSURE_VARS.items():
        logger.info(f"  GFS: {v}")
        _grab(v, p, lk)
        time.sleep(1)
    logger.info("  GFS: tcwv")
    _grab("tcwv", "PWAT", None)

    # Build tensor in VARIABLES order
    channels = [fields[v].astype(np.float32) for v in VARIABLES]
    arr = np.stack(channels, axis=0)
    # Convert HGT from gpm to specific geopotential (m²/s²)
    HGT_VARS = {"z1000", "z850", "z500", "z250", "z50"}
    for vi, v in enumerate(VARIABLES):
        if v in HGT_VARS:
            arr[vi] *= 9.80665
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(out_path, arr)
    logger.info(f"  Cached IC: {out_path}")
    return torch.from_numpy(arr).unsqueeze(0).unsqueeze(0)


def run_forecast(ic: torch.Tensor, n_steps: int = 28) -> list[torch.Tensor]:
    """Auto-regressive forecast. n_steps=28 -> 168h."""
    model = load_model()
    model.eval()

    x = ic
    outputs = []
    with torch.inference_mode():
        for step in range(n_steps):
            t0 = time.perf_counter()
            x = model._forward(x)
            dt = time.perf_counter() - t0
            outputs.append(x.cpu())
            t2m = x[0, 0, 2, 360, 720].item()
            arr = x[0, 0].numpy()
            logger.info(f"  +{(step+1)*6:3d}h  {dt:.2f}s  t2m@eq={t2m-273.15:.1f}°C  "
                        f"min={arr.min():.0f} max={arr.max():.0f}")
            if step >= 2:
                step_change = abs(arr - outputs[-2][0, 0].numpy()).max()
                if step_change > 50000:
                    logger.warning(f"  Large step change: {step_change:.0f}")
    return outputs


def crop_kalimantan(outputs: list[torch.Tensor]) -> pd.DataFrame:
    """Extract Kalimantan bbox from forecast tensors."""
    bbox = KALIMANTAN_BBOX
    lon_ticks = np.linspace(0.125, 359.875, 1440)
    lat_ticks = np.linspace(89.875, -89.875, 720)

    kal_lons = np.arange(bbox["lon_min"], bbox["lon_max"] + 0.01, 0.25)
    kal_lons_360 = np.where(kal_lons < 0, kal_lons + 360, kal_lons)
    kal_lats = np.arange(bbox["lat_max"], bbox["lat_min"] - 0.01, -0.25)

    lon_idx = np.searchsorted(lon_ticks, kal_lons_360)
    lat_idx = np.searchsorted(-lat_ticks, -kal_lats)
    lon_idx = lon_idx[(lon_idx >= 0) & (lon_idx < 1440)]
    lat_idx = lat_idx[(lat_idx >= 0) & (lat_idx < 720)]
    n_lon, n_lat = len(lon_idx), len(lat_idx)

    rows = []
    for step, t in enumerate(outputs):
        lead = (step + 1) * 6
        arr = t.squeeze().numpy()
        for vi, var in enumerate(VARIABLES):
            sub = arr[vi][np.ix_(lat_idx, lon_idx)]
            flat = sub.ravel()
            for ri in range(n_lat):
                base = ri * n_lon
                for ci in range(n_lon):
                    rows.append((
                        lead,
                        var,
                        kal_lats[ri],
                        kal_lons[ci],
                        float(flat[base + ci]),
                    ))

    df = pd.DataFrame(rows, columns=["lead_time_h", "variable", "lat", "lon", "value"])
    df["source"] = "fcn"
    return df


def forecast(date: str | None = None, cycle: str | None = None,
             n_steps: int = 28) -> pd.DataFrame | None:
    """Real GFS → FourCastNet forecast → Kalimantan crop."""
    if date is None or cycle is None:
        date, cycle = _latest_cycle()
    logger.info(f"FCN forecast {date} {cycle}z, {n_steps} steps ({n_steps*6}h)")

    logger.info("Downloading GFS IC...")
    t0 = time.perf_counter()
    ic = download_ic(date, cycle)
    if ic is None:
        return None
    logger.info(f"  IC: {ic.shape} ({time.perf_counter()-t0:.1f}s)")

    logger.info("Running forecast...")
    t0 = time.perf_counter()
    outputs = run_forecast(ic.float(), n_steps)
    logger.info(f"  Done ({time.perf_counter()-t0:.1f}s)")

    logger.info("Cropping to Kalimantan...")
    t0 = time.perf_counter()
    df = crop_kalimantan(outputs)
    logger.info(f"  {len(df):,} rows ({time.perf_counter()-t0:.1f}s)")

    out_dir = DATA_DIR / date / cycle
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "forecast.parquet"
    df.to_parquet(path, index=False)
    logger.info(f"Saved: {path} ({path.stat().st_size/1024/1024:.1f}MB)")
    return df
