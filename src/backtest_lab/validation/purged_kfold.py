"""Purged and embargoed K-fold cross-validation (METHODS.md Section 3)."""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from backtest_lab.engine.backtest import INFORMATION_SPAN
from backtest_lab.engine.metrics import sharpe
from backtest_lab.validation.selection import best_trial

type Index = npt.NDArray[np.intp]


def default_embargo(n: int) -> int:
    """ceil(0.01 n) in integer arithmetic."""
    return -(-n // 100)


def information_intervals(n: int) -> tuple[Index, Index]:
    """[t0, t1] of each of `n` daily returns, in rows: a return is earned on row i from a
    target decided INFORMATION_SPAN rows earlier."""
    t1 = np.arange(n, dtype=np.intp)
    return t1 - INFORMATION_SPAN, t1


def kfold_splits(t0: Index, t1: Index, k: int, embargo: int) -> list[tuple[Index, Index]]:
    """(train, test) row indices for K contiguous, unshuffled test folds.

    A non-test row j stays in training only if t1[j] < min test t0 (purge) or
    t0[j] > max test t1 + embargo (embargo). Intervals are closed.
    """
    n = len(t0)
    if len(t1) != n or not 2 <= k <= n or embargo < 0:
        raise ValueError("need matching intervals, 2 <= k <= n and embargo >= 0")
    rows = np.arange(n, dtype=np.intp)
    splits = []
    for test in np.array_split(rows, k):
        lo, hi = t0[test].min(), t1[test].max()
        keep = (t1 < lo) | (t0 > hi + embargo)
        keep[test] = False
        splits.append((rows[keep], test))
    return splits


@dataclass(frozen=True)
class Fold:
    test_start: pd.Timestamp
    test_end: pd.Timestamp  # last test date
    n_train: int
    trial: int  # selected on the training rows
    train_sharpe: float  # annualized
    test_sharpe: float  # annualized


@dataclass(frozen=True)
class PurgedCV:
    folds: tuple[Fold, ...]
    embargo: int

    @property
    def score(self) -> float:
        """Mean test-fold Sharpe, annualized; a NaN fold counts as 0."""
        return float(np.mean(np.nan_to_num([f.test_sharpe for f in self.folds], nan=0.0)))

    @property
    def train_score(self) -> float:
        return float(np.mean(np.nan_to_num([f.train_sharpe for f in self.folds], nan=0.0)))

    @property
    def retention(self) -> float | None:
        """score / train_score, reported only when train_score is positive."""
        return self.score / self.train_score if self.train_score > 0 else None


def purged_cv(returns: pd.DataFrame, k: int = 10, embargo: int | None = None) -> PurgedCV:
    """Select the best trial on each fold's purged training rows; score it on the test fold."""
    x = returns.to_numpy(dtype=np.float64)
    h = default_embargo(len(x)) if embargo is None else embargo
    folds = []
    for train, test in kfold_splits(*information_intervals(len(x)), k, h):
        if len(train) < 2:
            raise ValueError("a fold has fewer than two training rows")
        trial = best_trial(x[train])
        folds.append(
            Fold(
                test_start=pd.Timestamp(returns.index[test[0]]),
                test_end=pd.Timestamp(returns.index[test[-1]]),
                n_train=len(train),
                trial=trial,
                train_sharpe=sharpe(x[train, trial]),
                test_sharpe=sharpe(x[test, trial]),
            )
        )
    return PurgedCV(folds=tuple(folds), embargo=h)
