"""Combinatorially symmetric cross-validation (CSCV) and the probability of backtest
overfitting (PBO), METHODS.md Section 4."""

import itertools
import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from backtest_lab.engine.metrics import ZERO_TOL

type Matrix = npt.NDArray[np.float64]


def n_combinations(blocks: int) -> int:
    return math.comb(blocks, blocks // 2)


def selection_logits(is_perf: Matrix, oos_perf: Matrix) -> Matrix:
    """Logit of the OOS relative rank of each row's IS winner.

    Rows are combinations, columns trials. The winner is the first column with the
    highest IS value; OOS ranks run from 1 (worst) to N with ties averaged.
    """
    rows = np.arange(len(is_perf))
    winner = np.argmax(is_perf, axis=1)
    value = oos_perf[rows, winner][:, None]
    rank = (oos_perf < value).sum(axis=1) + ((oos_perf == value).sum(axis=1) + 1) / 2
    omega = rank / (is_perf.shape[1] + 1)
    return np.asarray(np.log(omega / (1 - omega)), dtype=np.float64)


def _union_sharpe(members: Matrix, length: int, centre: Matrix, dev: Matrix, m2: Matrix) -> Matrix:
    """Sharpe ratio of each column over each union of blocks (rows of `members`).

    Uses per-block means as deviations `dev` from a per-column `centre` and per-block
    sums of squared deviations `m2`, so a constant column has zero variance up to
    rounding instead of the cancellation error of raw sums of squares.
    """
    k = members.sum(axis=1, keepdims=True)
    count = k * length
    dev_bar = (members @ dev) / k
    total_m2 = members @ m2 + length * (members @ dev**2) - count * dev_bar**2
    std = np.sqrt(np.maximum(total_m2, 0.0) / (count - 1))
    with np.errstate(divide="ignore", invalid="ignore"):
        sr = np.where(std >= ZERO_TOL, (centre + dev_bar) / std, np.nan)
    return np.nan_to_num(sr, nan=0.0)  # a NaN Sharpe ranks as 0


@dataclass(frozen=True)
class CSCV:
    logits: Matrix  # one per combination
    is_sharpe: Matrix  # IS Sharpe of each combination's winner, non-annualized
    oos_sharpe: Matrix  # OOS Sharpe of the same trial
    n_trials: int
    n_blocks: int

    @property
    def pbo(self) -> float:
        return float(np.mean(self.logits <= 0))

    @property
    def degradation_slope(self) -> float | None:
        """OLS slope of OOS on IS Sharpe across combinations; descriptive only."""
        x = self.is_sharpe - self.is_sharpe.mean()
        sxx = float(x @ x)
        return float(x @ self.oos_sharpe) / sxx if sxx > 0 else None

    @property
    def prob_oos_loss(self) -> float:
        return float(np.mean(self.oos_sharpe < 0))


def cscv(returns: npt.ArrayLike, blocks: int = 16) -> CSCV:
    """CSCV over all C(S, S/2) splits of S contiguous blocks; the earliest T mod S rows
    are dropped."""
    x = np.asarray(returns, dtype=np.float64)
    if x.ndim != 2 or blocks < 2 or blocks % 2:
        raise ValueError("need a 2-D matrix and an even number of blocks")
    t, n = x.shape
    length = t // blocks
    if length < 2 or n < 2:
        raise ValueError("need at least two rows per block and two trials")
    split = x[t - blocks * length :].reshape(blocks, length, n)
    centre = x[t - blocks * length :].mean(axis=0)
    means = split.mean(axis=1)
    m2 = ((split - means[:, None, :]) ** 2).sum(axis=1)
    dev = means - centre

    chosen = np.array(list(itertools.combinations(range(blocks), blocks // 2)))
    members = np.zeros((len(chosen), blocks))
    members[np.arange(len(chosen))[:, None], chosen] = 1.0
    is_perf = _union_sharpe(members, length, centre, dev, m2)
    oos_perf = _union_sharpe(1.0 - members, length, centre, dev, m2)

    rows = np.arange(len(members))
    winner = np.argmax(is_perf, axis=1)
    return CSCV(
        logits=selection_logits(is_perf, oos_perf),
        is_sharpe=is_perf[rows, winner],
        oos_sharpe=oos_perf[rows, winner],
        n_trials=n,
        n_blocks=blocks,
    )
