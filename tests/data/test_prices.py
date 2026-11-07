from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from backtest_lab.data.prices import UpdateKind, normalize, read_cached, update_ticker
from tests.factories import price_frame


def _yf_layout(df: pd.DataFrame) -> pd.DataFrame:
    raw = df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "adj_close": "Adj Close",
            "volume": "Volume",
            "dividends": "Dividends",
            "splits": "Stock Splits",
        }
    )
    raw.index = pd.DatetimeIndex(df.index).tz_localize("America/New_York")
    return raw


def test_normalize_drops_timezone_across_dst() -> None:
    raw = _yf_layout(price_frame(n=5, start="2024-03-07"))  # spans the March DST switch
    raw.index = pd.DatetimeIndex(raw.index).tz_convert("UTC")  # as if returned in another zone
    idx = pd.DatetimeIndex(normalize(raw).index)
    assert idx.tz is None
    assert list(idx.strftime("%Y-%m-%d")) == [
        "2024-03-07",
        "2024-03-08",
        "2024-03-11",
        "2024-03-12",
        "2024-03-13",
    ]
    assert idx.name == "date"


class FakeYahoo:
    def __init__(self, history: pd.DataFrame) -> None:
        self.history = history
        self.calls: list[date | None] = []

    def __call__(self, ticker: str, start: date | None, end: date) -> pd.DataFrame:
        self.calls.append(start)
        h = self.history[self.history.index < pd.Timestamp(end)]
        return h if start is None else h[h.index >= pd.Timestamp(start)]


def test_first_run_fetches_full_history(tmp_path: Path) -> None:
    yahoo = FakeYahoo(price_frame())
    assert update_ticker("SPY", tmp_path, fetch=yahoo, end=date(2030, 1, 1)) is UpdateKind.FULL
    assert yahoo.calls == [None]
    cached = read_cached(tmp_path / "prices" / "SPY.parquet")
    assert cached is not None
    pd.testing.assert_frame_equal(cached, yahoo.history, check_freq=False)


def test_second_run_only_fetches_recent_rows(tmp_path: Path) -> None:
    history = price_frame(n=80)
    first_end = history.index[60].date()
    yahoo = FakeYahoo(history)
    update_ticker("SPY", tmp_path, fetch=yahoo, end=first_end)
    kind = update_ticker("SPY", tmp_path, fetch=yahoo, end=date(2030, 1, 1))
    assert kind is UpdateKind.INCREMENTAL
    assert yahoo.calls[1] == history.index[50].date()
    cached = read_cached(tmp_path / "prices" / "SPY.parquet")
    assert cached is not None
    pd.testing.assert_frame_equal(cached, history, check_freq=False)


def test_rewritten_history_triggers_full_refetch(tmp_path: Path) -> None:
    history = price_frame(n=80)
    yahoo = FakeYahoo(history)
    update_ticker("SPY", tmp_path, fetch=yahoo, end=history.index[60].date())
    # A new dividend rescales every earlier adjusted close.
    yahoo.history = history.assign(adj_close=history["adj_close"] * 0.99)
    kind = update_ticker("SPY", tmp_path, fetch=yahoo, end=date(2030, 1, 1))
    assert kind is UpdateKind.FULL
    assert yahoo.calls[-1] is None
    cached = read_cached(tmp_path / "prices" / "SPY.parquet")
    assert cached is not None
    pd.testing.assert_frame_equal(cached, yahoo.history, check_freq=False)


def test_missing_overlap_rows_trigger_full_refetch(tmp_path: Path) -> None:
    history = price_frame(n=80)
    yahoo = FakeYahoo(history)
    update_ticker("SPY", tmp_path, fetch=yahoo, end=history.index[60].date())
    yahoo.history = history.drop(history.index[55])
    assert update_ticker("SPY", tmp_path, fetch=yahoo, end=date(2030, 1, 1)) is UpdateKind.FULL


def test_bars_on_or_after_end_are_excluded(tmp_path: Path) -> None:
    history = price_frame(n=20)
    end = history.index[15].date()
    update_ticker("SPY", tmp_path, fetch=FakeYahoo(history), end=end)
    cached = read_cached(tmp_path / "prices" / "SPY.parquet")
    assert cached is not None
    assert cached.index.max() < pd.Timestamp(end)


@pytest.mark.network
def test_download_spy() -> None:
    from backtest_lab.data.prices import download

    df = download("SPY", date(2024, 1, 2), date(2024, 1, 10))
    idx = pd.DatetimeIndex(df.index)
    assert idx[0] == pd.Timestamp("2024-01-02")
    assert idx.tz is None
