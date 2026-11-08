"""Mean reversion on a rolling z-score."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest_lab.strategies.base import MarketData


@dataclass(frozen=True)
class MeanReversion:
    """Short when price is `entry_z` deviations above its rolling mean, long when below."""

    ticker: str = "SPY"
    lookback: int = 20
    entry_z: float = 1.0
    allow_short: bool = True

    def __post_init__(self) -> None:
        if self.lookback < 2 or self.entry_z <= 0:
            raise ValueError("need lookback >= 2 and entry_z > 0")

    @property
    def warmup(self) -> int:
        return self.lookback - 1

    def weights(self, data: MarketData) -> pd.DataFrame:
        close = data.prices.close[self.ticker]
        mean = close.rolling(self.lookback).mean()
        std = close.rolling(self.lookback).std(ddof=1)
        z = (close - mean) / std.where(std > 0)
        above = -1.0 if self.allow_short else 0.0
        w = pd.Series(
            np.select([z > self.entry_z, z < -self.entry_z], [above, 1.0], 0.0), index=close.index
        )
        return w.where(mean.notna()).to_frame(self.ticker)
