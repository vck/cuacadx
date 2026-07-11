# CUACADX — Production Weather Intelligence Platform

## Product Vision

A **regional weather intelligence engine** for Kalimantan that delivers actionable forecasts to industrial operators — mining (ITMG), palm oil plantations, energy infrastructure — enabling **risk-aware decision-making** from 0 to 168 hours ahead.

**Core value proposition**: weather risk translated into operational cost/impact, not just numbers on a map.

---

## 1. Market & Use Cases

### Mining (contractor liability, equipment safety)
| Decision | Weather Input | Lead Time | Business Impact |
|---|---|---|---|
| Haul road passability | Precip intensity (0-6h) + soil moisture | 0-24h | Idle haulers: ~$5k/hr per fleet |
| Overburden/blast windows | Wind speed (10m, 100m), lightning risk | 0-72h | Missed blast = 1 shift lost |
| Pit dewatering planning | Precip accumulation (72-168h) | 72-168h | Sump capacity planning |
| Coal stockpile moisture | Precip + RH + surface temp | 0-48h | Reject moisture penalties |

### Plantation (harvest/logistics, fire prevention)
| Decision | Weather Input | Lead Time | Business Impact |
|---|---|---|---|
| Harvest scheduling | Precip probability (0-72h) | 0-72h | Wet FFB = lower CPO quality |
| Fertilizer application | Wind + precip-free window | 0-24h | Runoff loss: ~30% of applied NPK |
| Fire risk | Temp + RH + wind + drought index | 0-168h | Legal liability, satellite fire alerts |
| FFB transport | Road condition (precip × cumulative) | 0-48h | Logistics delays to mill |

### Energy (load forecasting, infrastructure protection)
| Decision | Weather Input | Lead Time | Business Impact |
|---|---|---|---|
| Load forecasting | Temp + humidity (cooling demand) | 0-168h | Peaker plant dispatch cost |
| Hydro generation | Catchment precip (accumulated) | 24-168h | Reservoir management |
| Transmission line | Wind gust + lightning risk | 0-24h | Line derating |
| Solar farm | Cloud cover (Himawari BT proxy) | 0-6h | Duck curve management |

---

## 2. Architecture

```
                    ┌─────────────────────────────────────┐
                    │         Data Ingestion Layer         │
                    │  Himawari-9  │  GFS  │  CHIRPS  │ DEM│
                    └──────┬──────┴──┬────┴────┬─────┴────┘
                           │         │         │
                    ┌──────▼─────────▼─────────▼──────────┐
                    │      Model Layer                    │
                    │  FourCastNet AFNO (6-168h)          │
                    │  Storm cell detection (0-6h)        │
                    │  Optical-flow precip (0-6h)         │
                    │  Flood risk engine                  │
                    └──────┬──────────────────────────────┘
                           │
                    ┌──────▼──────────────────────────────┐
                    │      Fusion Layer                   │
                    │  0-6h: Himawari-weighted nowcast    │
                    │  6-168h: FCN pure                   │
                    │  Both: DEM downscaling              │
                    └──────┬──────────────────────────────┘
                           │
                    ┌──────▼──────────────────────────────┐
                    │      Serving Layer                  │
                    │  DuckDB / Parquet → FastAPI → React │
                    └─────────────────────────────────────┘
```

### 2.1 Data Flow

```
GFS analysis (0.25°, f000, 26 vars)
        │
        ▼
  [STUBBED] → FourCastNet AFNO (28 steps, 6h each)
        │
        ▼
  Cropped to Kalimantan bbox (37×45 grid ≈ 1665 pts)
        │
        ▼
  Parquet: forecast.parquet (1.2M rows, ~64MB)
        │
        ▼
  FastAPI serves subset (frame, point, timeline) via DuckDB
```

---

## 3. Frontend Dashboard

### 3.1 MVP (Current)

**Stack**: React 18 + Vite + Leaflet + Recharts

