# CUACADX — Regional Weather Intelligence Engine for Indonesia
### Technical & Product Blueprint v0.1

**Positioning:** bukan "GraphCast tapi versi Indonesia" — tapi *downscaling + nowcasting layer* yang duduk di atas global NWP/AI weather model, dikalibrasi ke ground-truth lokal, plus storm-cell nowcasting berbasis Himawari-9 buat convective event yang global model-nya nggak bisa liat.

Target customer: mining/energy/plantation ops (ITMG, port operators, perkebunan sawit) yang butuh *actionable* short-fuse alerting (badai, angin kencang, curah hujan ekstrem) — bukan cuma "prakiraan cuaca kelurahan" ala BMKG.

---

## 1. Arsitektur Sistem (High Level)

```
┌─────────────────┐   ┌──────────────────┐   ┌────────────────────┐
│  DATA INGESTION  │──▶│   FEATURE STORE   │──▶│  MODEL LAYER        │
│                  │   │   (DuckDB/Parquet)│   │                    │
│ - ERA5 (reanal.) │   │                  │   │ A) GraphCast-based │
│ - CHIRPS/IMERG   │   │  Partitioned by: │   │    regional model  │
│ - Himawari-9     │   │  - date          │   │ B) Storm-cell      │
│ - BMKG stations  │   │  - variable      │   │    detector/tracker│
│ - GFS/ECMWF open │   │  - region grid   │   │                    │
└─────────────────┘   └──────────────────┘   └────────────────────┘
                                                        │
                                                        ▼
                                            ┌────────────────────────┐
                                            │  INFERENCE / SERVING    │
                                            │  - Nowcast (0-6h)       │
                                            │  - Short-range (6-72h)  │
                                            │  - Calibration layer    │
                                            └────────────────────────┘
                                                        │
                                                        ▼
                                            ┌────────────────────────┐
                                            │  PRODUCT LAYER          │
                                            │  - API/Dashboard        │
                                            │  - Alert engine         │
                                            │  - LLM narrative/report │
                                            └────────────────────────┘
```

Prinsip desain: **jangan retrain GraphCast dari nol**. Compute buat pretrain foundation model global itu ratusan GPU-days, data ERA5 puluhan TB. Value lo ada di layer regional fine-tuning + fusion + calibration, bukan di layer pretraining global.

---

## 2. Data Ingestion Layer (Python + DuckDB)

### 2.1 Sumber data & karakteristik

| Source | Variable | Resolusi | Update freq | Akses |
|---|---|---|---|---|
| ERA5 (Copernicus CDS) | temp, wind, humidity, pressure, geopotential | 0.25° (~28km), hourly | 5 hari delay | `cdsapi` (butuh API key gratis) |
| CHIRPS | precipitation | ~5km, daily | ~2 hari delay | HTTP download langsung (GeoTIFF) |
| GPM IMERG | precipitation | 0.1° (~10km), 30-menit | near-real-time (~4jam) | NASA GES DISC (butuh Earthdata login) |
| Himawari-9 (JAXA) | full-disk imagery, IR/VIS bands | 2km (VIS 0.5-1km), 10-menit | near-real-time | JAXA P-Tree / AWS Open Data (Himawari bucket) |
| BMKG dataonline | ground station obs | per-stasiun, hourly/daily | historis (perlu request manual) | dataonline.bmkg.go.id |
| GFS/ECMWF open data | forecast fields (buat bootstrap awal sebelum GraphCast jalan) | 0.25°, 6-hourly | real-time | NOAA NOMADS / ECMWF open-data (gratis) |

### 2.2 Struktur pipeline ingestion

```
ingestion/
├── sources/
│   ├── era5_client.py       # cdsapi wrapper, chunked by month+variable
│   ├── chirps_client.py      # download + GeoTIFF -> array
│   ├── imerg_client.py       # earthaccess/harmony API
│   ├── himawari_client.py    # AWS S3 open data bucket (noaa-himawari9)
│   ├── bmkg_station_client.py
│   └── gfs_client.py
├── transform/
│   ├── regrid.py             # reproject semua source ke grid target lo
│   ├── normalize.py          # z-score per variable, per season
│   └── qc.py                 # flag outlier, gap-fill, station QC
├── loaders/
│   └── duckdb_loader.py      # parquet -> duckdb ingestion, partitioned
└── orchestration/
    └── dagster_pipeline.py   # atau Airflow/Prefect — scheduled DAG
```

