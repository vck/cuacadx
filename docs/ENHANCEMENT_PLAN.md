# CUACADX — Flood Prediction Engine Enhancement Plan

## Current (v1 — Rule-based)
```
for each point (lat, lon, ts):
    precip_24h = FourCastNet total_precipitation
    slope, twi = DEM lookup
    risk_score = f(precip_24h, slope, twi) → 0-5
```

---

## Tier 1 — Quick Wins (1-2 days each)

### 1. Himawari-9 rainfall rate → 0-6h fusion

**Why**: FourCastNet is 28km. Himawari is 2km. Fusing optical-flow rainfall advection for 0-6h gives 10× higher resolution where it counts — short-fuse flash flood risk.

**How**: Classical optical flow on BT frames → rainfall rate estimate → weighted blend with FourCastNet (100% Himawari at t=0, linear to 100% FourCastNet at t+6h).

### 2. CHIRPS historical climatology for adaptive thresholds

**Why**: "100mm in 24h" means different flood risk in different catchments. CHIRPS has 30+ years of daily data at 5km. Per-pixel percentile thresholds adapt risk to local climate.

**How**: Load CHIRPS historical stack → compute percentiles (50th, 75th, 90th, 95th, 99th) per grid cell → store as lookup table. Flood risk = where does the forecast fall on this location's historical distribution.

### 3. BMKG station bias correction

**Why**: FourCastNet has systematic precip bias in the tropics. Even 5-10 BMKG stations can provide per-station correction factors.

**How**: Compare FourCastNet precip at station locations vs observed → compute bias ratio → interpolate bias field across Kalimantan.

---

## Tier 2 — Medium (3-5 days)

### 4. Full river network + flow accumulation (pysheds / richdem)

**Why**: The biggest physics improvement. Instead of point-based scoring, model actual hydrological flow — water flows downhill and accumulates. A plantation at the bottom of a 100km² catchment floods much worse than one on a ridge.

**How**:
```
SRTM DEM → pysheds:
  fill_pits → fill_depressions → resolve_flats
  → flow_direction → flow_accumulation
  → extract_river_network
  → compute_hand (Height Above Nearest Drainage)
```
River network + HAND gives: which cells are in a floodplain, how connected, and how much upstream area drains through them.

**CPU cost**: pysheds processes 36M cells in under 30s — trivial on our machine.

### 5. Soil + land cover data for runoff ratio

**Why**: Same rainfall on forest vs palm oil vs bare soil produces 2-5× different runoff.

**How**: Static lookup: FAO SoilGrids (250m) → soil type → infiltration rate. ESA CCI → land cover → runoff coefficient. Combined with slope → actual runoff ratio per grid cell. Precip × runoff_ratio = effective water for flooding.

### 6. Time-to-flood estimate

**Why**: "Flood risk level 4" is less actionable than "flooding expected in 2 hours."

**How**: Given current rain rate + forecast, compute hours until precip accumulation threshold is breached. Simple linear extrapolation for v1, FourCastNet trend for v2.

---

## Tier 3 — Advanced (1-2 weeks)

### 7. Simplified 2D hydraulic model (LISFLOOD-FP style)

**Why**: For critical catchments (haul roads, tailings dams), a full hydrodynamic model gives actual flood extent, depth, and velocity — not just a risk score.

**How**: Diffusive wave approximation on DEM → flood wave propagation across terrain → flood depth per grid cell. Run only for high-risk catchments.

**CPU cost**: LISFLOOD-FP runs 4-8× real-time on a single CPU core.

### 8. ML flood classifier (Random Forest / XGBoost)

**Why**: Once historical flood data exists, a model captures non-linear interactions rule-based systems miss.

**Features**: precip_accum (6/12/24/48/72h), flow_accumulation, HAND, soil_infiltration, land_cover_runoff, slope, precip_percentile, season

**Target**: binary flood/no-flood or risk level 0-5

**Compute**: XGBoost inference is microseconds per point on CPU.

---

## Recommended Upgrade Path

```
v1 (now)    Rule-based: precip × slope × TWI → risk 0-5
               │
               ▼
v1.5 (week 2)  + CHIRPS percentile thresholds
               + Himawari-9 fusion (0-6h high-res)
               + BMKG bias correction
               ── biggest accuracy jump for least effort ──
               │
               ▼
v2 (week 3-4)  + pysheds river network + flow accumulation
               + Soil/land cover runoff ratio
               + Time-to-flood estimate
               ── now it's a real hydrological model ──
               │
               ▼
v3 (month 2)   + XGBoost flood classifier
               + LISFLOOD-FP for critical catchments
               + Probabilistic (ensemble-based) risk
```

## Data Sources Needed

| Data | Purpose | Source | Size | License |
|---|---|---|---|---|
| SRTM 30m | Elevation, slope, flow | USGS/OpenTopography | ~50MB | Free |
| FAO SoilGrids (250m) | Soil type, infiltration | ISRIC | ~100MB | CC-BY |
| ESA CCI Land Cover | Runoff coefficient | ESA | ~50MB | Free |
| CHIRPS (30yr daily) | Historical precip percentiles | CHIRPS (client exists) | ~500MB | Free |
| BMKG stations | Bias correction ground truth | dataonline.bmkg.go.id | — | Free (need key) |
| BNPB flood records | Training data for ML | BNPB/BPBD | — | Need request |
