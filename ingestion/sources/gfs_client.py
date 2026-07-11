import logging
import ssl
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import certifi
import pandas as pd
import xarray as xr

from ..config import KALTIM_BBOX

logger = logging.getLogger(__name__)

GFS_BASE = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"

GFS_VARIABLES = {
    "t2m": {"param": "TMP", "level": "2 m above ground"},
    "d2m": {"param": "DPT", "level": "2 m above ground"},
    "u10": {"param": "UGRD", "level": "10 m above ground"},
    "v10": {"param": "VGRD", "level": "10 m above ground"},
    "sp": {"param": "PRES", "level": "surface"},
    "msl": {"param": "PRMSL", "level": "mean sea level"},
    "tp": {"param": "APCP", "level": "surface"},
}

GFS_LEVEL_KEYS = {
    "2 m above ground": "2_m_above_ground",
    "10 m above ground": "10_m_above_ground",
    "surface": "surface",
    "mean sea level": "mean_sea_level",
}


def _ssl_ctx():
    return ssl.create_default_context(cafile=certifi.where())


def _latest_cycle() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    date = now.strftime("%Y%m%d")
    h = now.hour
    cycle = (h // 6) * 6
    cycle_str = f"{cycle:02d}"
    return date, cycle_str


def _gfs_url(
    date: str, cycle: str, fcst_hour: int, param: str, level: str, bbox: dict
) -> str:
    level_key = GFS_LEVEL_KEYS[level]
    return (
        f"{GFS_BASE}?dir=/gfs.{date}/{cycle}/atmos"
        f"&file=gfs.t{cycle}z.pgrb2.0p25.f{fcst_hour:03d}"
        f"&var_{param}=on&lev_{level_key}=on"
        f"&subregion="
        f"&toplat={bbox['lat_max']}&leftlon={bbox['lon_min']}"
        f"&rightlon={bbox['lon_max']}&bottomlat={bbox['lat_min']}"
    )


def _download_grib2(url: str, dest: Path) -> Path | None:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        ctx = _ssl_ctx()
        with urllib.request.urlopen(url, context=ctx, timeout=60) as resp:
            with open(dest, "wb") as f:
                f.write(resp.read())
        return dest
    except Exception as e:
        logger.warning(f"Download failed {dest.name}: {e}")
        return None


def _grib_to_parquet(grib_path: Path, var: str, fcst_hour: int) -> Path | None:
    parquet_path = grib_path.with_suffix(".parquet")
    if parquet_path.exists():
        return parquet_path

    try:
        ds = xr.open_dataset(
            grib_path,
            engine="cfgrib",
            backend_kwargs={"errors": "ignore"},
        )
        df = ds.to_dataframe().reset_index()
        ds.close()

        val_col = [c for c in df.columns if c not in (
            "lat", "lon", "latitude", "longitude", "time", "step",
            "valid_time", "surface", "meanSea", "meansea",
            "heightAboveGround", "height_above_ground",
            "isobaricInhPa", "isobaricinhpa",
        )]
        if val_col:
            df["value"] = df[val_col[0]]
        else:
            logger.warning(f"No value column found in {grib_path.name}")
            return None

        df = df.rename(columns={"latitude": "lat", "longitude": "lon"})
        df["variable"] = var
        df["source"] = "gfs"
        df["forecast_hour"] = fcst_hour
        df[["valid_time", "lat", "lon", "value", "variable", "source", "forecast_hour"]].to_parquet(parquet_path, index=False)

        grib_path.unlink(missing_ok=True)
        return parquet_path

    except Exception as e:
        logger.warning(f"Parse failed {grib_path.name}: {e}")
        return None


def fetch_forecast(
    date: str | None = None,
    cycle: str | None = None,
    max_lead_hours: int = 48,
) -> dict[str, pd.DataFrame]:
    bbox = KALTIM_BBOX
    if date is None or cycle is None:
        date, cycle = _latest_cycle()

    fcst_hours = [h for h in [0, 3, 6, 9, 12, 18, 24, 36, 48] if h <= max_lead_hours]
    out_dir = Path("data") / "gfs" / date / cycle
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {var: [] for var in GFS_VARIABLES}

    for fh in fcst_hours:
        logger.info(f"  +{fh:03d}h")
        for var, spec in GFS_VARIABLES.items():
            grib_path = out_dir / f"{var}_{fh:03d}.grib2"
            url = _gfs_url(date, cycle, fh, spec["param"], spec["level"], bbox)
            path = _download_grib2(url, grib_path)
            if path is None:
                continue
            parquet_path = _grib_to_parquet(path, var, fh)
            if parquet_path:
                df = pd.read_parquet(parquet_path)
                results[var].append(df)

    merged = {}
    for var, frames in results.items():
        if frames:
            merged[var] = pd.concat(frames, ignore_index=True)
            logger.info(f"  {var}: {len(merged[var])} rows")
    return merged


def fetch_today() -> dict[str, pd.DataFrame]:
    return fetch_forecast()


def fetch_tomorrow() -> dict[str, pd.DataFrame]:
    date, cycle = _latest_cycle()
    dt = datetime.strptime(date, "%Y%m%d") + timedelta(days=1)
    return fetch_forecast(date=dt.strftime("%Y%m%d"), cycle=cycle)
