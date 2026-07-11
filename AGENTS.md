# CUACADX — Agent Memory

## Objective
Build a regional weather intelligence engine for **whole Kalimantan**: **FourCastNet** (NVIDIA, ONNX, primary global model), Himawari-9 nowcasting, and a flood/inundation risk layer. Target clients: mining (ITMG), palm oil plantations, energy ops.

## Core Strategy
- **Run FourCastNet v1 ONNX locally** (~50MB, CPU-native, 1-3s/step on M1)
- **Pangu-Weather** as CPU fallback/QA (ONNX, `inference_cpu.py`)
- Defensible IP = fusion + downscaling + flood-translation layer, not the global model
- Infra: CPU-only VM for MVP ($5–20/mo), occasional GPU rental for benchmarking only

## Region
**Kalimantan**: lat -4.5° to 4.5°, lon 108.5° to 119.5° (`KALIMANTAN_BBOX` in `config.py`)
Band 13 Himawari segments: S0510–S0610 (Kaltim) expanded as needed.

## Architecture
```
GFS Analysis (0.25°, 4x/d)          Himawari-9 (10-min, IR Band 13)
         │                                      │
         └──────────┬───────────────────────────┘
                    ▼
        FourCastNet ONNX (1-3s/step, CPU)
        6h → 12h → ... → 168h auto-regressive
                    │
                    ▼
            Fusion Layer (0–6h → Himawari weighted, 6h+ → FourCastNet)
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
| FourCastNet (ONNX) | t2m, d2m, u10, v10, sp, msl, tp, tcwv, ... | 0.25° | 6-hourly (auto-regressive to 168h) | NVIDIA NGC |
| Himawari-9 | BT Band 13 (rainfall proxy) | 2km | 10 min | Free (AWS) |
| CHIRPS | precip | 5km | daily | Free |
| DEM | elevation (SRTM/Copernicus) | 30m | static | Free |
| BMKG | station obs | point | hourly | Free |

## Modelling Pipeline
### 0–6h nowcast (Himawari)
- Storm cell detection: BT < 233K threshold + connected components (done)
- Storm cell tracking: IoU matching + motion vectors (done)
- Optical-flow rainfall advection (classical CV, no DL) — **NEXT**
- Fuse with FourCastNet precip for seamless transition

### 6h+ forecast (FourCastNet)
- Download FourCastNet v1 ONNX weights (~50MB)
- Build GFS analysis → model input tensor pipeline
- Run auto-regressive inference (6h steps → 168h)
- Crop to Kalimantan bbox, save as Parquet

### Flood risk (product IP)
1. **Threshold/rule-based** (ship v1): precip × DEM slope × TWI → risk 0-5
2. **+ CHIRPS historical percentiles** (v1.5): adaptive thresholds per location
3. **+ Himawari fusion** (v1.5): 0-6h high-res precip from optical flow
4. **+ River network + flow accumulation** (v2): pysheds/richdem hydrology
5. **+ ML flood classifier** (v3): XGBoost trained on historical flood data

## Work State
### Completed
- ERA5: 7 vars Jan 2024 (Kaltim), ingestion pipeline
- GFS: ingestion from NOAA NOMADS, forecast +0–+48h
- CHIRPS: client written (SSL fixed)
- Himawari-9: full pipeline — AWS HSD download, custom parser (BT via Planck), geolocation (pyproj), crop to bbox, Parquet storage
- Storm cell detection: threshold + connected components (BT < 233K, 0.05° raster), scipy.ndimage.label
- Storm cell tracking: IoU bbox matching, velocity/heading computation
- Backend: FastAPI (GFS/ERA5/himawari9 sources, `/cells` endpoint)
- Frontend: React/Vite/Leaflet — BT color scale, cell polygon overlay, Legend, TimeSeriesChart
- Branch `blueprint-v2`: strategic pivot to FourCastNet + Kalimantan + flood risk
- Plans: `docs/IMPLEMENTATION_PLAN.md`, `docs/ENHANCEMENT_PLAN.md`

### Active
- **Phase 0: FourCastNet model setup** — download ONNX weights, install onnxruntime, verify inference
- Kalimantan-wide data: expand ERA5/GFS/Himawari to whole Kalimantan bbox

### Blocked
- BMKG station data — need API key / data request for ground truth
- FourCastNet input data pipeline — needs GFS analysis → model tensor conversion

## Next Moves
1. **Phase 0**: Install onnxruntime-silicon, download FourCastNet v1 ONNX, verify single-step inference
2. **Phase 1**: Build GFS → FourCastNet input tensor pipeline (20 var, 721×1440 grid)
3. **Phase 2**: Run full auto-regressive forecast loop, crop to Kalimantan, save Parquet
4. **Phase 3**: Download SRTM DEM, compute flow accumulation + TWI via pysheds
5. **Phase 4**: Build rule-based flood risk engine, wire into backend
6. **Phase 5**: Flood risk overlay on frontend

## Relevant Files
- `ingestion/config.py` — bbox, variables, paths (single source of truth)
- `ingestion/sources/himawari_client.py` — HSD parser → BT → Parquet
- `ingestion/models/storm_cell.py` — detector + tracker
- `backend/data_service.py` — composite source registry
- `backend/main.py` — FastAPI endpoints
- `frontend/src/` — React dashboard
- `docs/IMPLEMENTATION_PLAN.md` — FourCastNet + flood risk build plan
- `docs/ENHANCEMENT_PLAN.md` — flood engine upgrade path

## Key Decisions
- **Primary global model**: FourCastNet v1 ONNX (~50MB, CPU-native)
- **Fallback**: Pangu-Weather (ONNX, CPU inference via `inference_cpu.py`)
- **Do NOT use**: GraphCast (license unclear), GenCast (300GB RAM), AIFS (ECMWF open data connectivity issues)
- **BT formula**: radiance = count * abs(gain) + intercept, wavenumber = 10000 / cwl, Planck BT
- **Geolocation**: pyproj GEOS, CFAC=20466275 (2km), sat_alt_m = (distance − earth_eq_radius) * 1000
- **HSD parsing**: numpy structured dtypes (packed, no alignment), block 5 + IRCAL (c0/c1/c2)
- **Downsampling**: every 5th pixel in backend (~13k points/frame)
