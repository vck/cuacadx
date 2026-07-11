# CUACADX — Regional Weather Intelligence Engine for Indonesia

Downscaling + nowcasting layer on top of global NWP/AI models, calibrated to
local ground truth, with Himawari-9 storm-cell nowcasting for convective events
that global models can't resolve.

## Quick Start

```bash
source .venv/bin/activate
python run_ingestion.py --year 2024 --month 1   # download ERA5 for Jan 2024
python run_ingestion.py --backfill               # full 2020–2024 backfill
python run_ingestion.py --help                   # see all options
```

## Live Dashboard

```bash
python viz.py
```

Open **http://localhost:8765** — interactive Leaflet map with:

- **ERA5** — Jan 2024, 744 hourly timestamps, 7 variables (temperature, wind,
  pressure, precipitation), 425 grid points (0.25° ~28km)
- **GFS** — latest 48-hour forecast from NOAA NOMADS, 7 lead times

Toggle between sources, variables, and timestamps via dropdowns.

## Project Structure

```
cuacadx/
├── ingestion/
│   ├── config.py                  # bounding box, variables, paths
│   ├── sources/
│   │   ├── era5_client.py         # CDS API → monthly Parquet
│   │   ├── chirps_client.py       # UCSB GeoTIFF → Parquet
│   │   └── gfs_client.py          # NOMADS GRIB2 → Parquet
│   ├── transform/
│   │   └── qc.py                  # range checks
│   └── loaders/
│       └── duckdb_loader.py       # schema + Parquet views
├── data/
│   ├── era5/                      # ERA5 Parquet (partitioned by year/month)
│   └── gfs/                       # GFS forecast Parquet
├── run_ingestion.py               # CLI entry point
├── viz.py                         # Leaflet visualization server
├── BLUEPRINT.md                   # full technical & product plan
└── opencode.json                  # opencode AI configuration
```

## Data Sources

| Source | What | Access | Status |
|--------|------|--------|--------|
| ERA5 | T, wind, pressure, precip (hourly, 0.25°) | CDS API (free, key required) | ✅ Ingested Jan 2024 |
| GFS | T, wind, pressure, precip (3-6h, 0.25°) | NOAA NOMADS (open) | ✅ Live forecast |
| CHIRPS | Daily precip (~5km) | UCSB HTTP (open) | ⏳ Client ready |
| Himawari-9 | Full-disk IR/VIS (10-min) | AWS Open Data (open) | ❌ Not started |
| BMKG stations | Ground obs | dataonline.bmkg.go.id | ❌ Not started |

## Agents & Skills

This project includes opencode AI configuration for specialized agents:

- **data-engineer** — weather data pipeline work
- **storm-cell-analyst** — satellite imagery & storm tracking
- **viz-builder** — Leaflet dashboard development

Load a skill explicitly when working on a specific domain:

- `era5-download` — CDS API details and variable reference
- `gfs-download` — NOMADS URL structure and GRIB2 pipeline
- `himawari-read` — Himawari-9 AWS bucket access and BT calculation
- `storm-cell-detect` — threshold detection, Kalman tracking

## Roadmap

1. **Phase 0** (done) — ERA5 + CHIRPS ingestion, DuckDB schema
2. **Phase 1** (in progress) — Himawari-9 storm cell detection & tracking
3. **Phase 2** — Regional downscaling model (GraphCast fine-tune)
4. **Phase 3** — API, alert engine, LLM narrative layer

See `BLUEPRINT.md` for the full technical plan.