### 2.3 Skema DuckDB

Prinsip: **DuckDB bukan tempat nyimpen raw grid tensor** (itu tetap di Parquet/Zarr, columnar, partitioned by date+variable). DuckDB dipakai sebagai *query layer* di atas Parquet — bagus banget buat ini karena native Parquet scan tanpa loading semua ke memory.

```python
# loaders/duckdb_loader.py
import duckdb

con = duckdb.connect("cuacadx.duckdb")

con.execute("""
CREATE TABLE IF NOT EXISTS obs_station (
    station_id      VARCHAR,
    ts_utc          TIMESTAMP,
    lat             DOUBLE,
    lon             DOUBLE,
    temp_c          DOUBLE,
    rh_pct          DOUBLE,
    wind_speed_ms   DOUBLE,
    wind_dir_deg    DOUBLE,
    precip_mm       DOUBLE,
    pressure_hpa    DOUBLE,
    source          VARCHAR,      -- 'bmkg' | 'era5_point_extract'
    qc_flag         TINYINT        -- 0=ok, 1=interpolated, 2=suspect
);

CREATE TABLE IF NOT EXISTS grid_reanalysis (
    ts_utc          TIMESTAMP,
    variable        VARCHAR,       -- 't2m','u10','v10','tp','msl', etc
    lat             DOUBLE,
    lon             DOUBLE,
    value           FLOAT,
    source          VARCHAR        -- 'era5','gfs','chirps'
) PARTITION BY (variable);

CREATE TABLE IF NOT EXISTS storm_cells (
    cell_id         VARCHAR,
    ts_utc          TIMESTAMP,
    centroid_lat    DOUBLE,
    centroid_lon    DOUBLE,
    area_km2        DOUBLE,
    max_reflectivity_proxy DOUBLE,   -- dari brightness temp IR
    track_id        VARCHAR,         -- hasil tracking, linked antar timestamp
    velocity_ms     DOUBLE,
    heading_deg     DOUBLE,
    source          VARCHAR          -- 'himawari9'
);
```

Kenapa DuckDB di sini masuk akal buat use-case lo:
- Query time-series per region/station itu jadi SQL biasa, gampang dipakai buat feature engineering (window functions buat rolling stats)
- `read_parquet()` native — bisa langsung query lake Parquet ERA5 yang di-partition by month tanpa ETL tambahan
- Cocok jalan di edge/on-prem (mirip pattern NONA lo yang offline-first) — nggak butuh Postgres server buat analytical query

```python
# contoh feature extraction buat training set
con.sql("""
    SELECT
        station_id,
        ts_utc,
        temp_c,
        AVG(precip_mm) OVER (
            PARTITION BY station_id ORDER BY ts_utc
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS precip_6h_rolling,
        LAG(pressure_hpa, 3) OVER (PARTITION BY station_id ORDER BY ts_utc) AS pressure_3h_ago
    FROM obs_station
    WHERE qc_flag = 0
""")
```

### 2.4 Orkestrasi & scheduling

- ERA5: batch monthly backfill (20 tahun ≈ bisa ditarget provinsi/regional bounding box dulu, jangan full-Indonesia grid resolution tinggi — storage bengkak)
- Himawari-9: streaming ingestion tiap 10 menit dari AWS Open Data bucket
- BMKG station: daily batch pull + manual historical backfill request
- Pakai Dagster atau Prefect (lebih ringan dari Airflow, cocok buat tim kecil) — asset-based DAG cocok banget buat pipeline data science kayak gini

---

## 3. Storm Cell Detection & Tracking (Himawari-9)

### 3.1 Pipeline

```
Himawari-9 raw (HSD/NetCDF)
   → radiance calibration → brightness temperature (IR band 13, 10.4µm)
   → cold-cloud-top thresholding (proxy convective activity)
   → segmentation (candidate cells)
   → tracking (frame-to-frame association)
   → feature extraction (area, growth rate, min BT, motion vector)
   → storm_cells table (DuckDB)
```

### 3.2 Detection model

Dua opsi, pilih sesuai maturity data lo:

**Opsi A — Threshold + connected component (baseline, ship dulu ini)**
- IR band 13 brightness temp < -60°C sampai -75°C = proxy strong convection (dasar teknik CI — Convective Initiation nowcasting yang sudah standar di met. ops)
- `scipy.ndimage.label` buat connected component, filter by min area
- Cepat, no training data needed, good enough buat MVP

