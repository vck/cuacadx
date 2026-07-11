# CUACADX — Implementation Plan: FourCastNet + Flood Risk Engine

## Objective
Build a regional weather intelligence engine for whole **Kalimantan** using NVIDIA **FourCastNet** as the global weather model, **Himawari-9** for nowcasting (0-6h), and a **rule-based flood risk layer** as the product IP.

Infra: **CPU-only M1 Mac** for development, **$5-20/mo VPS** for deployment. No GPU needed.

---

## 1. Model Choice: FourCastNet v1 (AFNO)

| Variant | Size | Format | CPU on M1 | Precip? | How to get |
|---|---|---|---|---|---|
| **✓ FourCastNet v1 (AFNO)** | ~50MB | ONNX | ✅ Fast, 1-3s/step | Separate model, derived from TCWV/RH | `ai-models-fourcastnet` or NGC direct |
| FourCastNet v2 (SFNO) small | 2.93GB | PyTorch | ⚠️ Heavy | 73 vars, includes tp directly | NGC `modulus_fcnv2_sm` |
| FourCastNet 3 | Container | NIM | ❌ GPU-only | Ensemble probabilistic | NGC container |
| FourCastNeXt | ~50MB | PyTorch | ⚠️ Needs PyTorch | 20 vars (RH + TCWV) | GitHub `nci/FourCastNeXt` |

**Winner: FourCastNet v1 ONNX** — smallest download, CPU-native, fastest path to running on this machine.

---

## 2. Architecture

```
┌──────────────────────────────┐     ┌───────────────────────────────┐
│  GFS Analysis (0.25°, 4x/d)  │     │  Himawari-9 (10-min, IR B13)   │
│  → regrid to 20-var tensor   │     │  → rainfall-rate retrieval      │
└──────────────┬───────────────┘     └──────────────┬────────────────┘
               │                                     │
               ▼                                     ▼
       ┌─────────────────────────────────────────────────────┐
       │  FourCastNet ONNX Inference (1-3s/step, M1 CPU)      │
       │  6h → 12h → 18h → ... → 168h (auto-regressive)       │
       │  Output: 20 vars, 0.25° global, cropped to Kalimantan │
       └──────────────────────┬────────────────────────────────┘
                              ▼
       ┌─────────────────────────────────────────────────────┐
       │  Precip Accumulation + DEM (SRTM 30m) → Flood Risk   │
       │  Rule-based scoring: precip_24h × terrain_wetness     │
       └──────────────────────┬────────────────────────────────┘
                              ▼
       ┌─────────────────────────────────────────────────────┐
       │  Parquet Store + FastAPI + React Dashboard             │
       │  + Flood risk overlay + point query API               │
       └─────────────────────────────────────────────────────┘
```

---

## 3. Phased Implementation

### Phase 0 — Model & Dependencies (1 day)
```
- pip install onnxruntime-silicon (M1/Apple Silicon optimized)
- Download FourCastNet v1 ONNX weights (~50MB)
  → via `pip install ai-models-fourcastnet` (auto-downloads)
  → OR download ONNX directly from NGC/ECMWF
- Verify single inference step works with sample input
- Benchmark: time per 6h step on M1
```

### Phase 1 — Input Data Pipeline (2 days)
```
GFS analysis → FourCastNet input tensor (1, 20, 721, 1440)

Variables needed (20):
  Surface:  u10, v10, t2m, sp, msl, tcwv  (6)
  Upper:    u, v, z, t, q  at 13 levels    (14)

Pipeline:
  1. Fetch latest GFS analysis (we have gfs_client.py)
  2. Remap GFS native grid → 0.25° regular lat/lon
  3. Interpolate missing pressure levels if needed
  4. Normalize using ERA5 stats (mean/std per variable)
  5. Stack into (1, 20, 721, 1440) numpy array → .npy file

Alternative shortcut:
  - Use ECMWF ai-models framework (if connectivity issues resolved)
  - Or copy ai-models' input preparation code for local use
```

### Phase 2 — Inference & Output (1 day)
```
Auto-regressive loop:
  input = initial_analysis.npy
  for lead in [6, 12, 18, 24, 36, 48, 72, 96, 120, 144, 168]:
      output = fourcastnet_model.run(input)
      save output cropped to Kalimantan bbox → Parquet
      input = output  # feed back for next step

Output storage:
  /data/fourcastnet/{YYYYMMDD}/{HH}/{lead}h/{var}.parquet
  - schema: lat, lon, value, ts, lead_hour, variable
  - same pattern as existing GFS/ERA5 data

Variables to extract (prioritize for flood):
  tp (total precip) — if available
  tcwv (total column water vapor) — moisture proxy
  t2m, u10, v10, msl, sp — for context
```

