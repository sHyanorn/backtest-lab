"""DuckDB views over the Parquet cache."""

from collections.abc import Sequence
from pathlib import Path

import duckdb
import pandas as pd

from backtest_lab.data.prices import COLUMNS as PRICE_COLUMNS

DATE_COLUMNS = {"prices": ("date",), "macro": ("date", "available_date")}


def connect(root: Path) -> duckdb.DuckDBPyConnection:
    """In-memory connection with a view per table that has Parquet files under `root`.

    Dates are exposed as DATE in both views so prices and macro join directly.
    """
    con = duckdb.connect()
    for table, date_cols in DATE_COLUMNS.items():
        if not any((root / table).glob("*.parquet")):
            continue
        pattern = (root / table / "*.parquet").as_posix().replace("'", "''")
        casts = ", ".join(f"CAST({c} AS DATE) AS {c}" for c in date_cols)
        con.execute(
            f"CREATE VIEW {table} AS SELECT * REPLACE ({casts}) FROM read_parquet('{pattern}')"
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


def macro_series(con: duckdb.DuckDBPyConnection, series_id: str) -> pd.DataFrame:
    """Observations of one series with the date each became available."""
    df = con.execute(
        "SELECT date, value, available_date FROM macro WHERE series = ? ORDER BY date",
        [series_id],
    ).df()
    if df.empty:
        raise KeyError(f"no macro data for {series_id!r}")
    return df
