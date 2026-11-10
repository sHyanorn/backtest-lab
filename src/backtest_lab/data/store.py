"""The Parquet cache: its layout, atomic writes and DuckDB views over it.

`<data_dir>/raw/prices/<ticker>.parquet` and `<data_dir>/raw/macro/<series>.parquet`.
"""

import os
from collections.abc import Sequence
from pathlib import Path

import duckdb
import pandas as pd

from backtest_lab.engine.backtest import Prices

PRICE_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume", "dividends", "splits"]
DATE_COLUMNS = {"prices": ("date",), "macro": ("date", "available_date")}


def raw_dir(data_dir: Path) -> Path:
    return data_dir / "raw"


def price_file(raw: Path, ticker: str) -> Path:
    return raw / "prices" / f"{ticker}.parquet"


def macro_file(raw: Path, series_id: str) -> Path:
    return raw / "macro" / f"{series_id}.parquet"


def write_parquet_atomic(df: pd.DataFrame, path: Path) -> None:
    """Write `df` so readers never see a partial file, on POSIX and Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def connect(root: Path) -> duckdb.DuckDBPyConnection:
    """In-memory connection with a view per table that has Parquet files under `root`.

    Dates are exposed as DATE in both views so prices and macro join directly.
    """
    con = duckdb.connect()
    for table, date_cols in DATE_COLUMNS.items():
        files = sorted((root / table).glob("*.parquet"))
        if not files:
            continue
        # An explicit file list, so brackets or asterisks in `root` are not read as a glob.
        paths = ", ".join("'" + f.as_posix().replace("'", "''") + "'" for f in files)
        casts = ", ".join(f"CAST({c} AS DATE) AS {c}" for c in date_cols)
        con.execute(
            f"CREATE VIEW {table} AS SELECT * REPLACE ({casts}) FROM read_parquet([{paths}])"
        )
    return con


def price_panel(
    con: duckdb.DuckDBPyConnection, tickers: Sequence[str], field: str = "adj_close"
) -> pd.DataFrame:
    """Wide frame of one price field: one row per date, one column per ticker."""
    if field not in PRICE_COLUMNS:
        raise ValueError(f"unknown field {field!r}")
    long = con.execute(
        f"SELECT date, ticker, {field} AS value FROM prices "
        "WHERE list_contains(?, ticker) ORDER BY date",
        [list(tickers)],
    ).df()
    # pivot (not pivot_table) so a duplicate (date, ticker) raises instead of being averaged
    wide = long.pivot(index="date", columns="ticker", values="value")  # noqa: PD010
    missing = set(tickers) - set(wide.columns)
    if missing:
        raise KeyError(f"no prices for {sorted(missing)}")
    wide.index = pd.DatetimeIndex(wide.index).as_unit("us")
    wide.columns.name = None
    return wide[list(tickers)]


def load_prices(con: duckdb.DuckDBPyConnection, tickers: Sequence[str]) -> Prices:
    """Total-return adjusted opens and closes of `tickers`."""
    raw = {field: price_panel(con, tickers, field) for field in ("open", "close", "adj_close")}
    return Prices.from_raw(raw["open"], raw["close"], raw["adj_close"])


def macro_series(con: duckdb.DuckDBPyConnection, series_id: str) -> pd.DataFrame:
    """Observations of one series with the date each became available."""
    df = con.execute(
        "SELECT date, value, available_date FROM macro WHERE series = ? ORDER BY date",
        [series_id],
    ).df()
    if df.empty:
        raise KeyError(f"no macro data for {series_id!r}")
    return df