### Phase 3 — DEM & Terrain (1 day)
```
1. Download SRTM 30m tiles covering Kalimantan bbox
   → ~12 tiles (1°×1° each), ~50MB total
   → Source: USGS EarthExplorer or OpenTopography

2. Build elevation lookup at 0.005° (~500m) grid:
   - Elevation (m)
   - Slope (degrees)
   - Terrain Wetness Index = ln(flow_accum / tan(slope))
   - Flow direction / accumulation (using pysheds or richdem)

3. Store as Parquet: /data/static/dem.parquet
   - schema: lat, lon, elevation_m, slope_deg, twi
```

### Phase 4 — Flood Risk Engine (2 days)
```
Rule-based v1 — no ML, no GPU.

For any point (lat, lon, timestamp):
  1. Fetch FourCastNet precip accumulation for 6h, 12h, 24h windows
  2. Fetch DEM data: elevation, slope, TWI
  3. Compute risk factors:
     - precip_score = precip_24h / threshold (e.g. 100mm)
     - terrain_score = 1 - min(slope / 5°, 1)  # flat = risky
     - wetness_score = min(TWI / 15, 1)  # higher TWI = wetter
  4. Aggregate: risk_score = (precip_score × 0.5
                              + terrain_score × 0.3
                              + wetness_score × 0.2) × 5
     Clamp to 0-5 scale.

Risk levels:
  0 (none):      < 30mm/24h + good drainage
  1 (low):       30-60mm + moderate
  2 (moderate):  60-100mm + moderate
  3 (high):      60-100mm + flat
  4 (very high): 100-150mm + flat/poor drainage
  5 (extreme):   > 150mm + flat/poor drainage

Storage: DuckDB table `flood_risk`
  (ts, lat, lon, precip_6h, precip_12h, precip_24h,
   elevation_m, slope_deg, risk_score, risk_label)
```

### Phase 5 — Backend Integration (2 days)
```
New source: "fourcastnet" in backend/data_service.py
  - /api/sources → includes fourcastnet
  - /api/sources/fourcastnet/variables → tp, t2m, u10, v10, msl, sp
  - /api/sources/fourcastnet/{var}/timestamps → forecast cycles
  - /api/sources/fourcastnet/{var}/frame → grid data
  - /api/sources/fourcastnet/{var}/point → point time series

New endpoints:
  - POST /api/flood/risk
      Body: { "lat": ..., "lon": ..., "cycle_ts": "..." }
      Response: { "risk_score": 3, "risk_label": "high",
                  "precip_24h": 85.2, "elevation_m": 42,
                  "contributing_factors": { ... } }

  - GET /api/flood/map?ts=...&source=fourcastnet
      Response: { "grid": [{lat, lon, risk_score}, ...] }
```

### Phase 6 — Frontend (2 days)
```
1. Add fourcastnet as a selectable source in ControlPanel
2. Variables: tp (precip), t2m, u10, v10, msl, sp
3. Flood risk overlay:
   - When flood risk endpoint is active, overlay risk heatmap
   - Color scale: green(0) → yellow(2) → orange(3) → red(5)
   - Semi-transparent polygons covering risk zones
4. Point click on risk map shows contributing factors tooltip
5. Legend shows risk scale + current source variable
```

---

## 4. Timeline Summary

| Phase | Days | Deliverable |
|---|---|---|
| 0 — Model setup | 1 | FourCastNet ONNX running on M1 |
| 1 — Input pipeline | 2 | GFS→model input conversion works |
| 2 — Inference loop | 1 | Forecast Parquet files generated |
| 3 — DEM import | 1 | Elevation + wetness index for Kalimantan |
| 4 — Flood engine | 2 | Risk scores for any lat/lon |
| 5 — Backend API | 2 | `/api/flood/risk` endpoint live |
| 6 — Frontend | 2 | Flood overlay on map |
| **Total** | **~11 days** | |

---

## 5. Infrastructure (VPS)

| Tier | Provider | Spec | Cost/mo | Use |
|---|---|---|---|---|
| MVP | Hetzner CX22 | 2 vCPU, 4GB RAM, 40GB SSD | ~€4.49 (~$5) | Daily inference + API |
| With storage | + Backblaze B2 | S3-compatible, 10GB | ~$0.50 | Historical Parquet archive |
| Total | | | **~$5.50/mo** | |

No GPU needed. $20/mo is generous — leftover can fund occasional GPU spot rental for benchmarking.

---

## 6. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| ECMWF open data connectivity issues | Medium | Fall back to GFS analysis (already working) |
| FourCastNet precip quality on tropics | Medium | v1: use GFS precip directly, FourCastNet for context. Calibrate with CHIRPS. |
| SRTM DEM download size | Low | ~50MB for Kalimantan tiles |
| ONNX model ops not supported on M1 | Low | onnxruntime-silicon covers ARM NEON ops |
| Inference speed too slow for batch | Low | 1-3s/step × 28 steps = ~1 min per cycle, fine |