**Opsi B — Learned segmentation (upgrade path, fits skillset lo dari CANOPAI/VANTARA)**
- YOLOv8-seg atau U-Net, input multi-band Himawari (IR1, IR2, WV, VIS kalau siang), output per-pixel convective probability
- Label pakai proxy dari radar BMKG kalau available di beberapa kota, atau self-supervised pakai threshold Opsi A sebagai weak label awal (bootstrap)

### 3.3 Tracking

Sesuai gaya lo yang udah biasa pakai Kalman filter (NONA, ANARCH context):
- Centroid tracking + Kalman filter per cell buat estimasi velocity vector & predicted next-position
- Association pakai Hungarian algorithm (IoU + distance cost) antar frame — mirip ByteTrack tapi buat blob bukan bounding box orang/kendaraan
- Output: `track_id`, `velocity_ms`, `heading_deg` → ini yang jadi basis nowcast 0-3 jam (lebih akurat dari NWP manapun buat window sependek ini, karena convective cell life-cycle cuma puluhan menit sampai beberapa jam)

Nowcasting window ini penting dipisah dari GraphCast layer — literatur nowcasting (termasuk DeepMind's precipitation nowcasting) udah proven bahwa untuk 0-6 jam, extrapolation-based approach (macam Lagrangian persistence + ML correction) ngalahin NWP global. Jadi arsitektur produk lo emang harus dual-track:

- **0-6 jam**: storm-cell tracker (Himawari-based) — high confidence, high spatial res, convective-specific
- **6-72 jam**: GraphCast-based regional model — synoptic scale, lower res tapi longer horizon

---

## 4. Model Layer — GraphCast-based Regional Model

### 4.1 Strategi: fine-tune, jangan pretrain

GraphCast (DeepMind, open-weight) dilatih di ERA5 global 0.25°. Untuk Indonesia:

1. **Gunakan pretrained GraphCast weights** sebagai backbone/prior
2. **Regional fine-tuning**: freeze sebagian besar layer message-passing global, fine-tune decoder head + tambahkan regional refinement network di atasnya, dilatih khusus di domain Indonesia (bounding box ~95°E-141°E, 11°S-6°N) dengan resolusi lebih halus dari 0.25° pakai downscaling network terpisah

```
[Global GraphCast output, 0.25°]
            │
            ▼
[Regional crop: Indonesia bbox]
            │
            ▼
[Downscaling network]  ← ini yang lo train sendiri
   - input: coarse GraphCast fields + static terrain (elevation, land-sea mask, coastline)
   - arsitektur: U-Net atau Vision Transformer super-resolution
   - target resolution: ~5-10km
            │
            ▼
[Bias correction / calibration layer]
   - input: downscaled output + historical BMKG station error
   - metode: quantile mapping ATAU lightweight gradient-boosted correction per station
            │
            ▼
[Final regional forecast, per grid cell]
```

### 4.2 Kenapa downscaling network, bukan full retrain

- GraphCast full retrain butuh data ERA5 skala global penuh + compute besar (DeepMind train pakai TPU pods) — nggak realistis buat tim kecil
- Downscaling network (super-resolution style) itu problem yang jauh lebih kecil: input-output pair-nya cuma coarse-to-fine di domain terbatas (Indonesia), dataset yang dibutuhkan jauh lebih kecil
- Ini pattern yang sama kayak literature "statistical downscaling" di klimatologi, cuma versi neural network-nya

### 4.3 Training loop (skeleton)

```python
# training/downscale_train.py
import torch
from torch.utils.data import DataLoader

class DownscaleDataset(torch.utils.data.Dataset):
    """
    Pairs: (coarse GraphCast/ERA5 field, terrain static, fine BMKG-calibrated target)
    Pulled directly from DuckDB via read_parquet + SQL join, no separate ETL needed.
    """
    def __init__(self, duckdb_con, split="train"):
        self.con = duckdb_con
        self.index = self.con.sql(f"""
            SELECT ts_utc FROM grid_reanalysis
            WHERE variable = 't2m' AND split_tag = '{split}'
        """).df()

    def __getitem__(self, idx):
        ts = self.index.iloc[idx]["ts_utc"]
        coarse = self._fetch_coarse(ts)
        target = self._fetch_target(ts)
        static = self._fetch_static()
        return coarse, static, target

model = RegionalDownscaleUNet(in_channels=..., out_channels=...)
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
loss_fn = torch.nn.L1Loss()  # MAE lebih robust buat precip yang skewed

for epoch in range(epochs):
    for coarse, static, target in train_loader:
        pred = model(coarse, static)
        loss = loss_fn(pred, target)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
```

### 4.4 Evaluasi

Metrik standar meteorologi, bukan cuma MAE biasa:
- **RMSE/MAE** per variable (temp, wind, precip terpisah — precip butuh metrik khusus karena distribusinya skewed)
- **CSI (Critical Success Index)** & **POD/FAR** buat threshold-based rain event (misal >20mm/hari) — ini metrik yang dipakai BMKG/WMO buat verifikasi forecast hujan
- **Brier score** kalau output-nya probabilistic
- Backtesting terhadap 20yr historical data yang udah lo kumpulin — walk-forward validation per musim (Indonesia punya pola wet/dry season yang harus displit biar nggak leakage)

---

## 5. Serving & Product Layer

### 5.1 Inference stack

```
Client request (lat/lon or region)
        │
        ▼
API Gateway (Go, sesuai stack lo yang biasa)
        │
        ├──▶ Nowcast service (0-6h)   → storm_cells table + extrapolation
        ├──▶ Short-range service (6-72h) → regional GraphCast model output (cached, refreshed tiap run cycle GFS/ECMWF, ~4x/hari)
        └──▶ Alert engine → threshold rules (wind>X, precip>Y) → push notif/webhook
```

### 5.2 Peran LLM di produk ini (bukan di core prediction)

- **Report generation**: convert structured forecast JSON → narasi Bahasa Indonesia yang bisa dibaca ops manager tambang/perkebunan ("Potensi hujan lebat 60mm dalam 3 jam ke depan di area X, disertai angin kencang dari arah tenggara")
- **Anomaly explanation**: kalau model confidence rendah atau ada disagreement antar model (storm-cell vs GraphCast layer), LLM bisa generate context/caveat ke user
- **Conversational query layer**: "gimana cuaca minggu depan buat area tambang blok 7?" → LLM translate ke structured query ke API di atas, bukan LLM yang predict cuacanya

### 5.3 Product tiering (nyambung ke pola produk lo yang lain — ANARCH/CANOPAI B2B)

| Tier | Target | Fitur |
|---|---|---|
| Basic | Perkebunan kecil, SME | Forecast harian per titik koordinat, alert dasar |
| Pro | Mining/energy ops | Nowcast storm-cell real-time, dashboard, API access |
| Enterprise | ITMG-scale client | On-prem/edge deployment option, custom threshold alerting, SLA, integrasi ke existing ops system |

---

## 6. Roadmap Implementasi (realistis)

**Phase 0 (2-3 minggu)** — Data foundation
- Setup ERA5 + CHIRPS ingestion buat 1 region pilot (misal Kalimantan Timur, area ITMG)
- BMKG station historical request buat ground truth
- DuckDB schema live, backfill 5 tahun dulu (bukan langsung 20 tahun — validasi pipeline dulu)

**Phase 1 (3-4 minggu)** — Storm-cell MVP
- Himawari-9 ingestion + threshold-based detection (Opsi A)
- Kalman filter tracking
- Validasi visual vs kejadian cuaca aktual yang diketahui

**Phase 2 (6-8 minggu)** — Regional downscaling model
- GraphCast pretrained inference pipeline jalan (pakai open-weight, cukup GPU consumer buat inference — bukan training dari nol)
- Downscaling network training di region pilot
- Bias correction layer pakai BMKG station data

**Phase 3** — Product wrap
- API + dashboard + alert engine
- LLM narrative layer
- Pilot ke 1 klien (ITMG kalau udah warm)

---

## 7. Risiko & catatan jujur

- **Data BMKG historis itu gap-prone** — jangan andalkan ini sebagai primary source, cuma buat kalibrasi/validasi
- **GraphCast inference butuh GPU decent** (bukan trivial di edge/Termux-scale device) — untuk versi real-time production, ini kemungkinan besar butuh cloud GPU instance, bukan on-prem edge kayak NONA
- **Convective storm di tropis itu genuinely hard** — jangan janji akurasi tinggi ke klien enterprise di fase awal, posisikan sebagai "decision support" bukan "guaranteed forecast"
- **Lisensi data**: ERA5/CHIRPS/IMERG semua gratis buat riset & komersial dengan atribusi, tapi cek ulang term Himawari-9 AWS Open Data kalau mau dipakai di produk komersial berbayar
