import logging
from pathlib import Path

import pandas as pd

from ..config import CLEAN_DIR, DATA_DIR

logger = logging.getLogger(__name__)


RANGE_LIMITS = {
    "t2m": {"min": 223.15, "max": 333.15},
    "d2m": {"min": 223.15, "max": 323.15},
    "u10": {"min": -50.0, "max": 50.0},
    "v10": {"min": -50.0, "max": 50.0},
    "sp": {"min": 50000.0, "max": 110000.0},
    "msl": {"min": 85000.0, "max": 110000.0},
    "tp": {"min": -0.001, "max": 2.0},
    "precip": {"min": -0.001, "max": 1500.0},
}


def flag_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Add qc_flag column: 0=ok, 2=suspect if value outside range."""
    df = df.copy()
    df["qc_flag"] = 0

    var = df["variable"].iloc[0] if "variable" in df.columns else "precip"
    limits = RANGE_LIMITS.get(var)

    val_col = "value" if "value" in df.columns else var
    if limits and val_col in df.columns:
        mask = (df[val_col] < limits["min"]) | (df[val_col] > limits["max"])
        df.loc[mask, "qc_flag"] = 2
        n = mask.sum()
        if n:
            logger.warning(f"  Flagged {n} outliers in {var}")

    return df


def run(parquet_path: Path) -> Path:
    """Read a per-variable Parquet, apply QC, write to clean dir."""
    df = pd.read_parquet(parquet_path)
    df = flag_outliers(df)

    rel = parquet_path.relative_to(parquet_path.parent.parent.parent)
    clean_path = Path(__file__).resolve().parent.parent.parent / "data" / "clean" / rel
    clean_path.parent.mkdir(parents=True, exist_ok=True)

    df.to_parquet(clean_path, index=False)
    logger.info(f"QC done → {clean_path}")
    return clean_path