**Current routes**:
| Route | Asset | Status |
|---|---|---|
| `/` | Map with source selector | Done |
| BT Band 13 color layer | Blue→red→white diverging | Done |
| Storm cell polygon overlay | Detected cells | Done |
| Legend | Dynamic per variable | Done |
| TimeSeriesChart | Point click → time series | Done |
| AnimControls | Basic playback | Done |

### 3.2 V1.0 Dashboard (Next)

**New elements:**

| Component | Description | Priority |
|---|---|---|
| **Source tab bar** | Horizontal tabs: Himawari / FCN / ERA5 / GFS | P0 |
| **Variable selector** | Dropdown within each source (BT, t2m, u10m, sp, etc.) | P0 |
| **Lead time slider** | 6-168h for FCN, uses timestamp for others | P0 |
| **Layer toggle** | Checkboxes: base map, BT raster, cell polygons, road overlay | P1 |
| **Point info popup** | Click lat/lon → show all variables at that point | P1 |
| **Alert panel** | Right sidebar: storm cells, heavy precip, flood risk | P1 |
| **Station overlay** | BMKG station markers (if data becomes available) | P2 |

**Dashboard layout:**
```
┌─────────────┬─────────────────────────────────┬──────────────┐
│  Left Panel │        Map (Leaflet)            │ Right Panel  │
│  ─────────  │                                 │  ──────────  │
│  Source Tab │  • Base layer (OSM/Dark)        │  Alerts      │
│  Variable   │  • Weather overlay              │  Storm cells │
│  Lead Time  │  • Cell polygons                │  Flood risk  │
│  Legend     │  • Click for point              │  Point info  │
│             │                                 │              │
├─────────────┴─────────────────────────────────┴──────────────┤
│                Bottom Panel: Time Series Chart                │
│     (Selected point: t2m, precip, wind by lead time)         │
└──────────────────────────────────────────────────────────────┘
```

### 3.3 Frontend API integration

```typescript
// Type definitions
interface FramePoint {
  lat: number;
  lon: number;
  v: number;
}

interface CellPolygon {
  lat: number;
  lon: number;
  bbox: [number, number, number, number];
  area_km2: number;
  motion: { u: number; v: number } | null;
}

interface TimeSeriesPoint {
  ts: string;
  v: number;
}

// API calls
GET  /api/sources                                    → Source[]
GET  /api/sources/{source}/variables                  → VariableInfo[]
GET  /api/sources/{source}/{var}/timestamps           → string[]
GET  /api/sources/{source}/{var}/frame?ts={ts}        → FramePoint[]
GET  /api/sources/himawari9/bt/cells?ts={ts}          → CellPolygon[]
GET  /api/sources/{source}/{var}/point?lat=&lon=      → TimeSeriesPoint[]
```

---

## 4. Backend APIs (Complete Spec)

### 4.1 Data Sources

| Source | Variables | Available | Times |
|---|---|---|---|
| `himawari9` | bt, bt_cells | Now | ~260/day (every 10 min) |
| `fcn` | 26 vars (u10m..t250) | Now (stub IC) | 28 lead times (6-168h) |
| `era5` | t2m, d2m, u10, v10, sp, msl, tp | Now | Jan 2024 hourly |
| `gfs` | t2m, d2m, u10, v10, sp, msl, tp | Now | 6h cycle, 0-48h |

### 4.2 Planned Endpoints

| Endpoint | Method | Purpose | Priority |
|---|---|---|---|
| `/api/flood/risk` | GET | Flood risk map for given lead time | P1 |
| `/api/flood/point` | GET | Flood risk at specific lat/lon | P1 |
| `/api/alerts` | GET | Active alerts (storm, heavy precip, flood) | P1 |
| `/api/forecast/summary` | GET | Text summary of key variables for ops | P2 |
| `/api/export/csv` | GET | Download point forecast as CSV | P2 |

### 4.3 Flood Risk Endpoint

