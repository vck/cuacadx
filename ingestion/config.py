import os
from pathlib import Path


KALTIM_BBOX = {
    "lat_min": -3.0,
    "lat_max": 3.0,
    "lon_min": 115.0,
    "lon_max": 119.0,
}


ERA5_VARIABLES = [
    "t2m",
    "d2m",
    "u10",
    "v10",
    "sp",
    "msl",
    "tp",
]


ERA5_CDS_NAMES = {
    "t2m": "2m_temperature",
    "d2m": "2m_dewpoint_temperature",
    "u10": "10m_u_component_of_wind",
    "v10": "10m_v_component_of_wind",
    "sp": "surface_pressure",
    "msl": "mean_sea_level_pressure",
    "tp": "total_precipitation",
}


ERA5_UNITS = {
    "t2m": "K",
    "d2m": "K",
    "u10": "m/s",
    "v10": "m/s",
    "sp": "Pa",
    "msl": "Pa",
    "tp": "m",
}


CHIRPS_VARIABLES = ["precip"]


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ERA5_DIR = DATA_DIR / "era5"
CHIRPS_DIR = DATA_DIR / "chirps"
CLEAN_DIR = DATA_DIR / "clean"

DUCKDB_PATH = PROJECT_ROOT / "cuacadx.duckdb"


CDS_URL = "https://cds.climate.copernicus.eu/api"
CDS_KEY = os.environ.get("CDSAPI_KEY", "")


YEAR_START = 2020
YEAR_END = 2024
