import logging

import duckdb

from ..config import CLEAN_DIR, DUCKDB_PATH, ERA5_DIR, ERA5_VARIABLES

logger = logging.getLogger(__name__)


def create_schema(con: duckdb.DuckDBPyConnection) -> None:
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
            source          VARCHAR,
            qc_flag         TINYINT
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS storm_cells (
            cell_id                VARCHAR,
            ts_utc                 TIMESTAMP,
            centroid_lat           DOUBLE,
            centroid_lon           DOUBLE,
            area_km2               DOUBLE,
            max_reflectivity_proxy DOUBLE,
            track_id               VARCHAR,
            velocity_ms            DOUBLE,
            heading_deg            DOUBLE,
            source                 VARCHAR
        )
    """)

    logger.info("Schema ready: obs_station, storm_cells")


def register_views(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("DROP VIEW IF EXISTS grid_reanalysis")

    parquet_glob = str(CLEAN_DIR / "era5" / "*" / "*" / "*.parquet")
    try:
        con.execute(f"""
            CREATE VIEW grid_reanalysis AS
            SELECT * FROM read_parquet('{parquet_glob}', union_by_name=True)
        """)
        logger.info("View grid_reanalysis → clean/era5/*.parquet")
    except Exception:
        con.execute("CREATE VIEW grid_reanalysis AS SELECT NULL::TIMESTAMP AS ts_utc WHERE 1=0")
        logger.info("View grid_reanalysis created (empty — no parquet files yet)")


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(DUCKDB_PATH))
    con.execute("SET memory_limit = '4GB'")
    con.execute("SET threads = 4")
    return con


def init() -> duckdb.DuckDBPyConnection:
    """Create DuckDB database with schema + views."""
    con = connect()
    create_schema(con)
    register_views(con)
    logger.info(f"DuckDB ready at {DUCKDB_PATH}")
    return con
