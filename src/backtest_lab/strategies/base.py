"""Strategy interface."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

from backtest_lab.engine.backtest import Prices

SYMBOL = "symbol"  # dataclass field metadata key: what a string parameter names


def ticker_field(default: str) -> str:
    """A strategy field that names a ticker."""
    value: str = field(default=default, metadata={SYMBOL: "ticker"})
    return value


def series_field(default: str) -> str:
    """A strategy field that names a macro series."""
    value: str = field(default=default, metadata={SYMBOL: "series"})
    return value


@dataclass(frozen=True)
class MarketData:
    prices: Prices
    # Macro series by id, with columns date, value, available_date (D010).
    macro: Mapping[str, pd.DataFrame] = field(default_factory=dict)

    def macro_as_of(self, series_id: str) -> pd.Series:
        """Newest observation whose available_date is on or before each price date."""
        obs = self.macro[series_id].sort_values(["available_date", "date"])
        # A release of an older period after a newer one does not replace the newer value.
        obs = obs[obs["date"] >= obs["date"].cummax()]
        dates = pd.DataFrame({"t": self.prices.close.index})
        merged = pd.merge_asof(
            dates,
            obs[["available_date", "value"]].astype({"available_date": dates["t"].dtype}),
            left_on="t",
            right_on="available_date",
            direction="backward",
        )
        return pd.Series(merged["value"].to_numpy(), index=self.prices.close.index, name=series_id)


class Strategy(Protocol):
    """Maps market data to target weights decided at each close.

    Rows inside the warm-up are NaN. Signals must be scale-invariant in prices,
    since back-adjustment rescales history (D013).
    """

    @property
    def warmup(self) -> int:
        """Rows of history needed before the first signal.

        Listings and publication lags can delay the first signal further; align
        trials on `Result.start`, which accounts for both.
        """
        ...

    def weights(self, data: MarketData) -> pd.DataFrame: ...
