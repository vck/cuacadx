# CUACADX — Agent Memory

## Objective
Build a regional weather intelligence engine for **whole Kalimantan**: ECMWF AIFS (primary global model), Himawari-9 nowcasting, and a flood/inundation risk layer. Target clients: mining (ITMG), palm oil plantations, energy ops.

## Core Strategy
- **Do NOT run a frontier weather model** — consume ECMWF AIFS precomputed open data (CC-BY-4.0, free, no GPU)
- **Pangu-Weather** as CPU/cheap-GPU fallback/QA (ONNX, `inference_cpu.py`)
- Defensible IP = fusion + downscaling + flood-translation layer, not the global model
- Infra: CPU-only VM for MVP ($20–50/mo), occasional GPU rental for benchmarking only

## Region
**Kalimantan**: lat -4.5° to 4.5°, lon 108.5° to 119.5° (`KALIMANTAN_BBOX` in `config.py`)
Band 13 Himawari segments: S0510–S0610 (Kaltim) expanded as needed.

## Architecture
```
AIFS (ECMWF, 0.25°, 4x daily, CC-BY-4.0)    Himawari-9 (10-min, IR Band 13)
         │                                              │
         └──────────┬───────────────────────────────────┘
                    ▼
            Fusion Layer (0–6h → Himawari weighted, 6h+ → AIFS)
                    ▼
            Downscaling (DEM-aware, statistical/lightweight ML)
                    ▼
            Flood/Inundation Model (rule-based → hydrological → ML)
                    ▼
            DuckDB/Parquet + FastAPI + Dashboard + Alerting
```

## Data Layers
| Source | Variables | Res | Freq | License |
|---|---|---|---|---|
| ECMWF AIFS | t2m, d2m, u10, v10, sp, msl, tp | 0.25° | 4x daily | CC-BY-4.0 |
| Himawari-9 | BT Band 13 (rainfall proxy) | 2km | 10 min | Free (AWS) |
| CHIRPS | precip | 5km | daily | Free |
| DEM | elevation (SRTM/Copernicus) | 30m | static | Free |
| BMKG | station obs | point | hourly | Free |

## Modelling Pipeline
### 0–6h nowcast (Himawari)
- Storm cell detection: BT < 233K threshold + connected components (done)
- Storm cell tracking: IoU matching + motion vectors (done)
- Optical-flow rainfall advection (classical CV, no DL) — **NEXT**
- ConvLSTM v2 upgrade (if local rain gauge ground truth available)

### 6h+ forecast (AIFS)
- Consume precomputed AIFS from ECMWF open data (GRIB2 → Parquet)
- Crop to Kalimantan bbox, regrid to common resolution
- Store partitioned by date+variable in DuckDB

### Flood risk (product IP)
1. **Threshold/rule-based** (ship v1): rainfall accumulation over N hours vs catchment threshold
2. **Simplified hydrological model** (v2): LISFLOOD-FP-style diffusive wave
3. **ML flood classifier** (2027): train on historical flood data from BNPB/BMKG/clients

## Work State
### Completed
- ERA5: 7 vars Jan 2024 (Kaltim), ingestion pipeline
- GFS: ingestion from NOAA NOMADS, forecast +0–+48h
- CHIRPS: client written (SSL fixed)
- Himawari-9: full pipeline — AWS HSD download, custom parser (BT via Planck), geolocation (pyproj), crop to bbox, Parquet storage
- Storm cell detection: threshold + connected components (BT < 233K, 0.05° raster), scipy.ndimage.label
- Storm cell tracking: IoU bbox matching, velocity/heading computation
- Backend: FastAPI (AIFS/GFS/ERA5/himawari9 sources, `/cells` endpoint)
- Frontend: React/Vite/Leaflet — BT color scale, cell polygon overlay, Legend, TimeSeriesChart
- Branch `blueprint-v2`: strategic pivot to AIFS + Kalimantan + flood risk

### Active
- AIFS ingestion client — needs building (GRIB2 reader, ECMWF open data API)
- Kalimantan-wide data: expand ERA5/GFS/Himawari to whole Kalimantan bbox
- Flood/scoring model: rule-based v1

### Blocked
- BMKG station data — need API key / data request for ground truth

## Next Moves
1. Build AIFS ingestion client: fetch GRIB2 from ECMWF open data → regrid → Parquet
2. Expand Himawari-9 coverage to whole Kalimantan (more HSD segments)
3. Implement rule-based flood risk scoring
4. Integrate DEM (SRTM) for terrain-aware downscaling
5. Update frontend: Kalimantan map focus, flood overlay

## Relevant Files
- `ingestion/config.py` — bbox, variables, paths (single source of truth)
- `ingestion/sources/himawari_client.py` — HSD parser → BT → Parquet
- `ingestion/models/storm_cell.py` — detector + tracker
- `backend/data_service.py` — composite source registry
- `backend/main.py` — FastAPI endpoints
- `frontend/src/` — React dashboard

## Key Decisions
- **Primary global model**: ECMWF AIFS (precomputed, CC-BY-4.0, zero inference infra)
- **Fallback**: Pangu-Weather (ONNX, CPU inference via `inference_cpu.py`)
- **Do NOT use**: GraphCast (license unclear), GenCast (300GB RAM), GFS (lower skill)
- **BT formula**: radiance = count * abs(gain) + intercept, wavenumber = 10000 / cwl, Planck BT
- **Geolocation**: pyproj GEOS, CFAC=20466275 (2km), sat_alt_m = (distance − earth_eq_radius) * 1000
- **HSD parsing**: numpy structured dtypes (packed, no alignment), block 5 + IRCAL (c0/c1/c2)
- **Downsampling**: every 5th pixel in backend (~13k points/frame)
