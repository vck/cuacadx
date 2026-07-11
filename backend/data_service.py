import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from functools import lru_cache

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ERA5_DIR = ROOT / "data" / "era5"
GFS_DIR = ROOT / "data" / "gfs"
HIMAWARI_DIR = ROOT / "data" / "himawari9"
FCN_DIR = ROOT / "data" / "fcn"

TRANSFORMS = {
    "t2m": lambda v: round(v - 273.15, 1),
    "d2m": lambda v: round(v - 273.15, 1),
    "u10": lambda v: round(v, 1),
    "v10": lambda v: round(v, 1),
    "sp": lambda v: round(v / 100, 1),
    "msl": lambda v: round(v / 100, 1),
    "tp": lambda v: round(v, 5),
}

# FCN-specific transforms
FCN_TRANSFORMS = {
    "t2m": lambda v: round(v - 273.15, 1),
    "t850": lambda v: round(v - 273.15, 1),
    "t500": lambda v: round(v - 273.15, 1),
    "t250": lambda v: round(v - 273.15, 1),
    "sp": lambda v: round(v / 100, 1),
    "msl": lambda v: round(v / 100, 1),
    "u10m": lambda v: round(v, 1),
    "v10m": lambda v: round(v, 1),
    "u100m": lambda v: round(v, 1),
    "v100m": lambda v: round(v, 1),
    "u250": lambda v: round(v, 1),
    "v250": lambda v: round(v, 1),
    "u850": lambda v: round(v, 1),
    "v850": lambda v: round(v, 1),
    "u1000": lambda v: round(v, 1),
    "v1000": lambda v: round(v, 1),
    "u500": lambda v: round(v, 1),
    "v500": lambda v: round(v, 1),
    "z1000": lambda v: round(v / 9.80665, 1),
    "z850": lambda v: round(v / 9.80665, 1),
    "z500": lambda v: round(v / 9.80665, 1),
    "z250": lambda v: round(v / 9.80665, 1),
    "z50": lambda v: round(v / 9.80665, 1),
    "r500": lambda v: round(v, 1),
    "r850": lambda v: round(v, 1),
    "tcwv": lambda v: round(v, 2),
}

UNITS = {
    "t2m": "°C", "d2m": "°C", "u10": "m/s", "v10": "m/s",
    "sp": "hPa", "msl": "hPa", "tp": "m", "bt": "K",
    "t850": "°C", "t500": "°C", "t250": "°C",
    "u10m": "m/s", "v10m": "m/s", "u100m": "m/s", "v100m": "m/s",
    "u250": "m/s", "v250": "m/s", "u850": "m/s", "v850": "m/s",
    "u1000": "m/s", "v1000": "m/s", "u500": "m/s", "v500": "m/s",
    "z1000": "m", "z850": "m", "z500": "m", "z250": "m", "z50": "m",
    "r500": "%", "r850": "%", "tcwv": "kg/m²",
}

VARIABLE_LABELS = {
    "t2m": "Temperature (2m)", "d2m": "Dewpoint (2m)",
    "u10": "U Wind (10m)", "v10": "V Wind (10m)",
    "sp": "Surface Pressure", "msl": "MSL Pressure",
    "tp": "Precipitation", "bt": "BT Band 13",
    "t850": "Temp @ 850hPa", "t500": "Temp @ 500hPa", "t250": "Temp @ 250hPa",
    "u10m": "U Wind @ 10m", "v10m": "V Wind @ 10m",
    "u100m": "U Wind @ 100m", "v100m": "V Wind @ 100m",
    "u250": "U Wind @ 250hPa", "v250": "V Wind @ 250hPa",
    "u850": "U Wind @ 850hPa", "v850": "V Wind @ 850hPa",
    "u1000": "U Wind @ 1000hPa", "v1000": "V Wind @ 1000hPa",
    "u500": "U Wind @ 500hPa", "v500": "V Wind @ 500hPa",
    "z1000": "Geopotential @ 1000hPa", "z850": "Geopotential @ 850hPa",
    "z500": "Geopotential @ 500hPa", "z250": "Geopotential @ 250hPa",
    "z50": "Geopotential @ 50hPa",
    "r500": "Rel Humidity @ 500hPa", "r850": "Rel Humidity @ 850hPa",
    "tcwv": "Total Column Water Vapor",
}

ALL_VARIABLES = list(TRANSFORMS.keys())
FCN_VARIABLES = list(FCN_TRANSFORMS.keys())

