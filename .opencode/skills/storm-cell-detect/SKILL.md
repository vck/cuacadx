---
name: storm-cell-detect
description: Use when building or running the Himawari-9 storm cell detection and tracking pipeline. IR threshold segmentation, connected-component labeling, Kalman filter tracking, and feature extraction.
---

# Storm Cell Detection & Tracking

## Overview

Two-tier approach from the blueprint:

- **Opsi A (baseline):** IR brightness temperature threshold + connected
  components. No training data needed. Ship first.
- **Opsi B (upgrade):** Learned segmentation (YOLOv8-seg / U-Net) with weak
  labels from Opsi A as bootstrap.

## Opsi A Pipeline

```
Himawari-9 Band 13 (10.4µm, 2km)
  → crop to Kaltim region
  → radiance → brightness temperature (BT)
  → BT < -60°C → binary convective mask
  → scipy.ndimage.label → connected components
  → filter by min area (>50 km²)
  → centroid + feature extraction
  → track_id via Kalman filter + Hungarian association
  → storm_cells Parquet
```

### Threshold Selection

- **-60°C** (213K): Deep convection / cumulonimbus anvil
- **-70°C** (203K): Very strong convection, overshooting tops
- **-40°C** (233K): Moderate convection, growing cumulus

Start with -60°C for MVP; tune based on validation against actual events.

### Connected Components

```python
from scipy.ndimage import label, find_objects

mask = bt < 213.15  # boolean: convective/not
labeled, n_features = label(mask)
slices = find_objects(labeled)

for i, slc in enumerate(slices, 1):
    cell_mask = labeled[slc] == i
    area_px = cell_mask.sum()
    # area_km2 ≈ area_px * (2km)² (at 2km resolution)
```

### Feature Extraction

Per detected cell:

| Feature | Method |
|---------|--------|
| Centroid | `ndimage.center_of_mass(mask, labeled, i)` |
| Area | Pixel count × spatial resolution |
| Min BT | Min brightness temp within cell mask |
| Mean BT | Mean brightness temp within cell mask |
| Boundary | `ndimage.find_objects` bounding box |

## Tracking (Kalman Filter)

### State Vector

```
x = [cx, cy, vx, vy]ᵀ
  - cx, cy: centroid position (pixel coords)
  - vx, vy: velocity in pixels per frame
```

### Constant Velocity Model

```
F = [[1, 0, dt, 0],
     [0, 1, 0, dt],
     [0, 0, 1,  0],
     [0, 0, 0,  1]]
```

### Association (Hungarian Algorithm)

Cost matrix based on:
- IoU of bounding boxes between frames
- Euclidean distance between centroids
- Optionally: size similarity

```python
from scipy.optimize import linear_sum_assignment

cost = iou_matrix(current_cells, previous_cells)
row_idx, col_idx = linear_sum_assignment(cost)
```

### Track Management

- **Confirm:** after 2 consecutive associations → assign `track_id`
- **Coast:** up to 3 frames without association (cell temporarily obscured)
- **Delete:** >3 frames without association → end track

## Output Schema (DuckDB `storm_cells`)

```sql
CREATE TABLE storm_cells (
    cell_id                VARCHAR,       -- "SC_{date}_{track_id}_{frame}"
    ts_utc                 TIMESTAMP,
    centroid_lat           DOUBLE,
    centroid_lon           DOUBLE,
    area_km2               DOUBLE,
    min_bt_c               DOUBLE,        -- min brightness temp in °C
    track_id               VARCHAR,
    velocity_ms            DOUBLE,        -- from Kalman filter
    heading_deg            DOUBLE,        -- direction of motion
    source                 VARCHAR        -- 'himawari9'
);
```

Or save as Parquet with matching schema.

## Velocity Vector (for nowcast)

The Kalman filter velocity can be converted to physical units:

```python
# pixel velocity → m/s
# 1 pixel ≈ 2 km (at nadir)
# dt = 10 minutes = 600 seconds
vx_ms = vx_px * 2000 / 600  # m/s
heading = (90 - np.degrees(np.arctan2(vy, -vx))) % 360
```

This velocity + heading is the basis for **0-3 hour nowcast** — the main
differentiator from global NWP models.

## References

- Blueprint §3: Storm Cell Detection & Tracking
- `scipy.ndimage.label`, `scipy.ndimage.center_of_mass`
- `filterpy.kalman.KalmanFilter` (if using filterpy)
- Hungarian algorithm: `scipy.optimize.linear_sum_assignment`
