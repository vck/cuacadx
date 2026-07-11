import numpy as np
from scipy.ndimage import label

BT_THRESHOLD_K = 233.0
MIN_CELL_PIXELS = 3
RASTER_RES_DEG = 0.05

# Tracking
IOU_MATCH_THRESHOLD = 0.1
MAX_SPEED_MS = 60  # m/s — sanity cap for storm motion (~200 km/h)


def detect_cells(
    bt: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    threshold: float = BT_THRESHOLD_K,
    min_pixels: int = MIN_CELL_PIXELS,
    resolution_deg: float = RASTER_RES_DEG,
) -> list[dict]:
    cold_mask = bt < threshold
    if cold_mask.sum() < min_pixels:
        return []

    lat_c, lon_c = lat[cold_mask], lon[cold_mask]

    lat_grid = np.arange(lat_c.min(), lat_c.max() + resolution_deg, resolution_deg)
    lon_grid = np.arange(lon_c.min(), lon_c.max() + resolution_deg, resolution_deg)
    if len(lat_grid) < 2 or len(lon_grid) < 2:
        return []

    ix = np.clip(np.searchsorted(lat_grid, lat_c) - 1, 0, len(lat_grid) - 2)
    iy = np.clip(np.searchsorted(lon_grid, lon_c) - 1, 0, len(lon_grid) - 2)

    raster = np.zeros((len(lat_grid) - 1, len(lon_grid) - 1), dtype=bool)
    np.add.at(raster, (ix, iy), True)

    labeled, n_cells = label(raster)

    cells = []
    for cell_id in range(1, n_cells + 1):
        pixel_count = int((labeled == cell_id).sum())
        if pixel_count < min_pixels:
            continue

        ys, xs = np.where(labeled == cell_id)
        cell_lats = lat_grid[ys] + resolution_deg / 2
        cell_lons = lon_grid[xs] + resolution_deg / 2

        cells.append({
            "cell_id": cell_id,
            "centroid_lat": round(float(cell_lats.mean()), 4),
            "centroid_lon": round(float(cell_lons.mean()), 4),
            "pixel_count": pixel_count,
            "min_lat": round(float(cell_lats.min()), 4),
            "max_lat": round(float(cell_lats.max()), 4),
            "min_lon": round(float(cell_lons.min()), 4),
            "max_lon": round(float(cell_lons.max()), 4),
            "polygon": [
                [round(float(cell_lats.min()), 4), round(float(cell_lons.min()), 4)],
                [round(float(cell_lats.min()), 4), round(float(cell_lons.max()), 4)],
                [round(float(cell_lats.max()), 4), round(float(cell_lons.max()), 4)],
                [round(float(cell_lats.max()), 4), round(float(cell_lons.min()), 4)],
            ],
        })

    return cells


def track_cells(
    prev_cells: list[dict],
    curr_cells: list[dict],
    dt_seconds: float = 600,
) -> list[dict]:
    """Match cells between consecutive frames by IoU overlap + centroid distance.

    Returns curr_cells augmented with track_id, velocity_ms, heading_deg.
    """
    unmatched = list(range(len(curr_cells)))
    for pc in prev_cells:
        pb = (pc["min_lat"], pc["max_lat"], pc["min_lon"], pc["max_lon"])
        best_i, best_iou = -1, 0
        for i in unmatched:
            cb = (curr_cells[i]["min_lat"], curr_cells[i]["max_lat"],
                  curr_cells[i]["min_lon"], curr_cells[i]["max_lon"])
            iou = _bbox_iou(pb, cb)
            if iou > best_iou:
                best_iou = iou
                best_i = i
        if best_i >= 0 and best_iou >= IOU_MATCH_THRESHOLD:
            ci = curr_cells[best_i]
            ci["track_id"] = pc.get("track_id", pc["cell_id"])
            dlat = ci["centroid_lat"] - pc["centroid_lat"]
            dlon = ci["centroid_lon"] - pc["centroid_lon"]
            dy = dlat * 111000
            dx = dlon * 111000 * np.cos(np.deg2rad(ci["centroid_lat"]))
            dist_m = np.sqrt(dx**2 + dy**2)
            speed = min(dist_m / dt_seconds, MAX_SPEED_MS)
            heading = (np.degrees(np.arctan2(dx, dy)) + 360) % 360
            ci["velocity_ms"] = round(float(speed), 1)
            ci["heading_deg"] = round(float(heading), 1)
            unmatched.remove(best_i)

    for i in unmatched:
        curr_cells[i]["track_id"] = curr_cells[i]["cell_id"]
        curr_cells[i]["velocity_ms"] = 0
        curr_cells[i]["heading_deg"] = 0

    return curr_cells


def _bbox_iou(a: tuple, b: tuple) -> float:
    a_min_lat, a_max_lat, a_min_lon, a_max_lon = a
    b_min_lat, b_max_lat, b_min_lon, b_max_lon = b
    ix_min = max(a_min_lat, b_min_lat)
    ix_max = min(a_max_lat, b_max_lat)
    iy_min = max(a_min_lon, b_min_lon)
    iy_max = min(a_max_lon, b_max_lon)
    if ix_min >= ix_max or iy_min >= iy_max:
        return 0.0
    inter = (ix_max - ix_min) * (iy_max - iy_min)
    a_area = (a_max_lat - a_min_lat) * (a_max_lon - a_min_lon)
    b_area = (b_max_lat - b_min_lat) * (b_max_lon - b_min_lon)
    union = a_area + b_area - inter
    return inter / union if union > 0 else 0.0
