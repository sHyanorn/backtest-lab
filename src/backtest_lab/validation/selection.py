"""Sharpe ratios of trial columns and selection of the best trial."""

import math
from typing import overload

import numpy as np
import numpy.typing as npt

from backtest_lab.engine.metrics import ANNUALIZATION, ZERO_TOL

type Matrix = npt.NDArray[np.float64]


def daily_sharpe_ratios(returns: npt.ArrayLike) -> Matrix:
    """Daily (non-annualized) Sharpe ratio of each column; NaN for a degenerate column."""
    x = np.asarray(returns, dtype=np.float64)
    if x.ndim != 2:
        raise ValueError("returns must be two-dimensional")
    if len(x) < 2:
        return np.full(x.shape[1], np.nan)
    std = x.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(std >= ZERO_TOL, x.mean(axis=0) / std, np.nan)


def ranking_daily_sharpe(returns: npt.ArrayLike) -> Matrix:
    """Daily Sharpe ratios with NaN counted as 0, as in rankings (METHODS.md, Conventions)."""
    return np.nan_to_num(daily_sharpe_ratios(returns), nan=0.0)


def best_trial(returns: npt.ArrayLike) -> int:
    """Column with the highest Sharpe ratio; ties go to the first in grid order."""
    return int(np.argmax(ranking_daily_sharpe(returns)))


@overload
def annualize(daily_sharpe: float) -> float: ...
@overload
def annualize(daily_sharpe: Matrix) -> Matrix: ...
def annualize(daily_sharpe: float | Matrix) -> float | Matrix:
    """The annualized Sharpe ratio: sqrt(A) times the daily one."""
    return math.sqrt(ANNUALIZATION) * daily_sharpe
