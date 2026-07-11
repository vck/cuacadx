---
name: gfs-download
description: Use when fetching real-time GFS forecast data from NOAA NOMADS. Covers NOMADS filter URL construction, GRIB2 to Parquet via cfgrib, SSL cert handling on macOS, and forecast hour selection.
---

# GFS Download

## Source

NOAA NOMADS filter service for GFS 0.25°:
```
https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl
```

No API key needed. Open HTTP access.

## URL Structure

```
$GFS_BASE
  ?dir=/gfs.<YYYYMMDD>/<HH>/atmos
  &file=gfs.t<HH>z.pgrb2.0p25.f<FFF>
  &var_<PARAM>=on
  &lev_<LEVEL>=on
  &subregion=
  &toplat=<N>&leftlon=<W>&rightlon=<E>&bottomlat=<S>
```

The `dir` parameter is **required** (NOMADS serves multiple models).

## Available Variables

| Short | GRIB Param | Level | Level Key |
|-------|-----------|-------|-----------|
| `t2m` | `TMP` | 2 m above ground | `2_m_above_ground` |
| `d2m` | `DPT` | 2 m above ground | `2_m_above_ground` |
| `u10` | `UGRD` | 10 m above ground | `10_m_above_ground` |
| `v10` | `VGRD` | 10 m above ground | `10_m_above_ground` |
| `sp`  | `PRES` | surface | `surface` |
| `msl` | `PRMSL` | mean sea level | `mean_sea_level` |
| `tp`  | `APCP` | surface | `surface` |

Mapping in `ingestion/sources/gfs_client.py`: `GFS_VARIABLES`, `GFS_LEVEL_KEYS`.

## Forecast Cycles

GFS runs 4x daily: **00z, 06z, 12z, 18z**. Available ~3-4 hours after cycle
time. The client auto-selects the nearest cycle.

## Forecast Hours

| Hours | Coverage |
|-------|----------|
| 0 | Analysis (closest to "now") |
| 3, 6, 9, 12 | Today |
| 18, 24 | Tonight + tomorrow |
| 36, 48 | Day after tomorrow |

Configurable via `max_lead_hours` parameter.

## Pipeline

1. `gfs_client.fetch_forecast()` → NOMADS filter download → GRIB2 files
2. `cfgrib` engine reads GRIB2 via `xarray`
3. Auto-detect value column (varies by parameter)
4. Normalize columns → per-variable per-forecast-hour Parquet
5. GRIB2 files deleted after conversion

### Output columns (Parquet)

```
valid_time     TIMESTAMP  — valid time of forecast
lat            DOUBLE     — grid latitude
lon            DOUBLE     — grid longitude
value          FLOAT      — the forecast value
variable       STRING     — short name (e.g. "t2m")
source         STRING     — always "gfs"
forecast_hour  INT        — lead time in hours (0..48)
```

## macOS SSL

The NOMADS server uses HTTPS with a certificate chain that macOS Python
sometimes can't verify. The client uses `certifi.where()` for the CA bundle:

```python
ctx = ssl.create_default_context(cafile=certifi.where())
```

## Entry point

```python
from ingestion.sources.gfs_client import fetch_forecast
data = fetch_forecast(max_lead_hours=48)
# data is {var: pd.DataFrame} with all forecast hours concatenated
```

Or via the CLI:

```python
python -c "
from ingestion.sources.gfs_client import fetch_today
fetch_today()
"
```

## File layout

```
data/gfs/
└── 20260708/
    └── 12/
        ├── t2m_000.parquet
        ├── t2m_003.parquet
        ├── t2m_006.parquet
        ├── d2m_000.parquet
        └── ...
```

## Limitations

- **APCP at f000 (analysis)** returns empty GRIB2 — no accumulated precipitation
  at step zero. Works from f003 onward.
- Each filter request is a **subset** (not full grid). NOMADS computes the
  subset server-side, so requests are fast (~2-5s).
- Rate limit: be reasonable with concurrent requests (serial is fine).
