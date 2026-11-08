"""Example strategies."""

from collections.abc import Callable, Mapping
from types import MappingProxyType

from backtest_lab.strategies.base import MarketData, Strategy
from backtest_lab.strategies.ma_crossover import MovingAverageCrossover
from backtest_lab.strategies.mean_reversion import MeanReversion
from backtest_lab.strategies.momentum import TimeSeriesMomentum
from backtest_lab.strategies.rate_rotation import RateRotation

# Registry by name, used to serialize trials and to list strategies.
STRATEGIES: Mapping[str, Callable[..., Strategy]] = MappingProxyType(
    {
        "ma_crossover": MovingAverageCrossover,
        "mean_reversion": MeanReversion,
        "momentum": TimeSeriesMomentum,
        "rate_rotation": RateRotation,
    }
)

__all__ = [
    "STRATEGIES",
    "MarketData",
    "MeanReversion",
    "MovingAverageCrossover",
    "RateRotation",
    "Strategy",
    "TimeSeriesMomentum",
]
