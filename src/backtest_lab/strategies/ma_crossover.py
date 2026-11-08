"""Moving-average crossover."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest_lab.strategies.base import MarketData


@dataclass(frozen=True)
class MovingAverageCrossover:
    """Long when the fast average is above the slow one; flat or short otherwise."""

    ticker: str = "SPY"
    fast: int = 50
    slow: int = 200
    allow_short: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.fast < self.slow:
            raise ValueError("need 1 <= fast < slow")

    @property
    def warmup(self) -> int:
        return self.slow - 1

    def weights(self, data: MarketData) -> pd.DataFrame:
        close = data.prices.close[self.ticker]
        fast = close.rolling(self.fast).mean()
        slow = close.rolling(self.slow).mean()
        below = -1.0 if self.allow_short else 0.0
        w = pd.Series(np.where(fast > slow, 1.0, below), index=close.index)
        return w.where(slow.notna()).to_frame(self.ticker)
