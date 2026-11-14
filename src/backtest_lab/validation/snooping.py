"""Data-snooping tests of a grid against a benchmark: White's Reality Check, Hansen's
SPA and Romano and Wolf's StepM on one stationary bootstrap (METHODS.md Section 8).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt

from backtest_lab.engine.metrics import ZERO_TOL

type Vector = npt.NDArray[np.float64]
type Matrix = npt.NDArray[np.float64]
type Indices = npt.NDArray[np.int64]

ALPHA = 0.05
CHUNK = 500  # resamples drawn at a time, to bound memory


class Criterion(StrEnum):
    SHARPE = "sharpe_difference"
    MEAN = "mean_difference"


def block_indices(new: npt.NDArray[np.bool_], starts: Indices, t: int) -> Indices:
    """Day indices of stationary-bootstrap resamples, one per row.

    Day i of a resample is `starts[i]` where `new[i]` (and always on day 0), otherwise
    the day after day i - 1, with the last day followed by the first.
    """
    pos = np.arange(new.shape[1])
    first = np.where(new | (pos == 0), pos, 0)
    block_start = np.maximum.accumulate(first, axis=1)
    return (np.take_along_axis(starts, block_start, axis=1) + pos - block_start) % t


def resample_indices(t: int, mean_block: float, reps: int, rng: np.random.Generator) -> Indices:
    """`reps` stationary-bootstrap resamples of `t` days with mean block length `mean_block`."""
    if mean_block < 1:
        raise ValueError("the mean block length must be at least 1")
    new = rng.random((reps, t)) < 1 / mean_block
    return block_indices(new, rng.integers(t, size=(reps, t)), t)


def resampled_means(columns: Matrix, mean_block: float, reps: int, seed: int) -> Matrix:
    """Column means of `reps` stationary-bootstrap resamples of the rows, reps x columns.

    A resample enters only through how often it draws each day.
    """
    t = len(columns)
    rng = np.random.default_rng(seed)
    out = np.empty((reps, columns.shape[1]))
    for lo in range(0, reps, CHUNK):
        n = min(CHUNK, reps - lo)
        idx = resample_indices(t, mean_block, n, rng)
        counts = np.bincount((idx + t * np.arange(n)[:, None]).ravel(), minlength=n * t)
        out[lo : lo + n] = counts.reshape(n, t) @ columns / t
    return out


def bootstrap_variance(psi: Matrix, mean_block: float) -> Vector:
    """T times the variance of each column's mean implied by the stationary bootstrap.

    Hansen (2005, Section 3): the autocovariances weighted by
    k(T, i) = (1 - i/T) (1 - q)^i + (i/T) (1 - q)^(T - i), q = 1 / mean_block.
    """
    t = len(psi)
    q = 1 / mean_block
    d = psi - psi.mean(axis=0)
    spectrum = np.fft.rfft(d, n=2 * t, axis=0)
    acov = np.fft.irfft(spectrum.real**2 + spectrum.imag**2, n=2 * t, axis=0)[:t] / t
    lag = np.arange(1, t)
    kernel = (1 - lag / t) * (1 - q) ** lag + (lag / t) * (1 - q) ** (t - lag)
    variance: Vector = acov[0] + 2 * kernel @ acov[1:]
    return variance


def _sharpe(mean: Matrix, mean_sq: Matrix, t: int) -> Matrix:
    """Daily Sharpe ratios from first and second moments; 0 for a degenerate series."""
    sd = np.sqrt(np.maximum(mean_sq - mean**2, 0.0) * t / (t - 1))
    safe = np.where(sd >= ZERO_TOL, sd, 1.0)
    out: Matrix = np.where(sd >= ZERO_TOL, mean / safe, 0.0)
    return out


def _sharpe_influence(y: Matrix) -> Matrix:
    """Delta-method influence series of the daily Sharpe ratio of each column."""
    mean, sd = y.mean(axis=0), y.std(axis=0, ddof=1)
    safe = np.where(sd >= ZERO_TOL, sd, 1.0)
    dev = y - mean
    phi = dev / safe - mean / (2 * safe**3) * (dev**2 - safe**2)
    out: Matrix = np.where(sd >= ZERO_TOL, phi, 0.0)
    return out


def _statistics(means: Matrix, criterion: Criterion, n: int, t: int) -> Matrix:
    """f for each setting from the means of [x, x^2, b, b^2, x - b] (rows: samples)."""
    if criterion is Criterion.MEAN:
        return means[:, 2 * n + 2 :]
    x = _sharpe(means[:, :n], means[:, n : 2 * n], t)
    b = _sharpe(means[:, 2 * n : 2 * n + 1], means[:, 2 * n + 1 : 2 * n + 2], t)
    return x - b


def reality_check(f: Vector, fb: Matrix, t: int) -> float:
    """White's (2000) p-value: the share of resamples whose recentred maximum exceeds the
    statistic's."""
    v = math.sqrt(t) * f.max()
    vb = (math.sqrt(t) * (fb - f)).max(axis=1)
    return float(np.mean(vb > v))


