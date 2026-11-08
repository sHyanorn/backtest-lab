"""Example strategies."""

from backtest_lab.strategies.base import MarketData, Strategy
from backtest_lab.strategies.ma_crossover import MovingAverageCrossover
from backtest_lab.strategies.mean_reversion import MeanReversion
from backtest_lab.strategies.momentum import TimeSeriesMomentum
from backtest_lab.strategies.rate_rotation import RateRotation

__all__ = [
    "MarketData",
    "MeanReversion",
    "MovingAverageCrossover",
    "RateRotation",
    "Strategy",
    "TimeSeriesMomentum",
]
