"""Sharpe ratios of trial columns and selection of the best trial."""

import numpy as np
import numpy.typing as npt

from backtest_lab.engine.metrics import ANNUALIZATION, ZERO_TOL

type Matrix = npt.NDArray[np.float64]


def sharpe_ratios(returns: npt.ArrayLike) -> Matrix:
    """Non-annualized Sharpe ratio of each column; NaN for a degenerate column."""
    x = np.asarray(returns, dtype=np.float64)
    if x.ndim != 2:
        raise ValueError("returns must be two-dimensional")
    if len(x) < 2:
        return np.full(x.shape[1], np.nan)
    std = x.std(axis=0, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(std >= ZERO_TOL, x.mean(axis=0) / std, np.nan)


def ranking_sharpe(returns: npt.ArrayLike) -> Matrix:
    """Sharpe ratios with NaN counted as 0, as in rankings (METHODS.md, Conventions)."""
    return np.nan_to_num(sharpe_ratios(returns), nan=0.0)


def best_trial(returns: npt.ArrayLike) -> int:
    """Column with the highest Sharpe ratio; ties go to the first in grid order."""
    return int(np.argmax(ranking_sharpe(returns)))


def annualize(sharpe: float) -> float:
    return float(np.sqrt(ANNUALIZATION) * sharpe)
