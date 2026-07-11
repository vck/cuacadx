import calendar
import logging
import time
from pathlib import Path

import cdsapi
import xarray as xr

from ..config import (
    ERA5_CDS_NAMES,
    ERA5_DIR,
    ERA5_VARIABLES,
    KALTIM_BBOX,
)

logger = logging.getLogger(__name__)


def _month_days(year: int, month: int) -> list[str]:
    _, ndays = calendar.monthrange(year, month)
    return [str(d).zfill(2) for d in range(1, ndays + 1)]


def _hours() -> list[str]:
    return [f"{h:02d}:00" for h in range(0, 24)]


def download_variable(
    year: int, month: int, variable: str, max_retries: int = 5
) -> Path | None:
    """Download a single ERA5 variable for one month → NetCDF.

    CDS API struggles with multi-variable month requests (500 errors),
    so we grab one variable at a time. Each is a much smaller payload.
    """
    cds_name = ERA5_CDS_NAMES[variable]

    out_dir = ERA5_DIR / str(year) / f"{month:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    nc_path = out_dir / f"{variable}.nc"

    if nc_path.exists():
        logger.info(f"  Already exists: {nc_path.name}")
        return nc_path

    client = cdsapi.Client()
    bbox = KALTIM_BBOX
    area = [bbox["lat_max"], bbox["lon_min"], bbox["lat_min"], bbox["lon_max"]]

    for attempt in range(1, max_retries + 1):
        try:
            client.retrieve(
                "reanalysis-era5-single-levels",
                {
                    "product_type": "reanalysis",
                    "variable": [cds_name],
                    "year": str(year),
                    "month": f"{month:02d}",
                    "day": _month_days(year, month),
                    "time": _hours(),
                    "area": area,
                    "format": "netcdf",
                },
                str(nc_path),
            )
            logger.info(f"  Downloaded: {nc_path.name}")
            return nc_path

        except Exception as e:
            logger.warning(
                f"  Attempt {attempt}/{max_retries} failed for {variable}: {e}"
            )
            if attempt < max_retries:
                wait = 60 * attempt
                logger.info(f"  Waiting {wait}s before retry...")
                time.sleep(wait)
            else:
                logger.error(f"  Gave up on {variable} after {max_retries} attempts")
                return None


def nc_to_parquet(nc_path: Path) -> Path | None:
    """Convert single-variable NetCDF → Parquet."""
    var = nc_path.stem
    parquet_path = nc_path.with_suffix(".parquet")

    if parquet_path.exists():
        return parquet_path

    try:
        ds = xr.open_dataset(nc_path, chunks={"time": 48})
        cds_name = list(ds.data_vars)[0]
        da = ds[cds_name]
        df = da.to_dataframe().reset_index()
        df.columns = [c.lower() for c in df.columns]
        df = df.rename(columns={"latitude": "lat", "longitude": "lon"})
        df["variable"] = var
        df["source"] = "era5"
        df.to_parquet(parquet_path, index=False)
        ds.close()

        nc_path.unlink()
        logger.info(f"  → {parquet_path.name}  ({len(df)} rows)")
        return parquet_path

    except Exception as e:
        logger.error(f"  Failed to convert {nc_path.name}: {e}")
        return None


def fetch(
    year: int, month: int, variables: list[str] | None = None
) -> dict[str, Path]:
    """Download each ERA5 variable separately for (year, month) → Parquet."""
    if variables is None:
        variables = ERA5_VARIABLES

    paths = {}
    for var in variables:
        nc_path = download_variable(year, month, var)
        if nc_path is None:
            continue
        parquet_path = nc_to_parquet(nc_path)
        if parquet_path is not None:
            paths[var] = parquet_path

    return paths
