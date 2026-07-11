import re
from pathlib import Path
from functools import lru_cache

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ERA5_DIR = ROOT / "data" / "era5"
GFS_DIR = ROOT / "data" / "gfs"

TRANSFORMS = {
    "t2m": lambda v: round(v - 273.15, 1),
    "d2m": lambda v: round(v - 273.15, 1),
    "u10": lambda v: round(v, 1),
    "v10": lambda v: round(v, 1),
    "sp": lambda v: round(v / 100, 1),
    "msl": lambda v: round(v / 100, 1),
    "tp": lambda v: round(v, 5),
}

UNITS = {
    "t2m": "°C", "d2m": "°C", "u10": "m/s", "v10": "m/s",
    "sp": "hPa", "msl": "hPa", "tp": "m",
}

VARIABLE_LABELS = {
    "t2m": "Temperature (2m)", "d2m": "Dewpoint (2m)",
    "u10": "U Wind (10m)", "v10": "V Wind (10m)",
    "sp": "Surface Pressure", "msl": "MSL Pressure",
    "tp": "Precipitation",
}

ALL_VARIABLES = list(TRANSFORMS.keys())


def _find_gfs_latest() -> Path | None:
    if not GFS_DIR.exists():
        return None
    for date_dir in sorted(GFS_DIR.iterdir(), reverse=True):
        if date_dir.is_dir():
            for cycle_dir in sorted(date_dir.iterdir(), reverse=True):
                if cycle_dir.is_dir() and list(cycle_dir.glob("*.parquet")):
                    return cycle_dir
    return None


def get_sources() -> list[dict]:
    sources = []

    if ERA5_DIR.exists() and ERA5_DIR.glob("*/*/*.parquet"):
        sources.append({
            "id": "era5",
            "name": "ERA5 Reanalysis",
            "description": "Hourly · 0.25° (~28km)",
            "variables": ALL_VARIABLES,
        })

    gfs_dir = _find_gfs_latest()
    if gfs_dir:
        sources.append({
            "id": "gfs",
            "name": "GFS Forecast",
            "description": f"Latest cycle ({gfs_dir.parent.name}/{gfs_dir.name}) · 3-6h lead · 0.25°",
            "variables": ALL_VARIABLES,
        })

    return sources


def _load_era5(var: str) -> pd.DataFrame:
    path = ERA5_DIR / "2024" / "01" / f"{var}.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    transform = TRANSFORMS.get(var)
    if transform:
        val_col = var
        df["v"] = df[val_col].apply(transform)
    else:
        df["v"] = df[var]
    df["ts"] = df["valid_time"].astype(str)
    return df


def _load_gfs(var: str) -> pd.DataFrame:
    gfs_dir = _find_gfs_latest()
    if not gfs_dir:
        return pd.DataFrame()
    frames = []
    for pf in sorted(gfs_dir.glob(f"{var}_*.parquet")):
        m = re.match(rf"{var}_(\d+)\.parquet", pf.name)
        if not m:
            continue
        fh = int(m.group(1))
        df = pd.read_parquet(pf)
        transform = TRANSFORMS.get(var)
        if transform:
            df["v"] = df["value"].apply(transform)
        else:
            df["v"] = df["value"]
        df["forecast_hour"] = fh
        df["ts"] = df["valid_time"].astype(str) + f" (+{fh:03d}h)"
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@lru_cache(maxsize=32)
def _cached_load(source: str, var: str) -> pd.DataFrame:
    if source == "era5":
        return _load_era5(var)
    elif source == "gfs":
        return _load_gfs(var)
    return pd.DataFrame()


def get_timestamps(source: str, var: str) -> list[str]:
    df = _cached_load(source, var)
    if df.empty:
        return []
    return sorted(df["ts"].unique())


def get_frame(source: str, var: str, ts: str) -> list[dict]:
    df = _cached_load(source, var)
    if df.empty:
        return []
    row = df[df["ts"] == ts]
    if row.empty:
        return []
    return row[["lat", "lon", "v"]].to_dict(orient="records")


def get_point_series(source: str, var: str, lat: float, lon: float) -> list[dict]:
    df = _cached_load(source, var)
    if df.empty:
        return []
    row = df[(df["lat"] == lat) & (df["lon"] == lon)].copy()
    if row.empty:
        return []
    return row[["ts", "v"]].to_dict(orient="records")


def get_variable_info(var: str) -> dict:
    return {
        "id": var,
        "label": VARIABLE_LABELS.get(var, var),
        "unit": UNITS.get(var, ""),
    }
