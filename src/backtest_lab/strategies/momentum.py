"""Time-series momentum (Moskowitz, Ooi and Pedersen, 2012)."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest_lab.strategies.base import MarketData


@dataclass(frozen=True)
class TimeSeriesMomentum:
    """Long after a positive trailing return; short (or flat) after a negative one."""

    ticker: str = "SPY"
    lookback: int = 252
    allow_short: bool = True

    def __post_init__(self) -> None:
        if self.lookback < 1:
            raise ValueError("lookback must be positive")

    @property
    def warmup(self) -> int:
        return self.lookback

    def weights(self, data: MarketData) -> pd.DataFrame:
        close = data.prices.close[self.ticker]
        trailing = close / close.shift(self.lookback) - 1
        w = pd.Series(np.sign(trailing.to_numpy()), index=close.index)
        if not self.allow_short:
            w = w.clip(lower=0.0)
        return w.to_frame(self.ticker)
