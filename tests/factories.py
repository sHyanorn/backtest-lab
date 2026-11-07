"""Synthetic market data for tests."""

import numpy as np
import pandas as pd

from backtest_lab.data.prices import COLUMNS


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
    return df[COLUMNS]
