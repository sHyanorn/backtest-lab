"""Asset rotation conditioned on the Treasury yield curve."""

from dataclasses import dataclass

import pandas as pd

from backtest_lab.strategies.base import MarketData, series_field, ticker_field


@dataclass(frozen=True)
class RateRotation:
    """Hold `risk_on` while the 10-year minus 3-month spread is above `threshold`
    (percentage points, averaged over `smoothing` days), else `risk_off`.

    Uses only rates published by each close (D010).
    """

    risk_on: str = ticker_field("SPY")
    risk_off: str = ticker_field("IEF")
    long_rate: str = series_field("DGS10")
    short_rate: str = series_field("DGS3MO")
    threshold: float = 0.0
    smoothing: int = 1

    def __post_init__(self) -> None:
        if self.smoothing < 1:
            raise ValueError("smoothing must be positive")
        # One ticker for both would collapse the weights into one column, the risk-off one.
        if self.risk_on == self.risk_off:
            raise ValueError("risk_on and risk_off must differ")

    @property
    def warmup(self) -> int:
        return self.smoothing - 1

    def weights(self, data: MarketData) -> pd.DataFrame:
        spread = data.macro_as_of(self.long_rate) - data.macro_as_of(self.short_rate)
        smooth = spread.rolling(self.smoothing).mean()
        listed = data.prices.close[[self.risk_on, self.risk_off]].notna().all(axis=1)
        on = (smooth > self.threshold).astype("float64").where(smooth.notna() & listed)
        return pd.DataFrame({self.risk_on: on, self.risk_off: 1.0 - on})
