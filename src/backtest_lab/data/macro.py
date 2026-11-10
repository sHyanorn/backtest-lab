"""FRED macro series from the keyless fredgraph CSV download (see D007, D010)."""

import io
import urllib.request
from enum import StrEnum
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from backtest_lab.data.fetch import with_retries
from backtest_lab.data.store import macro_file, write_parquet_atomic

FREDGRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"


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

# Monthly releases published after the end of the following month, from ALFRED
# vintages 1998-2026 (D010). October 2025 was never published and is absent.
LATE_RELEASES = {("UNRATE", "2025-09-01"): "2025-11-20"}


def available_dates(dates: pd.DatetimeIndex, freq: Frequency) -> pd.DatetimeIndex:
    """First date a value can be used without look-ahead.

    Daily rates are published the next Federal Reserve business day; a monthly
    value for month M is used from the last day of M+1, after its release,
    except for releases that came later (see D010).
    """
    if freq is Frequency.DAILY:
        if dates.empty:
            return dates
        holidays = USFederalHolidayCalendar().holidays(
            dates.min(), dates.max() + pd.Timedelta(days=14)
        )
        days = np.busday_offset(
            dates.to_numpy().astype("datetime64[D]"),
            1,
            roll="forward",
            holidays=holidays.to_numpy().astype("datetime64[D]"),
        )
        return pd.DatetimeIndex(days).as_unit("us")
    return dates + pd.offsets.MonthEnd(2)


def parse(text: str, series_id: str, freq: Frequency) -> pd.DataFrame:
    """Parse a fredgraph CSV; older files mark missing values with '.'."""
    raw = pd.read_csv(io.StringIO(text), na_values=["."])
    if list(raw.columns) != ["observation_date", series_id]:
        raise ValueError(f"unexpected columns: {list(raw.columns)}")
    raw = raw.dropna()
    dates = pd.DatetimeIndex(pd.to_datetime(raw["observation_date"])).as_unit("us")
    df = pd.DataFrame(
        {
            "series": series_id,
            "date": dates,
            "value": raw[series_id].astype("float64").to_numpy(),
            "available_date": available_dates(dates, freq),
        }
    )
    for (sid, obs), released in LATE_RELEASES.items():
        if sid == series_id:
            df.loc[df["date"] == pd.Timestamp(obs), "available_date"] = pd.Timestamp(released)
    return df


def download(series_id: str) -> pd.DataFrame:
    """Fetch and parse a series; an error page fails parsing and is retried."""

    def call() -> pd.DataFrame:
        with urllib.request.urlopen(FREDGRAPH_URL.format(series_id), timeout=60) as resp:
            body: bytes = resp.read()
        return parse(body.decode("utf-8"), series_id, SERIES[series_id])

    return with_retries(call, series_id)


def update_series(series_id: str, root: Path) -> None:
    """Refetch the full series into the raw directory `root`; it is small."""
    write_parquet_atomic(download(series_id), macro_file(root, series_id))
