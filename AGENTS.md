# CUACADX — Agent Memory

## Objective
Build a regional weather intelligence engine for **whole Kalimantan**: **FourCastNet** (NVIDIA, earth2studio/physicsnemo, primary global model), Himawari-9 nowcasting, and a flood/inundation risk layer. Target clients: mining (ITMG), palm oil plantations, energy ops.

## Core Strategy
- **FourCastNet v1 AFNO** via earth2studio + physicsnemo (75M params, ~4s/step on M1, STABLE)
- **GFS initial condition**: Sequential download from NOMADS, cached to `data/fcn/<date>/<cycle>/ic.npy`
- **Deployment**: macOS dev + **tmux** for session management on headless VPS
- Defensible IP = fusion + downscaling + flood-translation layer, not the global model

## Region
**Kalimantan**: lat -4.5° to 4.5°, lon 108.5° to 119.5° (`KALIMANTAN_BBOX` in `config.py`)
Band 13 Himawari segments: S0510–S0610 (Kaltim) expanded as needed.

## Architecture
```
Stub IC (synthetic global atmosphere)    Himawari-9 (10-min, IR Band 13)
         │                                      │
         └──────────┬───────────────────────────┘
                    ▼
     FourCastNet AFNO (earth2studio, ~4s/step)
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
| FourCastNet (AFNO) | u10m, v10m, t2m, sp, msl, t850, u/v/z at 1000/850/500/250/50 hPa, r500, r850, tcwv, u/v100m | 0.25° | 6-hourly (auto-regressive to 168h) | Apache 2.0 |
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
- Model: `nvidia/fourcastnet1` from HuggingFace (`fcn.mdlus`, 287MB, Modulus format)
- Framework: earth2studio v0.16.0 + nvidia-physicsnemo v2.1.1 + PyTorch
- Input: 26 vars, [1,1,26,720,1440], 0.25° global grid (720×1440, south-pole exclusive)
- IC: Real GFS (NOMADS, sequential download, 1s-2s delay between requests), cached to `ic.npy`
- CRITICAL FIX: HGT from GFS is in gpm (meters), model expects specific geopotential (m²/s²) → multiply all z vars by 9.80665
- CRITICAL FIX: Input tensor must be float32 (model weights are float32; float64 causes silent dtype mismatch)
- Auto-regressive: 28 steps → 168h forecast (stable t2m in Kalimantan: 26-29°C throughout)
- Output: Cropped to Kalimantan bbox, saved as Parquet

### Flood risk (product IP)
1. **Threshold/rule-based** (ship v1): precip × DEM slope × TWI → risk 0-5
2. **+ CHIRPS historical percentiles** (v1.5): adaptive thresholds per location
3. **+ Himawari fusion** (v1.5): 0-6h high-res precip from optical flow
4. **+ River network + flow accumulation** (v2): pysheds/richdem hydrology
5. **+ ML flood classifier** (v3): XGBoost trained on historical flood data

## Work State
### Completed
- ERA5: 7 vars Jan 2024 (Kaltim), ingestion pipeline
- GFS: ingestion from NOAA NOMADS (stubbed in backend, not used by FCN)
- CHIRPS: client written (SSL fixed)
- Himawari-9: full pipeline — AWS HSD download, custom parser (BT via Planck), geolocation (pyproj), crop to bbox, Parquet storage
- Storm cell detection: BT < 233K + connected components (scipy.ndimage.label)
- Storm cell tracking: IoU bbox matching, velocity/heading computation
- Backend: FastAPI (ERA5/GFS/himawari9/FCN sources, `/cells` endpoint)
- Frontend: React/Vite/Leaflet — BT color scale, cell overlay, Legend, TimeSeriesChart
- `docs/IMPLEMENTATION_PLAN.md`, `docs/ENHANCEMENT_PLAN.md`
- FourCastNet model: loaded and verified (75M params, AFNO via earth2studio+physicsnemo)
- FCN inference pipeline: stub IC → 28-step auto-regressive → Kalimantan crop → Parquet
- FCN backend source: synthetic data replaced with real model (stub IC only)
- `run_fcn.py`: standalone forecast runner script
- **Phase 1 — Real GFS IC pipeline**: Sequential NOMADS download + caching, HGT gpm→m²/s² fix, float32 dtype fix
- **Phase 1 — Stable 28-step forecast**: Verified — t2m@eq stable at 27°C through all 168h, Kalimantan range 19-31°C
- **Phase 1 — Backend wired**: Real GFS→FCN cached forecast served by API

### Active
- None — awaiting next task

### Blocked
- BMKG station data — need API key / data request for ground truth

## Next Moves
1. Implement optical-flow nowcast for 0-6h Himawari fusion
2. Verification pipeline (FCN +6h vs GFS analysis)
3. SRTM DEM download + flow accumulation via pysheds
4. Rule-based flood risk engine (precip × DEM slope × TWI)

## Fresh Start on New Machine

Complete setup sequence from bare OS to running services (see `SKILLS.md` for full detail):

1. **System deps**: `python3.12`, `tmux`, `git`, `node` (macOS: brew; VPS: apt)
2. **Clone**: `git clone <repo> && cd cuacadx && python3.12 -m venv .venv && source .venv/bin/activate`
3. **Pip**: `pip install torch earth2studio nvidia-physicsnemo numpy pandas xarray cfgrib netCDF4 fastapi uvicorn pyarrow certifi pyproj scipy`
4. **Model**: Auto-downloads from HuggingFace on first FCN import (287MB → `models/fourcastnet/`)
5. **Frontend**: `cd frontend && npm install`
6. **First run**: `python run_fcn.py --steps 4` (downloads GFS, runs 24h forecast)
7. **Launch**: `tmux new-session -d -s cuacadx -n api \; send-keys 'cd /opt/cuacadx && source .venv/bin/activate && uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000' Enter \; new-window -t cuacadx -n frontend \; send-keys 'cd /opt/cuacadx/frontend && npm run dev -- --host 0.0.0.0' Enter`
8. **Verify**: `http://<ip>:5173/` dashboard, `http://<ip>:8000/docs` API
9. **tmux**: `tmux ls` to list, `tmux attach -t cuacadx` to enter

