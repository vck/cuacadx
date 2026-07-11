# CUACADX — Agents & Project Rules

Regional weather intelligence engine for Indonesia. Downscaling + nowcasting
layer on top of global NWP/AI models, calibrated to local ground truth, with
Himawari-9 storm-cell nowcasting.

## General Rules

- **NEVER `rm -rf` data.** Archive instead. Data is precious and expensive to
  regenerate (ERA5 takes ~5 min/variable/month via CDS API, GFS is real-time).
- Parquet is the canonical storage format. All ingested data ends up as
  partitioned Parquet under `data/`.
- `ingestion/config.py` is the single source of truth for bounding boxes,
  variable lists, and paths.
- The `.venv` has all dependencies installed. Activate with
  `source .venv/bin/activate`.
- For viz, run `python viz.py` and open http://localhost:8765.

---

## Agent: data-engineer

**Mode:** subagent
**Best for:** Downloading, processing, and maintaining weather data pipelines

Handles all data ingestion tasks:
- **ERA5** via CDS API (`ingestion/sources/era5_client.py`) — one variable per
  request, monthly chunks, saved as per-variable Parquet.
- **CHIRPS** via UCSB HTTP (`ingestion/sources/chirps_client.py`) — daily
  GeoTIFF download, crop to Kaltim bbox, save as monthly Parquet.
- **GFS** via NOAA NOMADS (`ingestion/sources/gfs_client.py`) — GRIB2 -> Parquet
  via cfgrib, per-variable per-forecast-hour files.
- **Himawari-9** (`ingestion/sources/himawari_client.py`) — AWS S3 bucket
  `noaa-himawari9`, HSD segments.

Key files: `ingestion/config.py`, `ingestion/sources/*.py`, `run_ingestion.py`

CDS API key lives in `~/.cdsapirc`. macOS SSL issues fixed with `certifi`.

---

## Agent: storm-cell-analyst

**Mode:** subagent
**Best for:** Himawari-9 satellite imagery processing, storm detection, tracking

Builds the Phase 1 storm-cell pipeline:
- Reads Himawari-9 Band 13 (10.4µm, 2km) from AWS
- Converts radiance to brightness temperature
- Cold-cloud thresholding (< -60°C) for convective proxy
- Connected-component labeling (`scipy.ndimage.label`)
- Kalman filter tracking with Hungarian association
- Outputs `storm_cells` table in DuckDB schema

Key techniques: multi-band IR thresholding, centroid tracking, velocity
estimation from frame-to-frame association.

---

## Agent: viz-builder

**Mode:** subagent
**Best for:** Building and improving the weather visualization dashboard

Maintains `viz.py` — the Leaflet.js-based interactive map:
- ERA5 (Jan 2024, 744 timestamps, 7 variables)
- GFS (today's forecast, +0h to +48h)
- Switchable source/variable/timestamp dropdowns
- Color-coded grid points on OpenStreetMap tiles

Stack: Python `http.server`, Leaflet.js (CDN), Parquet -> JSON API.

When adding new data sources, follow the same pattern: a `/data/<source>/<var>`
endpoint that returns `{"timestamps": [...], "frames": [[{lat,lon,v}], ...]}`.
