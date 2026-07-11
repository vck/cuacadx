#!/usr/bin/env python3
"""FourCastNet forecast runner.

Usage:
    python run_fcn.py                         # latest cycle, 168h forecast
    python run_fcn.py 20260711 06               # specific cycle
    python run_fcn.py 20260711 06 --steps 4      # 24h forecast
"""
import argparse
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("run_fcn")


def main():
    parser = argparse.ArgumentParser(description="FourCastNet forecast runner")
    parser.add_argument("date", nargs="?", help="YYYYMMDD")
    parser.add_argument("cycle", nargs="?", help="HH")
    parser.add_argument("--steps", type=int, default=28, help="forecast steps (168h)")
    parser.add_argument("--keep-gribs", action="store_true")
    args = parser.parse_args()

    date = args.date
    cycle = args.cycle

    from ingestion.models.fourcastnet_pipeline import download_ic, run_forecast, crop_kalimantan, _latest_cycle

    if not date or not cycle:
        date, cycle = _latest_cycle()
    logger.info(f"FCN forecast {date} {cycle}z, {args.steps} steps ({args.steps*6}h)")

    ic = download_ic(date, cycle)
    if ic is None:
        logger.error("Failed to get IC")
        return 1

    logger.info(f"Running {args.steps} steps ({args.steps*6}h)...")
    t0 = time.perf_counter()
    outputs = run_forecast(ic.float(), args.steps)
    logger.info(f"  Total: {time.perf_counter()-t0:.1f}s")

    logger.info("Cropping to Kalimantan...")
    df = crop_kalimantan(outputs)

    out_dir = Path("data/fcn") / date / cycle
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "forecast.parquet"
    df.to_parquet(path, index=False)
    logger.info(f"Saved: {path} ({path.stat().st_size/1024/1024:.1f} MB)")

    if not args.keep_gribs:
        tmp = out_dir / "gribs"
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
