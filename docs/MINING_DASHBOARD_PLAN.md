# Mining Ops Weather Intelligence Dashboard — Design Plan

## Target Users & Their Needs

| Role | Primary Need | Decision |
|---|---|---|
| **Site Manager** | At-a-glance ops status | Go/no-go for shifts, maintenance windows |
| **Dispatcher** | Real-time conditions + 24h trend | Haul truck routing, road closures |
| **Safety Officer** | Threshold alerts (lightning, wind, rain) | Work stoppage, evacuation, blast delay |
| **Environmental Officer** | Cumulative precip, dust conditions | Compliance reporting, water mgmt |

## Key Weather Threats for Kalimantan Mining

| Threat | Impact | Threshold |
|---|---|---|
| Heavy rain | Haul road flooding, pit water, slope instability | >50mm/day, >20mm/h |
| Strong wind | Dust control failure, crane/conveyor halt | >30km/h sustained |
| Lightning | Work stoppage, blast delay | Within 15km of site |
| Extreme heat | Equipment cooling, worker fatigue | >36°C |
| Low visibility | Haul truck collision risk | <1km (BT proxy via Himawari) |

## Proposed Layout

```
┌────────────────────────────────────────────────────────────────────┐
│  ▲ Header: Logo · CUACADX | Site: Bengalon ▼ | 28°C · 12km/h · 🌧️ │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ╔═══ Operational Status ─────────────────────────────────────╗    │
│  ║  🌧️ Rain  10mm/24h 🟢    💨 Wind  12km/h 🟢               ║    │
│  ║  🌡️ Temp  28°C 🟢        ⚡ Lightning  NONE 🟢             ║    │
│  ║  ☁️ Cloud  Scattered 🟢   👁️ Visibility  8km 🟢            ║    │
│  ╚════════════════════════════════════════════════════════════╝    │
│                                                                    │
│  ┌─────────────────────────────────────┬─────────────────────────┐ │
│  │                                     │   7-Day Forecast        │ │
│  │         MAP VIEW                    │   ┌───┬───┬───┬───┬──┐ │ │
│  │   Rain overlay (Himawari/FCN)       │   │☔  │☔  │⛅ │☀️ │☔ │ │ │
│  │   Storm cells (lightning proxy)     │   │28° │26° │30° │31°│27°│ │
│  │   Wind quiver (FCN)                 │   │45mm│60mm│5mm │0mm│30mm│ │
│  │   Pit boundaries                    │   │ 🔴 │🔴 │ 🟢 │🟢 │🟡 │ │
│  │   Click for 168h point forecast     │   └───┴───┴───┴───┴──┘ │ │
│  │                                     │                         │ │
│  │   Layer toggles:                    │   → Detailed 168h chart │ │
│  │   ☑ Rain  ☑ Cells  ☑ Wind  ☑ Sites │   (t2m, precip, wind)   │ │
│  └─────────────────────────────────────┴─────────────────────────┘ │
│                                                                    │
│  ┌─── Alerts ───────────────────────────────────────────────────┐ │
│  │  🔴 12 Jul 03:00  Heavy rain alert: 45mm in 24h at Bengalon │ │
│  │  🟡 12 Jul 01:00  Moderate wind: 28km/h at Wahana pit       │ │
│  │  🔴 11 Jul 18:00  Lightning detected within 10km — ops halt │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  ┌─── Bottom Panel: Point Timeseries ──────────────────────────┐  │
│  │  📈 Temperature at -1.2°S, 117.3°E                          │  │
│  │  ▁▂▃▅▇▆▅▃▂▁▂▃▄▆▇▇▆▅▄▃▂▁▂▃▄▅▇▆ ····· 168h                  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

## Components to Build / Modify

### Phase A — Layout Restructure (1 session)
1. **App.tsx** — Redesign layout: full-height map, overlay panels, bottom chart
2. **OpsStatusBar** (NEW) — 6 traffic-light indicators (rain, wind, temp, lightning, visibility, cloud)
3. **AlertPanel** (NEW) — Scrolling log of threshold exceedances
4. **LayerToggle** (NEW) — Checkbox panel for map overlays
5. **SiteSelector** (NEW) — Dropdown for predefined mine sites

### Phase B — Mining Overlays (1 session)
6. **SiteLayer** (NEW) — GeoJSON polygons for mine pits, haul roads, processing plants
7. **WindQuiver** (NEW) — Wind direction arrows from FCN u10m/v10m
8. **PrecipOverlay** (NEW) — Rain intensity from FCN + Himawari fusion
9. **LightningRisk** (NEW) — Heatmap around storm cells, proximity alerts

### Phase C — 7-Day Forecast Tile (1 session)
10. **ForecastTiles** (NEW) — 7-day summary cards from FCN data
11. **Point168hChart** (NEW) — Replace current TimeSeriesChart with multi-variable chart (t2m, precip, wind)

### Phase D — Alerting Engine (backend, 1 session)
12. **Backend `/api/alerts`** — Threshold engine that checks FCN + Himawari data and generates alerts
13. **Backend `/api/sites`** — Predefined mine site definitions (lat/lon, thresholds per site)

## Data Flow

```
FCN Forecast (168h, 26 vars) ──→ OpsStatusBar (current conditions)
                                  ForecastTiles (daily aggregates)
                                  AlertEngine (threshold checks)
                                  Point168hChart (click point → timeseries)

Himawari-9 (10-min BT) ────────→ RainOverlay (BT→rain proxy)
                                  StormCells (lightning proxy)
                                  LightningRisk (proximity)

GFS Analysis ───────────────────→ Verification (FCN vs observed, not shown)
```

## Color Palette (Mining Dashboard)

Severity colors: 🟢 Green = normal, 🟡 Amber = caution, 🔴 Red = alert
Accent: Cyan (`#06b6d4`) for interactive elements
Background: Slate 900/950 (current)
Map tiles: CartoDB Dark Matter for night-shift readability

## Key UX Decisions

1. **Default view**: FCastNet t2m as default layer — temperature is baseline for all mining ops
2. **Click on map**: Shows 168h stacked chart (temp + precip + wind) rather than single-var
3. **Site selector**: Predefined site lat/lon + threshold config, stored in backend
4. **Animations**: 6-hourly FCN timeline auto-play, 10-min Himawari timeline manual-step
5. **Mobile**: Priority on current conditions + alerts — map as expandable overlay

## Implementation Order

1. Layout restructure (App.tsx + OpsStatusBar + AlertPanel) ← immediate next
2. Site selector + site boundary layer
3. 7-day forecast tiles
4. Wind quiver overlay
5. Enhanced point chart (multi-variable)
6. Lighting risk + alerting engine

## Backend Changes Needed

- `backend/main.py`: New endpoints `/api/sites`, `/api/alerts`
- `backend/data_service.py`: Site definitions, threshold logic, alert generation
- Threshold config per variable + per site (e.g., Bengalon rain threshold = 40mm/day, Wahana = 55mm/day)
