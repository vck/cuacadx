---
name: himawari-read
description: Use when reading, downloading, or processing Himawari-9 satellite data from the NOAA AWS Open Data bucket. Covers bucket structure, HSD format, band selection, region cropping, and brightness temperature calculation.
---

# Himawari-9 Read

## AWS Bucket

```
s3://noaa-himawari9/
```

Bucket is requester-pays? **No** — free and open access.

Access via HTTPS:
```
https://noaa-himawari9.s3.amazonaws.com/<key>
```

## Data Format

HSD (Himawari Standard Data), bzip2-compressed:
```
AHI-L1b-FLDK/<YYYY>/<MM>/<DD>/<HHMM>/
  HS_H09_<YYYYMMDD>_<HHMM>_B<BB>_FLDK_R<RR>_S<SSSS>.DAT.bz2
```

### Filename Breakdown

| Part | Meaning |
|------|---------|
| `HS` | Himawari Standard |
| `H09` | Himawari-9 |
| `YYYYMMDD_HHMM` | Observation timestamp (UTC) |
| `B<BB>` | Band number: 01..16 |
| `FLDK` | Full disk |
| `R<RR>` | Resolution code: 05 (0.5km), 10 (1km), 20 (2km) |
| `S<SSSS>` | Segment: 0210, 0310, ..., 1010 (10 stripes covering disk N→S) |

### Segment Coverage

The full disk is split into 10 north-south segments. Kalimantan (equatorial)
falls in segments **S0510–S0610**. Only 1-2 segments need to be downloaded.

## Bands for Storm Detection

| Band | Wavelength | Resolution | Use |
|------|-----------|------------|-----|
| B07 | 3.9µm | 2km | Cloud phase, fog |
| **B13** | **10.4µm** | **2km** | **Primary — cloud top temperature** |
| B14 | 11.2µm | 2km | Split window, cloud masking |

## Brightness Temperature Calculation

HSD stores radiance. Convert to brightness temperature (BT) using the
inverse Planck function:

```python
# Band 13 central wavenumber: ~960 cm⁻¹
c1 = 1.191042e-5  # 2hc² (mW/m²/sr/cm⁻⁴)
c2 = 1.4387752     # hc/k (K)
vc = 960.0         # central wavenumber for Band 13

# radiance → BT
bt = c2 * vc / (np.log(c1 * vc**3 / radiance + 1))
```

Threshold: **BT < -60°C (213.15 K)** = proxy strong convection.

## Reading HSD with Python

Use `satpy` (recommended) or raw HSD reader:

```python
from satpy import Scene
from glob import glob

filenames = glob("HS_H09_*_B13_*.DAT.bz2")
scn = Scene(filenames, reader="himawari_hsd")
scn.load(["IR_104"])
# scn["IR_104"] is a DataArray with lat/lon coords
```

Alternative: `xarray` with `h5netcdf` for native NetCDF format if re-gridded
files are available.

## Crop to Kaltim

After loading the full-disk scene, crop to Kaltim bounding box:

```python
from pyresample import geometry, kd_tree

area_def = geometry.AreaDefinition(
    "kaltim", "Kaltim", "kaltim",
    {"proj": "longlat", "datum": "WGS84"},
    25, 17,  # width, height in grid cells
    [115.0, -3.0, 119.0, 3.0],  # LL, UL, UR, LR or [W, S, E, N]
)
result = kd_tree.resample_nearest(
    scn["IR_104"].values, scn["IR_104"].attrs["area"], area_def, radius_of_influence=50000
)
```

## Pipeline

1. List AWS bucket for target datetime + band
2. Download relevant 1-2 segments (S0510, S0610 for Kaltim)
3. Decompress bzip2
4. Read HSD via `satpy` or raw binary
5. Convert to brightness temperature
6. Crop to Kaltim bbox
7. Save as Parquet (lat, lon, ts_utc, bt_c, band, source)

## File size estimates

| Item | Size |
|------|------|
| 1 segment (compressed) | ~3 MB |
| 1 segment (decompressed) | ~15 MB |
| Kaltim crop (2km res) | ~72 KB |
| Per day (1 band, 144 scans) | ~11 MB processed |

## Known issues

- Data only available from **2022-10-28** on AWS (no older archive)
- Raw HSD needs `satpy` with `geotiepoints` — install via pip
- Segments for a single scan arrive asynchronously; check all segments exist
  before processing full frame