```python
GET /api/flood/risk?ts=lead+6h&lat=-2.0&lon=115.0

Response:
{
  "risk_level": 0-5,
  "factors": {
    "precip_24h_mm": 78.5,
    "twi": 12.3,
    "slope_pct": 2.1,
    "soil_saturation_idx": 0.65
  },
  "recommendation": "Monitor - sustained precip expected"
}
```

---

## 5. Implementation Roadmap

### Phase 0: Foundation (Done)
- [x] FourCastNet model loaded (75M params, AFNO, ~4s/step)
- [x] Stub IC → 28-step forecast → Kalimantan crop → Parquet
- [x] Himawari-9 pipeline (HSD, BT, geolocation, 10-min data)
- [x] Storm cell detection + tracking
- [x] FastAPI backend with ERA5/GFS/Himawari/FCN sources
- [x] React Leaflet dashboard (BT layer, cells, legend, timeseries)

### Phase 1: Production Backend (Now → 2 weeks)

| Task | Effort | Dependencies |
|---|---|---|
| **FIX: FourCastNet divergence** — check residual vs direct prediction | 2d | Understanding model internals |
| **FIX: GFS IC download** — sequential retry, rate-limit aware | 1d | GFS server docs |
| **Real GFS → FCN tensor** — 26-var pipeline, no stub | 3d | GFS fix |
| **DuckDB integration** — replace pandas for frame loads | 2d | — |
| **Caching layer** — Redis or in-memory LRU for model outputs | 1d | — |
| **Background forecast worker** — separate process, schedule every 6h | 2d | GFS fix |
| **API rate limiting + auth** — API key per client | 1d | — |

### Phase 2: Dashboard V1 (Week 3-4)

| Task | Effort | Dependencies |
|---|---|---|
| Source tab bar + variable dropdown | 2d | Phase 1 API |
| Lead time slider for FCN | 1d | Phase 1 API |
| Point info popup on map click | 2d | Phase 1 API |
| Right sidebar: alerts panel | 3d | Storm cell API |
| Time series chart (all vars) | 2d | — |
| Dark mode map (CartoDB dark) | 0.5d | — |
| AnimControls: play/pause/loop for lead times | 1d | — |

### Phase 3: Flood Risk Engine (Week 5-6)

| Task | Effort | Dependencies |
|---|---|---|
| **DEM download** — SRTM 30m for Kalimantan via OpenTopography | 1d | |
| **Flow accumulation + TWI** via pysheds | 3d | DEM |
| **Rule-based flood risk** (precip × slope × TWI → risk 0-5) | 2d | TWI, FCN precip |
| **Flood risk API endpoint** | 1d | Rule engine |
| **Flood layer on map** | 2d | Flood API |
| **CHIRPS percentiles** — adaptive thresholds per location | 2d | CHIRPS client |

### Phase 4: Nowcast + Fusion (Week 7-8)

| Task | Effort | Dependencies |
|---|---|---|
| **Optical-flow rainfall advection** (Farneback/LucKanade) | 4d | Himawari pipeline |
| **0-6h nowcast from Himawari** | 2d | Optical flow |
| **Himawari + FCN fusion** — seamless transition at 6h | 3d | Nowcast + FCN |
| **Downscaling** — statistical (DEM-aware, bilinear) | 2d | DEM |
| **Verification** — compare FCN outputs vs ERA5 reanalysis | 3d | FCN pipeline |

### Phase 5: Business Layer (Week 9-10)

| Task | Effort | Dependencies |
|---|---|---|
| **Alert rules engine** — configurable thresholds per client | 3d | All data pipelines |
| **Export endpoints** — CSV, PDF report, image snapshot | 2d | Dashboard |
| **Client dashboard** — per-company view (multi-tenant) | 4d | Auth |
| **Webhook alerts** — Telegram, Email, SMS gateway | 2d | Alert engine |
| **Historical analytics** — verify forecast skill vs ERA5/GFS | 3d | — |

### Phase 6: Scale & Optimize (Ongoing)

