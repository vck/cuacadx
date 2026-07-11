#!/usr/bin/env python3
import argparse
import logging
import sys

from ingestion.config import ERA5_VARIABLES, YEAR_END, YEAR_START
from ingestion.sources import chirps_client, era5_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingestion")


def run_month(year: int, month: int, skip_chirps: bool = False) -> None:
    logger.info(f"=== {year}-{month:02d} ===")

    logger.info("--- ERA5 ---")
    era5_client.fetch(year, month, ERA5_VARIABLES)

    if not skip_chirps:
        logger.info("--- CHIRPS ---")
        chirps_client.fetch(year, month)

    logger.info(f"=== Done {year}-{month:02d} ===\n")


def backfill(year_start: int, year_end: int, skip_chirps: bool = False) -> None:
    for year in range(year_start, year_end + 1):
        for month in range(1, 13):
            run_month(year, month, skip_chirps)


def main() -> None:
    parser = argparse.ArgumentParser(description="CUACADX data ingestion")
    parser.add_argument("--year", type=int, help="Year to ingest")
    parser.add_argument("--month", type=int, help="Month to ingest")
    parser.add_argument("--backfill", action="store_true", help="Run full backfill")
    parser.add_argument("--skip-chirps", action="store_true", help="Skip CHIRPS")

    args = parser.parse_args()

    if args.backfill:
        backfill(YEAR_START, YEAR_END, args.skip_chirps)
    elif args.year and args.month:
        run_month(args.year, args.month, args.skip_chirps)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