@dataclass(frozen=True)
class SpaPValues:
    lower: float
    consistent: float
    upper: float


def spa(f: Vector, fb: Matrix, omega: Vector, t: int) -> tuple[float, SpaPValues]:
    """Hansen's (2005) statistic and its lower, consistent and upper p-values.

    Every resample is studentized with the same `omega` as the statistic.
    """
    rt = math.sqrt(t)
    z = rt * f / omega
    statistic = max(0.0, float(z.max()))
    centred = rt * (fb - f) / omega
    consistent = np.where(z < -math.sqrt(2 * math.log(math.log(t))), f, 0.0)

    def p(mu: Vector) -> float:
        tb = np.maximum((centred + rt * mu / omega).max(axis=1), 0.0)
        return float(np.mean(tb > statistic))

    return statistic, SpaPValues(p(np.minimum(f, 0.0)), p(consistent), p(np.zeros_like(f)))


def stepm(f: Vector, fb: Matrix, omega: Vector, t: int, alpha: float = ALPHA) -> list[int]:
    """Settings rejected by Romano and Wolf's (2005) studentized StepM at FWER `alpha`,
    with `omega` from the data in every resample."""
    rt = math.sqrt(t)
    z = rt * f / omega
    centred = rt * (fb - f) / omega
    rejected = np.zeros(len(f), dtype=bool)
    while not rejected.all():
        active = ~rejected
        d = np.quantile(centred[:, active].max(axis=1), 1 - alpha, method="inverted_cdf")
        new = active & (z > d)
        if not new.any():
            break
        rejected |= new
    return [int(k) for k in np.flatnonzero(rejected)]


def holm(p: Sequence[float]) -> list[float]:
    """Holm's (1979) adjusted p-values, in the order given."""
    values = np.asarray(p, dtype=np.float64)
    m = len(values)
    order = np.argsort(values, kind="stable")
    adjusted = np.maximum.accumulate(np.minimum(1.0, (m - np.arange(m)) * values[order]))
    out = np.empty(m)
    out[order] = adjusted
    return [float(v) for v in out]


@dataclass(frozen=True)
class Comparison:
    """The tests of one family: one criterion over every setting of a grid."""

    criterion: Criterion
    statistic: Vector  # f for each setting
    omega: Vector  # standard deviation of sqrt(T) f implied by the bootstrap
    studentized: list[int]  # settings in the SPA and StepM: omega at least ZERO_TOL
    reality_check: float
    spa_statistic: float
    spa: SpaPValues
    stepm: list[int]  # rejected settings


def compare(
    x: Matrix, b: Vector, *, mean_block: float, reps: int, seed: int, alpha: float = ALPHA
) -> dict[Criterion, Comparison]:
    """Every setting (column of `x`) against the benchmark `b` under both criteria, on one
    set of resamples of whole days."""
    t, n = x.shape
    if b.shape != (t,) or not (np.isfinite(x).all() and np.isfinite(b).all()):
        raise ValueError("need finite returns with one benchmark return per row")
    bc = b[:, None]
    columns = np.hstack([x, x**2, bc, bc**2, x - bc])
    data = columns.mean(axis=0, keepdims=True)
    resampled = resampled_means(columns, mean_block, reps, seed)
    psi = {
        Criterion.SHARPE: _sharpe_influence(x) - _sharpe_influence(bc),
        Criterion.MEAN: x - bc,
    }
    out = {}
    for criterion in Criterion:
        f = _statistics(data, criterion, n, t)[0]
        fb = _statistics(resampled, criterion, n, t)
        omega = np.sqrt(bootstrap_variance(psi[criterion], mean_block))
        keep = omega >= ZERO_TOL
        if keep.any():
            stat, pvalues = spa(f[keep], fb[:, keep], omega[keep], t)
            rejected = np.flatnonzero(keep)[stepm(f[keep], fb[:, keep], omega[keep], t, alpha)]
        else:  # every setting is the benchmark
            stat, pvalues, rejected = 0.0, SpaPValues(1.0, 1.0, 1.0), np.array([], dtype=int)
        out[criterion] = Comparison(
            criterion=criterion,
            statistic=f,
            omega=omega,
            studentized=[int(k) for k in np.flatnonzero(keep)],
            reality_check=reality_check(f, fb, t),
            spa_statistic=stat,
            spa=pvalues,
            stepm=[int(k) for k in rejected],
        )
    return out
