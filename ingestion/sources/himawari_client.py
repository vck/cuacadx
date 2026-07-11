import bz2
import logging
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path

import certifi
import numpy as np
import pandas as pd
from pyproj import Proj

from ..config import KALTIM_BBOX

logger = logging.getLogger(__name__)

AWS_BASE = "https://noaa-himawari9.s3.amazonaws.com"
KALTIM_SEGMENTS = ["S0510", "S0610"]

C1 = 1.191042e-5
C2 = 1.4387752

_BASIC = np.dtype([('hblock_number','u1'),('blocklength','<u2'),('total_number_of_hblocks','<u2'),('byte_order','u1'),('satellite','S16'),('proc_center_name','S16'),('observation_area','S4'),('other_observation_info','S2'),('observation_timeline','<u2'),('observation_start_time','f8'),('observation_end_time','f8'),('file_creation_time','f8'),('total_header_length','<u4'),('total_data_length','<u4'),('quality_flag1','u1'),('quality_flag2','u1'),('quality_flag3','u1'),('quality_flag4','u1'),('file_format_version','S32'),('file_name','S128'),('spare','S40')])
_DATA = np.dtype([('hblock_number','u1'),('blocklength','<u2'),('number_of_bits_per_pixel','<u2'),('number_of_columns','<u2'),('number_of_lines','<u2'),('compression_flag_for_data','u1'),('spare','S40')])
_PROJ = np.dtype([('hblock_number','u1'),('blocklength','<u2'),('sub_lon','f8'),('CFAC','<u4'),('LFAC','<u4'),('COFF','f4'),('LOFF','f4'),('distance_from_earth_center','f8'),('earth_equatorial_radius','f8'),('earth_polar_radius','f8'),('req2_rpol2_req2','f8'),('rpol2_req2','f8'),('req2_rpol2','f8'),('coeff_for_sd','f8'),('resampling_types','<i2'),('resampling_size','<i2'),('spare','S40')])
_NAV = np.dtype([('hblock_number','u1'),('blocklength','<u2'),('navigation_info_time','f8'),('SSP_longitude','f8'),('SSP_latitude','f8'),('distance_earth_center_to_satellite','f8'),('nadir_longitude','f8'),('nadir_latitude','f8'),('sun_position','f8',(3,)),('moon_position','f8',(3,)),('spare','S40')])
_CAL = np.dtype([('hblock_number','u1'),('blocklength','<u2'),('band_number','<u2'),('central_wave_length','f8'),('valid_number_of_bits_per_pixel','<u2'),('count_value_error_pixels','<u2'),('count_value_outside_scan_pixels','<u2'),('gain_count2rad_conversion','f8'),('offset_count2rad_conversion','f8')])


def _ssl_ctx():
    return ssl.create_default_context(cafile=certifi.where())


def _url(date: str, time_str: str, band: str, seg: str) -> str:
    return (
        f"{AWS_BASE}/AHI-L1b-FLDK/{date[:4]}/{date[4:6]}/{date[6:8]}/{time_str}"
        f"/HS_H09_{date}_{time_str}_B{band}_FLDK_R20_{seg}.DAT.bz2"
    )


def _read_bz2(url: str) -> bytes:
    ctx = _ssl_ctx()
    with urllib.request.urlopen(url, context=ctx, timeout=120) as resp:
        compressed = resp.read()
    return bz2.decompress(compressed)


def _read_header(raw: bytes) -> dict:
    offset = 0
    b1 = np.frombuffer(raw[0:_BASIC.itemsize], dtype=_BASIC, count=1); offset += int(b1['blocklength'][0])
    b2 = np.frombuffer(raw[offset:offset+_DATA.itemsize], dtype=_DATA, count=1); offset += int(b2['blocklength'][0])
    b3 = np.frombuffer(raw[offset:offset+_PROJ.itemsize], dtype=_PROJ, count=1); offset += int(b3['blocklength'][0])
    b4 = np.frombuffer(raw[offset:offset+_NAV.itemsize], dtype=_NAV, count=1); offset += int(b4['blocklength'][0])
    b5 = np.frombuffer(raw[offset:offset+_CAL.itemsize], dtype=_CAL, count=1)

    h = {
        "satellite": bytes(b1["satellite"][0]).split(b"\x00")[0].decode("ascii", errors="replace"),
        "observation_area": bytes(b1["observation_area"][0]).split(b"\x00")[0].decode("ascii", errors="replace"),
        "num_cols": int(b2["number_of_columns"][0]),
        "num_lines": int(b2["number_of_lines"][0]),
        "sub_lon": float(b3["sub_lon"][0]),
        "cfac": int(b3["CFAC"][0]),
        "lfac": int(b3["LFAC"][0]),
        "coff": float(b3["COFF"][0]),
        "loff": float(b3["LOFF"][0]),
        "distance": float(b3["distance_from_earth_center"][0]),
        "ssp_lon": float(b4["SSP_longitude"][0]),
        "ssp_lat": float(b4["SSP_latitude"][0]),
        "band_number": int(b5["band_number"][0]),
        "central_wavelength": float(b5["central_wave_length"][0]),
        "cal_slope": float(b5["gain_count2rad_conversion"][0]),
        "cal_intercept": float(b5["offset_count2rad_conversion"][0]),
        "error_pixel": int(b5["count_value_error_pixels"][0]),
        "outside_scan_pixel": int(b5["count_value_outside_scan_pixels"][0]),
        "total_header_length": int(b1["total_header_length"][0]),
        "total_data_length": int(b1["total_data_length"][0]),
        "earth_eq_radius": float(b3["earth_equatorial_radius"][0]),
        "earth_pol_radius": float(b3["earth_polar_radius"][0]),
    }
    h["wavenumber"] = 10000.0 / h["central_wavelength"]
    return h


