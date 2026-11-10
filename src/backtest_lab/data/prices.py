"""Daily prices from Yahoo Finance with an incremental Parquet cache (see D006)."""

from collections.abc import Callable
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

from backtest_lab.data.fetch import FetchError, with_retries
from backtest_lab.data.store import PRICE_COLUMNS, price_file, write_parquet_atomic

EXCHANGE_TZ = ZoneInfo("America/New_York")
_YF_COLUMNS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "splits",
}
# Rows refetched on an incremental update; they must match the cache or the
# history was rewritten by a new split or dividend and is fetched in full.
OVERLAP_ROWS = 10
REL_TOL = 1e-5

type Fetcher = Callable[[str, date | None, date], pd.DataFrame]


class UpdateKind(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"


def normalize(raw: pd.DataFrame) -> pd.DataFrame:
    """Rename yfinance columns and turn the exchange-local timestamps into trading dates."""
    missing = set(_YF_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"missing columns: {sorted(missing)}")
    df = raw[list(_YF_COLUMNS)].rename(columns=_YF_COLUMNS).astype("float64")
    idx = pd.DatetimeIndex(raw.index)
    if idx.tz is not None:
        idx = idx.tz_convert(EXCHANGE_TZ).tz_localize(None)
    df.index = idx.normalize().as_unit("us").rename("date")
    return df.sort_index()


def download(ticker: str, start: date | None, end: date) -> pd.DataFrame:
    """Fetch [start, end) from Yahoo; full history when `start` is None."""

    def call() -> pd.DataFrame:
        t = yf.Ticker(ticker)
        if start is None:
            raw = t.history(period="max", end=end.isoformat(), auto_adjust=False)
        else:
            raw = t.history(start=start.isoformat(), end=end.isoformat(), auto_adjust=False)
        if raw.empty:
            raise ValueError("no rows returned")
        return normalize(raw)

    return with_retries(call, ticker)


def exchange_today() -> date:
    """Today's date in New York; bars from today may be incomplete and are excluded."""
    return datetime.now(EXCHANGE_TZ).date()


def read_cached(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    return df.set_index("date")[PRICE_COLUMNS]


def _consistent(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    cols = ["close", "adj_close"]
    return bool(np.allclose(a[cols].to_numpy(), b[cols].to_numpy(), rtol=REL_TOL, atol=0.0))


def update_ticker(
    ticker: str,
    root: Path,
    *,
    fetch: Fetcher = download,
    end: date | None = None,
    full: bool = False,
) -> UpdateKind:
    """Bring the ticker's file under the raw directory `root` up to date."""
    end = end or exchange_today()
    path = price_file(root, ticker)
    cached = None if full else read_cached(path)
    kind = UpdateKind.FULL
    if cached is None or len(cached) < OVERLAP_ROWS:
        data = fetch(ticker, None, end)
    else:
        start = cached.index[-OVERLAP_ROWS].date()
        recent = fetch(ticker, start, end)
        overlap = cached.index.intersection(recent.index)
        if len(overlap) < OVERLAP_ROWS or not _consistent(cached.loc[overlap], recent.loc[overlap]):
            data = fetch(ticker, None, end)
        else:
            data = pd.concat([cached[cached.index < recent.index[0]], recent])
            kind = UpdateKind.INCREMENTAL
    if data.index.has_duplicates:
        raise FetchError(ticker, "duplicate dates in fetched data")
    out = data.reset_index()
    out.insert(0, "ticker", ticker)
    write_parquet_atomic(out, path)
    return kind
