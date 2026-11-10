"""Probabilistic and deflated Sharpe ratios, minimum track record length and minimum
backtest length (METHODS.md Sections 5 and 6).

Sharpe ratios are non-annualized unless stated otherwise; kurtosis is raw (3 for a
normal distribution).
"""

import math
from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import numpy.typing as npt

from backtest_lab.engine.metrics import ZERO_TOL

EULER_GAMMA = 0.5772156649015329
_NORMAL = NormalDist()


@dataclass(frozen=True)
class SharpeMoments:
    sharpe: float  # non-annualized, ddof = 1
    skewness: float  # population moments
    kurtosis: float  # raw, population moments
    n: int


def sharpe_moments(returns: npt.ArrayLike) -> SharpeMoments:
    """Sharpe ratio, skewness and raw kurtosis of one return series; NaN if degenerate."""
    r = np.asarray(returns, dtype=np.float64)
    if r.ndim != 1 or len(r) < 2 or not np.isfinite(r).all():
        raise ValueError("need at least two finite returns")
    if r.std(ddof=1) < ZERO_TOL:
        return SharpeMoments(math.nan, math.nan, math.nan, len(r))
    centred = r - r.mean()
    m2 = float(np.mean(centred**2))
    return SharpeMoments(
        sharpe=float(r.mean() / r.std(ddof=1)),
        skewness=float(np.mean(centred**3)) / m2**1.5,
        kurtosis=float(np.mean(centred**4)) / m2**2,
        n=len(r),
    )


def expected_max_z(n_trials: float) -> float:
    """e_N: large-N approximation to the expected maximum of N standard normals.

    Negative below N = 1.2836 and -inf at N = 1; callers clip it at 0.
    """
    if n_trials < 1:
        raise ValueError("need at least one trial")
    if n_trials == 1:
        return -math.inf
    return (1 - EULER_GAMMA) * _NORMAL.inv_cdf(1 - 1 / n_trials) + EULER_GAMMA * _NORMAL.inv_cdf(
        1 - 1 / (n_trials * math.e)
    )


def expected_max_sharpe(n_trials: float, variance: float) -> float:
    """SR_0: expected best Sharpe of N skill-less trials whose Sharpe ratios have
    `variance` across trials (Bailey and Lopez de Prado, 2014, Eq. 1)."""
    return math.sqrt(variance) * max(expected_max_z(n_trials), 0.0)


def _mean_off_diagonal(returns: npt.ArrayLike, power: int) -> float:
    """Mean of rho_ij ** power over the pairs of distinct columns, clipped to [0, 1].

    Degenerate columns are skipped; with fewer than two others the result is 0.
    """
    x = np.asarray(returns, dtype=np.float64)
    live = x[:, x.std(axis=0, ddof=1) >= ZERO_TOL] if len(x) >= 2 else x[:, :0]
    n = live.shape[1]
    if n < 2:
        return 0.0
    corr = np.corrcoef(live, rowvar=False) ** power
    mean = (corr.sum() - np.trace(corr)) / (n * (n - 1))
    return float(np.clip(mean, 0.0, 1.0))


def average_correlation(returns: npt.ArrayLike) -> float:
    """Mean pairwise correlation of the columns, clipped to [0, 1]."""
    return _mean_off_diagonal(returns, 1)


def mean_squared_correlation(returns: npt.ArrayLike) -> float:
    """Mean squared pairwise correlation of the columns: Var(lambda) / N of the
    correlation matrix's eigenvalues (Nyholt, 2004)."""
    return _mean_off_diagonal(returns, 2)


def effective_trials(correlation: float, n_trials: int) -> float:
    """N-hat = rho + (1 - rho) N. With the average correlation this is Bailey and Lopez
    de Prado (2014, Appendix A.3); with the mean squared correlation, Nyholt (2004)."""
    rho = min(max(correlation, 0.0), 1.0)
    return rho + (1 - rho) * n_trials


def _sharpe_dispersion(sharpe: float, skewness: float, kurtosis: float) -> float:
    return math.sqrt(1 - skewness * sharpe + (kurtosis - 1) / 4 * sharpe**2)


def probabilistic_sharpe_ratio(
    sharpe: float, benchmark: float, n: float, skewness: float, kurtosis: float
) -> float:
    """PSR(SR*): probability that the true Sharpe ratio exceeds `benchmark` after `n`
    observations (Eq. 11)."""
    if not all(map(math.isfinite, (sharpe, benchmark, skewness, kurtosis))):
        return math.nan
    z = (sharpe - benchmark) * math.sqrt(n - 1) / _sharpe_dispersion(sharpe, skewness, kurtosis)
    return _NORMAL.cdf(z)


def deflated_sharpe_ratio(
    sharpe: float, variance: float, n_trials: float, n: float, skewness: float, kurtosis: float
) -> float:
    """DSR: PSR at the expected best Sharpe of `n_trials` independent skill-less trials."""
    benchmark = expected_max_sharpe(n_trials, variance)
    return probabilistic_sharpe_ratio(sharpe, benchmark, n, skewness, kurtosis)


def min_track_record_length(
    sharpe: float, benchmark: float, skewness: float, kurtosis: float, alpha: float = 0.05
) -> float:
    """Observations needed for PSR(benchmark) to reach 1 - alpha (Eq. 13); NaN unless
    sharpe > benchmark."""
    if not sharpe > benchmark:
        return math.nan
    z = _NORMAL.inv_cdf(1 - alpha)
    return 1 + _sharpe_dispersion(sharpe, skewness, kurtosis) ** 2 * (z / (sharpe - benchmark)) ** 2


def min_backtest_length(n_trials: float, target: float) -> float:
    """Years of data before the expected best annualized Sharpe of `n_trials` skill-less
    trials falls to `target` (Bailey et al., 2014, Theorem 3.1); NaN unless target > 0."""
    if not target > 0:
        return math.nan
    return (max(expected_max_z(n_trials), 0.0) / target) ** 2


def min_backtest_length_bound(n_trials: float, target: float) -> float:
    """The upper bound 2 ln N / target^2 on MinBTL."""
    return 2 * math.log(n_trials) / target**2
