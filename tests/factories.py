"""Synthetic market data for tests."""

import numpy as np
import pandas as pd

from backtest_lab.data.store import PRICE_COLUMNS
from backtest_lab.engine.backtest import Prices
from backtest_lab.strategies import MarketData


def price_frame(
    n: int = 60, start: str = "2024-01-02", seed: int = 0, price: float = 100.0
) -> pd.DataFrame:
    """Clean daily bars in the normalized layout, with one dividend."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n).as_unit("us").rename("date")
    close = price * np.exp(np.cumsum(rng.normal(0.0, 0.01, n)))
    open_ = close * (1 + rng.normal(0.0, 0.002, n))
    high = np.maximum(open_, close) * 1.005
    low = np.minimum(open_, close) * 0.995
    dividends = np.zeros(n)
    div_day = n // 2
    dividends[div_day] = 0.5
    # Yahoo back-adjusts: rows before an ex-dividend date are scaled by 1 - D / C[t-1].
    factor = np.ones(n)
    factor[:div_day] = 1 - dividends[div_day] / close[div_day - 1]
    df = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "adj_close": close * factor,
            "volume": rng.integers(1_000, 10_000, n).astype("float64"),
            "dividends": dividends,
            "splits": np.zeros(n),
        },
        index=dates,
    )
    return df[PRICE_COLUMNS]


def synthetic_market(
    n: int = 300,
    tickers: tuple[str, ...] = ("SPY",),
    seed: int = 0,
    drift: float | tuple[float, ...] = 0.0,
) -> MarketData:
    """Random-walk opens and closes for `tickers` (daily log drift each), no macro data."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2000-01-03", periods=n).as_unit("us")
    k = len(tickers)
    close = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(drift, 0.01, (n, k)), axis=0)),
        index=dates,
        columns=list(tickers),
    )
    open_ = (close.shift(1) * np.exp(rng.normal(0.0, 0.003, (n, k)))).fillna(close)
    return MarketData(prices=Prices(open=open_, close=close))