def _counts_to_bt(counts: np.ndarray, h: dict) -> np.ndarray:
    gain = abs(h["cal_slope"])
    intercept = h["cal_intercept"]
    wavenumber = h["wavenumber"]
    radiance = counts.astype(np.float64) * gain + intercept
    radiance = np.maximum(radiance, 0.001)
    bt = C2 * wavenumber / np.log(1 + C1 * wavenumber ** 3 / radiance)
    return bt


def _geolocate(ncols: int, nlines: int, seg_idx: int, h: dict) -> tuple[np.ndarray, np.ndarray]:
    cfac = h["cfac"]
    coff = h["coff"]
    loff = h["loff"]
    sub_lon = h["sub_lon"]
    eq_rad_m = h["earth_eq_radius"] * 1000.0
    pol_rad_m = h["earth_pol_radius"] * 1000.0

    sat_alt_m = (h["distance"] - h["earth_eq_radius"]) * 1000.0

    step_deg = 2 ** 16 / cfac
    step_m = sat_alt_m * np.tan(np.deg2rad(step_deg))

    p = Proj(proj='geos', h=sat_alt_m, a=eq_rad_m, b=pol_rad_m, lon_0=sub_lon, sweep='x')

    line0 = seg_idx * nlines
    cols = np.arange(ncols, dtype=np.float64)
    lines = np.arange(nlines, dtype=np.float64) + line0

    x = (cols - coff) * step_m
    y = (lines - loff) * step_m

    x2d, y2d = np.meshgrid(x, y)

    lons, lats = p(x2d, y2d, inverse=True)
    lats = np.where(np.isinf(lats), np.nan, lats)
    lons = np.where(np.isinf(lons), np.nan, lons)

    return lats, lons


def fetch_frame(date_str: str, time_str: str, seg_list: list[str] | None = None) -> pd.DataFrame | None:
    if seg_list is None:
        seg_list = KALTIM_SEGMENTS

    bbox = KALTIM_BBOX
    all_rows = []

    for seg in seg_list:
        url = _url(date_str, time_str, "13", seg)
        logger.info(f"  Downloading {url.split('/')[-1]}")
        try:
            raw = _read_bz2(url)
        except Exception as e:
            logger.warning(f"  Failed to download segment {seg}: {e}")
            continue

        h = _read_header(raw)
        logger.info(f"    seg={seg} {h['num_cols']}x{h['num_lines']} "
                     f"sat={h['satellite']} band={h['band_number']} "
                     f"cwl={h['central_wavelength']:.4f}um "
                     f"hdr_len={h['total_header_length']}")

        ncols = h["num_cols"]
        nlines = h["num_lines"]
        pixel_bytes = raw[h["total_header_length"]:h["total_header_length"] + ncols * nlines * 2]
        counts = np.frombuffer(pixel_bytes, dtype=">u2").reshape(nlines, ncols)

        bt = _counts_to_bt(counts, h)

        seg_idx_lookup = {f"S{str(i+1).zfill(2)}10": i for i in range(10)}
        seg_idx = seg_idx_lookup.get(seg, 0)

        lats, lons = _geolocate(ncols, nlines, seg_idx, h)

        invalid_mask = (counts == h["error_pixel"]) | (counts == h["outside_scan_pixel"])
        bt[invalid_mask] = np.nan

        print(f"    lat=[{np.nanmin(lats):.2f},{np.nanmax(lats):.2f}] "
              f"lon=[{np.nanmin(lons):.2f},{np.nanmax(lons):.2f}] "
              f"bt=[{np.nanmin(bt):.1f}K,{np.nanmax(bt):.1f}K] "
              f"valid_px={np.isfinite(bt).sum()}")

        mask = (
            np.isfinite(lats) & np.isfinite(lons)
            & (lats >= bbox["lat_min"]) & (lats <= bbox["lat_max"])
            & (lons >= bbox["lon_min"]) & (lons <= bbox["lon_max"])
        )
        if not mask.any():
            logger.info(f"  No Kaltim pixels in segment {seg}")
            continue

        bt_crop = bt[mask]
        lats_crop = lats[mask]
        lons_crop = lons[mask]

        for i in range(len(bt_crop)):
            all_rows.append({
                "lat": round(float(lats_crop[i]), 4),
                "lon": round(float(lons_crop[i]), 4),
                "bt_k": round(float(bt_crop[i]), 2),
            })

    if not all_rows:
        logger.warning(f"No data for {date_str} {time_str}")
        return None

    df = pd.DataFrame(all_rows)
    df["ts_utc"] = datetime.strptime(f"{date_str} {time_str}", "%Y%m%d %H%M")
    df["source"] = "himawari9"
    df["variable"] = "bt"
    logger.info(f"  => {len(df)} Kaltim pixels")
    return df


def fetch_timestamp(date_str: str, time_str: str) -> Path | None:
    df = fetch_frame(date_str, time_str)
    if df is None:
        return None

    out_dir = Path("data") / "himawari9" / date_str[:4] / date_str[4:6] / date_str[6:8] / time_str
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / "bt.parquet"
    df.to_parquet(parquet_path, index=False)
    logger.info(f"Saved: {parquet_path}")
    return parquet_path


def fetch_latest() -> Path | None:
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    minute = (now.minute // 10) * 10
    time_str = f"{now.hour:02d}{minute:02d}"
    date_str = now.strftime("%Y%m%d")

    return fetch_timestamp(date_str, time_str)
