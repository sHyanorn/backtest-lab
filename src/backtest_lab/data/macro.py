"""FRED macro series from the keyless fredgraph CSV download (see D007, D010)."""

import io
import urllib.request
from enum import StrEnum
from pathlib import Path

import pandas as pd

from backtest_lab.data.fetch import with_retries
from backtest_lab.data.storage import write_parquet_atomic

FREDGRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
COLUMNS = ["series", "date", "value", "available_date"]


class Frequency(StrEnum):
    DAILY = "daily"
    MONTHLY = "monthly"


SERIES = {
    "DGS10": Frequency.DAILY,  # 10-year Treasury constant maturity
    "DGS3MO": Frequency.DAILY,  # 3-month Treasury constant maturity
    "DFF": Frequency.DAILY,  # effective federal funds rate
    "CPIAUCSL": Frequency.MONTHLY,  # CPI, all urban consumers, seasonally adjusted
    "UNRATE": Frequency.MONTHLY,  # unemployment rate
}


def available_dates(dates: pd.DatetimeIndex, freq: Frequency) -> pd.DatetimeIndex:
    """First date a value can be used without look-ahead.

    Daily rates are published the next business day; a monthly value for
    month M is used from the last day of M+1, after its release.
    """
    if freq is Frequency.DAILY:
        return dates + pd.offsets.BDay(1)
    return dates + pd.offsets.MonthEnd(2)


def parse(text: str, series_id: str, freq: Frequency) -> pd.DataFrame:
    """Parse a fredgraph CSV; older files mark missing values with '.'."""
    raw = pd.read_csv(io.StringIO(text), na_values=["."])
    if list(raw.columns) != ["observation_date", series_id]:
        raise ValueError(f"unexpected columns: {list(raw.columns)}")
    raw = raw.dropna()
    dates = pd.DatetimeIndex(pd.to_datetime(raw["observation_date"])).as_unit("us")
    return pd.DataFrame(
        {
            "series": series_id,
            "date": dates,
            "value": raw[series_id].astype("float64").to_numpy(),
            "available_date": available_dates(dates, freq),
        }
    )


def download(series_id: str) -> pd.DataFrame:
    """Fetch and parse a series; an error page fails parsing and is retried."""

    def call() -> pd.DataFrame:
        with urllib.request.urlopen(FREDGRAPH_URL.format(series_id), timeout=60) as resp:
            body: bytes = resp.read()
        return parse(body.decode("utf-8"), series_id, SERIES[series_id])

    return with_retries(call, series_id)


def update_series(series_id: str, root: Path) -> None:
    """Refetch the full series into `<root>/macro/<series_id>.parquet`; it is small."""
    write_parquet_atomic(download(series_id), root / "macro" / f"{series_id}.parquet")
