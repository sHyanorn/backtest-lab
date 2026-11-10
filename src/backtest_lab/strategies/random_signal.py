"""Random long or short positions: a control with no skill."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest_lab.strategies.base import MarketData, categorical_field, ticker_field


@dataclass(frozen=True)
class RandomSignal:
    """Fully long or short at random, redrawn every `hold` days.

    Directions are drawn in date order from `default_rng(seed)`, one per block of
    `hold` dates from the first price date, so a signal never depends on later data.
    """

    ticker: str = ticker_field("SPY")
    seed: int = categorical_field(0)
    hold: int = 5

    def __post_init__(self) -> None:
        if self.seed < 0 or self.hold < 1:
            raise ValueError("need seed >= 0 and hold >= 1")

    @property
    def warmup(self) -> int:
        return 0

    def weights(self, data: MarketData) -> pd.DataFrame:
        close = data.prices.close[self.ticker]
        n = len(close)
        draws = np.random.default_rng(self.seed).random(-(-n // self.hold))
        direction = np.repeat(np.where(draws < 0.5, -1.0, 1.0), self.hold)[:n]
        return pd.Series(direction, index=close.index).where(close.notna()).to_frame(self.ticker)
