"""Parquet file helpers."""

import os
from pathlib import Path

import pandas as pd


def write_parquet_atomic(df: pd.DataFrame, path: Path) -> None:
    """Write `df` so readers never see a partial file, on POSIX and Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)
