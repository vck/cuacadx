---
name: era5-download
description: Use when downloading ERA5 reanalysis data from the Copernicus CDS API. Covers variable selection, monthly chunking, bounding box config, Parquet conversion, and CDS API key setup.
---

# ERA5 Download

## Setup

CDS API key goes in `~/.cdsapirc`:
```
url: https://cds.climate.copernicus.eu/api
key: <UID>:<API_KEY>
```

The Python package `cdsapi` reads this file automatically.

## Available Variables (single levels)

| Short | CDS Name | Units | Description |
|-------|----------|-------|-------------|
| `t2m` | `2m_temperature` | K | 2m temperature |
| `d2m` | `2m_dewpoint_temperature` | K | 2m dewpoint temperature |
| `u10` | `10m_u_component_of_wind` | m/s | 10m zonal wind |
| `v10` | `10m_v_component_of_wind` | m/s | 10m meridional wind |
| `sp` | `surface_pressure` | Pa | Surface pressure |
| `msl` | `mean_sea_level_pressure` | Pa | MSL pressure |
| `tp` | `total_precipitation` | m | Total precipitation |

Config in `ingestion/config.py`: `ERA5_VARIABLES`, `ERA5_CDS_NAMES`,
`ERA5_UNITS`, `KALTIM_BBOX`.

## Strategy

**One variable at a time, one month at a time.** Multi-variable CDS requests
frequently get 500 errors. Each single-variable single-month NetCDF is
~500-800 KB for the Kaltim bounding box (25×17 grid, hourly).

### Retry logic

The CDS API can return transient 500s. The client retries up to 5 times with
exponential backoff (60s, 120s, ...).

## Pipeline

1. `era5_client.download_variable(year, month, var)` → CDS API → NetCDF
2. `era5_client.nc_to_parquet(nc_path)` → xarray → DataFrame → per-variable Parquet
3. NetCDF deleted after successful conversion

### Output columns (Parquet)

```
valid_time  TIMESTAMP  — hourly timesteps
lat         DOUBLE     — grid latitude
lon         DOUBLE     — grid longitude
number      INT        — ensemble member (0 for deterministic)
expver      STRING     — experiment version
t2m/d2m/.. FLOAT      — value column, named after the variable
variable    STRING     — short name (e.g. "t2m")
source      STRING     — always "era5"
```

## Entry point

```bash
python run_ingestion.py --year 2024 --month 1        # single month
python run_ingestion.py --backfill                    # full YEAR_START..YEAR_END
python run_ingestion.py --year 2024 --month 1 --skip-chirps
```

## File layout

```
data/era5/
├── 2024/
│   ├── 01/
│   │   ├── t2m.parquet
│   │   ├── d2m.parquet
│   │   ├── u10.parquet
│   │   ├── v10.parquet
│   │   ├── sp.parquet
│   │   ├── msl.parquet
│   │   └── tp.parquet
│   └── 02/
│       └── ...
└── 2025/
    └── ...
```

## Bounding box format

CDS API uses `[N, W, S, E]` (lat_max, lon_min, lat_min, lon_max).
`ingestion/config.py` stores named keys and converts automatically.

## CHIRPS (rainfall ground truth)

CHIRPS is daily precipitation from UCSB CHC, served as GeoTIFF over HTTP:

```
https://data.chc.ucsb.edu/products/CHIRPS-2.0/global_daily/tifs/p05/<year>/chirps-v2.0.<year>.<month>.<day>.tif.gz
```

Each daily file is ~2-5 MB for the global grid. The client downloads,
decompresses, crops to the Kaltim bbox, and stacks daily frames into a
monthly `precip.parquet`.

macOS SSL workaround: uses `certifi.where()` for the SSL context in
`chirps_client.py`.

Output columns: `lat, lon, precip, ts_utc, source` (always "chirps").