# Downsample himawari: keep 1 out of every N rows to stay fast
HIMAWARI_DOWNSAMPLE = 5


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

    sources.append({
        "id": "fcn",
        "name": "7-Day AI Forecast",
        "description": "6–168h (7-day) · 0.25° · global AI model",
        "variables": FCN_VARIABLES,
    })

    if HIMAWARI_DIR.exists():
        sources.append({
            "id": "himawari9",
            "name": "Himawari-9 IR",
            "description": "Band 13 (10.4µm) · 2km · every 10 min",
            "variables": ["bt"],
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


def _find_himawari_timestamps() -> list[str]:
    if not HIMAWARI_DIR.exists():
        return []
    ts_list = []
    for year in sorted(HIMAWARI_DIR.iterdir()):
        if not year.is_dir():
            continue
        for month in sorted(year.iterdir()):
            if not month.is_dir():
                continue
            for day in sorted(month.iterdir()):
                if not day.is_dir():
                    continue
                for time_dir in sorted(day.iterdir()):
                    if not time_dir.is_dir():
                        continue
                    if list(time_dir.glob("*.parquet")):
                        t = time_dir.name
                        ts_list.append(f"{year.name}-{month.name}-{day.name} {t[:2]}:{t[2:]}:00")
    return ts_list


def _load_himawari(ts: str) -> pd.DataFrame:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):\d{2}", ts)
    if not m:
        return pd.DataFrame()
    path = HIMAWARI_DIR / m.group(1) / m.group(2) / m.group(3) / f"{m.group(4)}{m.group(5)}" / "bt.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    df["v"] = df["bt_k"].round(1)
    df["ts"] = ts
    if len(df) > 10000:
        df = df.iloc[::HIMAWARI_DOWNSAMPLE].reset_index(drop=True)
    return df[["lat", "lon", "v", "ts"]]


FCN_CACHE: dict[str, pd.DataFrame] = {}


def _load_fcn(var: str) -> pd.DataFrame:
    if var in FCN_CACHE:
        return FCN_CACHE[var]

    logger = __import__("logging").getLogger(__name__)

    # Look for latest cached forecast
    forecast_dir = None
    if FCN_DIR.exists():
        for date_dir in sorted(FCN_DIR.iterdir(), reverse=True):
            if date_dir.is_dir():
                for cycle_dir in sorted(date_dir.iterdir(), reverse=True):
                    if cycle_dir.is_dir():
                        pf = cycle_dir / "forecast.parquet"
                        if pf.exists():
                            forecast_dir = cycle_dir
                            break
                if forecast_dir:
                    break

    if forecast_dir:
        logger.info(f"Loading cached FCN forecast: {forecast_dir}")
        df = pd.read_parquet(forecast_dir / "forecast.parquet")
    else:
        logger.info("No cached FCN forecast found. Generating one...")
        from ingestion.models.fourcastnet_pipeline import VARIABLES, forecast
        df = forecast()

    for v in df["variable"].unique():
        sub = df[df["variable"] == v].copy()
        transform = FCN_TRANSFORMS.get(v)
        if transform:
            sub["v"] = sub["value"].apply(transform)
        else:
            sub["v"] = sub["value"]

        # Convert lead hours to actual dates
        if forecast_dir:
            base_hour = int(forecast_dir.name)
            base_date = datetime(int(forecast_dir.parent.name[:4]), int(forecast_dir.parent.name[4:6]), int(forecast_dir.parent.name[6:8]), base_hour, tzinfo=timezone.utc)
            sub["ts"] = sub["lead_time_h"].apply(lambda h: (base_date + timedelta(hours=h)).strftime("%b %d %H:%M"))
        else:
            sub["ts"] = "D" + (sub["lead_time_h"] // 6 + 1).astype(str) + " " + ((sub["lead_time_h"] % 24)).astype(str) + "h"
        FCN_CACHE[v] = sub[["lat", "lon", "v", "ts"]]

    return FCN_CACHE.get(var, pd.DataFrame())


@lru_cache(maxsize=32)
def _cached_load(source: str, var: str) -> pd.DataFrame:
    if source == "era5":
        return _load_era5(var)
    elif source == "gfs":
        return _load_gfs(var)
    elif source == "himawari9":
        return _load_himawari(var)
    elif source == "fcn":
        return _load_fcn(var)
    return pd.DataFrame()


def get_timestamps(source: str, var: str) -> list[str]:
    if source == "himawari9":
        return _find_himawari_timestamps()
    df = _cached_load(source, var)
    if df.empty:
        return []
    return sorted(df["ts"].unique())


def get_frame(source: str, var: str, ts: str) -> list[dict]:
    if source == "himawari9":
        df = _load_himawari(ts)
    else:
        df = _cached_load(source, var)
    if df.empty:
        return []
    if source != "himawari9":
        row = df[df["ts"] == ts]
    else:
        row = df
    if row.empty:
        return []
    return row[["lat", "lon", "v"]].to_dict(orient="records")


def get_point_series(source: str, var: str, lat: float, lon: float) -> list[dict]:
    if source == "himawari9":
        timestamps = _find_himawari_timestamps()
        result = []
        for ts in timestamps:
            df = _load_himawari(ts)
            row = df[(df["lat"].round(4) == round(lat, 4)) & (df["lon"].round(4) == round(lon, 4))]
            if not row.empty:
                result.append({"ts": ts, "v": row.iloc[0]["v"]})
        return result

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


# ── Storm cell detection ─────────────────────────────────────────────────

def detect_himawari_cells(ts: str) -> list[dict]:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):\d{2}", ts)
    if not m:
        return []
    path = HIMAWARI_DIR / m.group(1) / m.group(2) / m.group(3) / f"{m.group(4)}{m.group(5)}" / "bt.parquet"
    if not path.exists():
        return []
    from ingestion.models.storm_cell import detect_cells
    import pyarrow.parquet as pq
    import numpy as np
    tbl = pq.read_table(str(path), columns=["lat", "lon", "bt_k"])
    lat = np.array(tbl.column("lat"))
    lon = np.array(tbl.column("lon"))
    bt = np.array(tbl.column("bt_k"))
    return detect_cells(bt, lat, lon)
