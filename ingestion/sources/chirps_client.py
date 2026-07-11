import calendar
import gzip
import logging
import shutil
import ssl
from pathlib import Path
from urllib.request import urlopen

import certifi
import pandas as pd
import xarray as xr

from ..config import CHIRPS_DIR, KALTIM_BBOX

logger = logging.getLogger(__name__)

CHIRPS_BASE = "https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05"


def _month_days(year: int, month: int) -> list[str]:
    _, ndays = calendar.monthrange(year, month)
    return [str(d).zfill(2) for d in range(1, ndays + 1)]


def _tif_url(year: int, month: int, day: str) -> str:
    return f"{CHIRPS_BASE}/{year}/chirps-v2.0.{year}.{month:02d}.{day}.tif.gz"


def _download_tif_gz(url: str, dest: Path) -> Path:
    ctx = ssl.create_default_context(cafile=certifi.where())
    dest_gz = dest.with_suffix(".tif.gz")
    with urlopen(url, context=ctx) as resp:
        with open(dest_gz, "wb") as f:
            shutil.copyfileobj(resp, f)

    tif_path = dest
    with gzip.open(dest_gz, "rb") as f_in:
        with open(tif_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    dest_gz.unlink()
    return tif_path


def _crop_to_bbox(da: xr.DataArray, bbox: dict) -> xr.DataArray:
    return da.sel(
        lat=slice(bbox["lat_min"], bbox["lat_max"]),
        lon=slice(bbox["lon_min"], bbox["lon_max"]),
    )


def _da_to_df(da: xr.DataArray, ts: pd.Timestamp) -> pd.DataFrame:
    df = da.to_dataframe(name="precip").reset_index()
    df["ts_utc"] = ts
    df["source"] = "chirps"
    df = df.rename(columns={"latitude": "lat", "longitude": "lon"})
    return df


def fetch_month(year: int, month: int) -> pd.DataFrame | None:
    """Download all daily CHIRPS GeoTIFFs for one month, return stacked DataFrame."""
    bbox = KALTIM_BBOX
    days = _month_days(year, month)
    frames = []

    out_dir = CHIRPS_DIR / str(year) / f"{month:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = out_dir / "precip.parquet"
    if parquet_path.exists():
        logger.info(f"Already exists: {parquet_path}")
        return pd.read_parquet(parquet_path)

    for day in days:
        url = _tif_url(year, month, day)
        tif_path = out_dir / f"chirps_{year}_{month:02d}_{day}.tif"
        if not tif_path.exists():
            try:
                _download_tif_gz(url, tif_path)
            except Exception as e:
                logger.warning(f"Failed to download {url}: {e}")
                continue

        da = xr.open_dataarray(tif_path)
        da_cropped = _crop_to_bbox(da, bbox)
        ts = pd.Timestamp(year, month, int(day))
        df = _da_to_df(da_cropped, ts)
        da.close()
        frames.append(df)

    if not frames:
        logger.warning(f"No CHIRPS data for {year}-{month:02d}")
        return None

    result = pd.concat(frames, ignore_index=True)
    result.to_parquet(parquet_path, index=False)
    logger.info(f"  → {parquet_path}  ({len(result)} rows)")
    return result


def fetch(year: int, month: int) -> pd.DataFrame | None:
    return fetch_month(year, month)