| Task | Effort | Dependencies |
|---|---|---|
| Auto-regressive instability investigation | 3d | Model internals |
| ONNX export from Modulus (faster CPU inference) | 3d | physicsnemo |
| Termux deployment testing | 2d | Phase 5 |
| Multi-model ensemble (FCN + Pangu) | 5d | — |
| ML flood classifier (XGBoost) | 5d | Historical flood data |

---

## 6. Business Model

### 6.1 Target Segments

| Segment | Players | Pain Point | Willingness to Pay |
|---|---|---|---|
| **Coal mining** | ITMG, ADRO, BUMI, PTBA | Rain downtime planning | High (lost revenue $k/hr) |
| **Palm oil** | AALI, LSIP, SIMP, SMAR | Harvest/logistics windows | Medium |
| **Energy** | PLN, geothermal operators | Load forecast, transmission | Medium-High |
| **Govt/Disaster** | BNPB, BMKG | Early warning | Low (budget constrained) |

### 6.2 Pricing Tiers

| Tier | Price | Features |
|---|---|---|
| **Basic** | $199/mo | 48h forecast, 3 vars (t2m, precip, wind), email alerts |
| **Pro** | $499/mo | 168h forecast, all vars, storm cells, flood risk, API |
| **Enterprise** | $1,999/mo | White-label dashboard, custom thresholds, SLA, on-prem deploy |

### 6.3 Key Metrics for Success

| Metric | Target | How |
|---|---|---|
| Forecast accuracy (t2m) | RMSE < 2.5°C at 24h | Compare with BMKG obs |
| Storm cell detection | Precision > 0.7, Recall > 0.6 | Verify against Himawari RGB |
| API uptime | 99.5% | Background worker + health checks |
| Dashboard TTFB | < 2s (cold), < 500ms (cached) | DuckDB + LRU cache |
| Cold forecast latency | < 10 min (download + model) | Async worker pool |

---

## 7. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Global model** | FourCastNet v1 AFNO | 75M params, CPU-native, Apache 2.0 |
| **Framework** | earth2studio + nvidia-physicsnemo | NVIDIA ecosystem, Modulus support |
| **IC source** | GFS analysis (0.25°, NOMADS) | Free, real-time, 26 vars |
| **Satellite** | Himawari-9 HSD (AWS) | 10-min IR, free, 2km resolution |
| **Reanalysis** | ERA5 (CDS) | Historical verification (5-day delay) |
| **Storage** | Parquet + DuckDB | Columnar, fast slices, single file |
| **API** | FastAPI + uvicorn | Python-native, async, auto-docs |
| **Frontend** | React 18 + Vite + Leaflet + Recharts | Lightweight, map-centric |
| **Deployment** | Hetzner CX32 (4 vCPU, 8GB) | $7/mo, or Oracle Free Tier |
| **Field** | Termux (Android) | Offline-capable, ARM64 |

---

## 8. Risk Matrix

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| FourCastNet divergence unsolvable (step 2+ blows up) | Medium | High | Residual-vs-direct investigation; fallback to Pangu; skip auto-regression, use 1-step nowcast only |
| GFS NOMADS rate limiting | High | Medium | Sequential retry, fallback to GDAS or S3 mirror |
| Himawari AWS bandwidth (mobile data) | Medium | Low | Optimistic caching, user-configurable resolution |
| Competitor launches similar product | Low | Medium | Focus on Kalimantan-specific flood risk (hard to replicate) |
| Client churn after trial | Medium | Medium | Prove forecast skill with 1-month ERA5 verification |

---

## 9. Success Criteria for MVP

1. **Functional**: All 26 FCN variables served via API, cropped to Kalimantan
2. **Stable**: Model runs through 28 steps without divergence
3. **Fast**: Full forecast in < 5 min, frame API in < 200ms
4. **Visual**: Dashboard shows BT + FCN overlays with lead time slider
5. **Business**: At least 1 pilot client using dashboard for daily decisions