## Critical Fixes (Don't Forget)

- **HGT units**: GFS gives geopotential in gpm (meters). FourCastNet expects specific
  geopotential (m²/s²). All z vars (z1000, z850, z500, z250, z50) must be multiplied
  by 9.80665 at IC build time (`fourcastnet_pipeline.py`).
- **float32**: Model weights are float32. Input tensor must be `.float()`. float64
  causes silent corruption in AFNO convolutions.
- **GFS rate limiting**: NOMADS filter CGI returns HTTP 500 on parallel requests.
  Sequential downloads with 1-2s delay required.

## Relevant Files
- `ingestion/config.py` — bbox, variables, paths
- `ingestion/models/fourcastnet_pipeline.py` — stub IC → model → Parquet
- `ingestion/models/storm_cell.py` — detector + tracker
- `backend/data_service.py` — composite source registry (ERA5/GFS/FCN/Himawari)
- `backend/main.py` — FastAPI endpoints
- `frontend/src/` — React dashboard
- `run_fcn.py` — CLI forecast runner
- `docs/IMPLEMENTATION_PLAN.md` — build phases
- `docs/ENHANCEMENT_PLAN.md` — flood engine upgrade tiers
- `SKILLS.md` — tmux deployment guide

## Key Decisions
- **Primary model**: FourCastNet v1 AFNO via earth2studio+physicsnemo (75M params, ~4s/step on M1)
- **IC source**: Real GFS (NOMADS, sequential), cached to `ic.npy`
- **Deployment**: macOS dev + **tmux** for session management on headless VPS
- **BT formula**: radiance = count * abs(gain) + intercept, wavenumber = 10000 / cwl, Planck BT
- **Geolocation**: pyproj GEOS, CFAC=20466275 (2km), sat_alt_m = (distance − earth_eq_radius) * 1000
- **HSD parsing**: numpy structured dtypes (packed, no alignment), block 5 + IRCAL (c0/c1/c2)
- **Downsampling**: every 5th pixel in backend (~13k points/frame)
