import math
from typing import cast

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest

from backtest_lab.validation.selection import daily_sharpe_ratios
from backtest_lab.validation.sharpe_stats import (
    average_correlation,
    deflated_sharpe_ratio,
    effective_trials,
    expected_max_sharpe,
    expected_max_z,
    mean_squared_correlation,
    min_backtest_length,
    min_backtest_length_bound,
    min_track_record_length,
    probabilistic_sharpe_ratio,
    sharpe_moments,
)

# Section 5: deflated Sharpe ratio, Bailey and Lopez de Prado (2014) pp. 9-10


def test_dsr_paper_example() -> None:
    variance, sr, t = 1 / (2 * 250), 2.5 / math.sqrt(250), 1250
    assert expected_max_sharpe(100, variance) == pytest.approx(0.1132, abs=1e-4)
    assert deflated_sharpe_ratio(sr, variance, 100, t, -3, 10) == pytest.approx(0.9004, abs=1e-4)
    assert deflated_sharpe_ratio(sr, variance, 46, t, -3, 10) == pytest.approx(0.9505, abs=1e-4)
    assert deflated_sharpe_ratio(sr, variance, 88, t, 0, 3) == pytest.approx(0.9505, abs=1e-4)


def test_effective_trials() -> None:
    assert effective_trials(0.0, 100) == 100
    assert effective_trials(1.0, 100) == 1
    assert effective_trials(0.5, 100) == 50.5
    assert effective_trials(-0.2, 100) == 100  # rho is clipped to [0, 1]


def test_expected_max_is_clipped_for_few_trials() -> None:
    assert expected_max_z(1.1) == pytest.approx(-0.318, abs=1e-3)
    assert expected_max_sharpe(1.1, 0.01) == 0.0
    assert expected_max_sharpe(1, 0.01) == 0.0
    assert expected_max_z(2) == pytest.approx(0.5198, abs=1e-4)


def test_average_correlation() -> None:
    rng = np.random.default_rng(0)
    base = rng.standard_normal((500, 1))
    same = np.hstack([base, 2 * base, np.zeros((500, 1))])  # the zero column is skipped
    assert average_correlation(same) == pytest.approx(1.0)
    assert average_correlation(rng.standard_normal((5000, 4))) < 0.05
    assert average_correlation(np.hstack([base, -base])) == 0.0  # clipped
    assert average_correlation(base) == 0.0


def test_mean_squared_correlation_gives_the_eigenvalue_estimate() -> None:
    rng = np.random.default_rng(0)
    n = 6
    x = rng.standard_normal((500, n)) @ rng.standard_normal((n, n))
    eigenvalues = np.linalg.eigvalsh(np.corrcoef(x, rowvar=False))
    nyholt = 1 + (n - 1) * (1 - eigenvalues.var(ddof=1) / n)
    assert effective_trials(mean_squared_correlation(x), n) == pytest.approx(nyholt)
    assert 1 < nyholt < n

    def n_hat(*columns: npt.NDArray[np.float64]) -> float:
        return effective_trials(mean_squared_correlation(np.hstack(columns)), len(columns))

    a = np.tile([1.0, -1.0, 1.0, -1.0], 25)[:, None]
    b = np.tile([1.0, 1.0, -1.0, -1.0], 25)[:, None]  # uncorrelated with a
    assert n_hat(a, b) == pytest.approx(2)
    assert n_hat(a, 2 * a) == pytest.approx(1)
    assert n_hat(a, a, b, b) == pytest.approx(3)  # two independent pairs: eigenvalues (2, 2, 0, 0)
    # An exact opposite is one trial here and two under the average correlation.
    assert n_hat(a, -a) == pytest.approx(1)
    assert effective_trials(average_correlation(np.hstack([a, -a])), 2) == 2
    assert mean_squared_correlation(a) == 0.0


def test_random_control() -> None:
    # SPEC Section 8: the best of 100 independent noise trials looks significant on
    # PSR(0) but not after deflation (N-hat = N by construction).
    dsr_significant = psr_significant = 0
    for seed in range(50):
        x = 0.01 * np.random.default_rng(seed).standard_normal((1000, 100))
        sr = daily_sharpe_ratios(x)
        best = sharpe_moments(x[:, int(np.argmax(sr))])
        psr = probabilistic_sharpe_ratio(best.daily_sharpe, 0, best.n, best.skewness, best.kurtosis)
        dsr = deflated_sharpe_ratio(
            best.daily_sharpe, float(np.var(sr, ddof=1)), 100, best.n, best.skewness, best.kurtosis
        )
        dsr_significant += dsr >= 0.95
        psr_significant += psr >= 0.95
    assert dsr_significant <= 2
    assert psr_significant >= 48


# Section 6: PSR and MinTRL, Bailey and Lopez de Prado (2012) pp. 10-11


@pytest.mark.parametrize(
    ("n", "skew", "kurt", "expected"),
    [(24, 0.0, 3.0, 0.982), (24, -2.448, 10.164, 0.913), (36, -2.448, 10.164, 0.953)],
)
def test_psr_paper_example(n: int, skew: float, kurt: float, expected: float) -> None:
    assert probabilistic_sharpe_ratio(0.458, 0, n, skew, kurt) == pytest.approx(expected, abs=1e-3)


@pytest.mark.parametrize(
    ("periods", "skew", "kurt", "years"),
    [(252, 0.0, 3.0, 2.73), (52, 0.0, 3.0, 2.83), (12, 0.0, 3.0, 3.24), (12, -0.72, 5.78, 4.99)],
)
def test_min_trl_paper_example(periods: int, skew: float, kurt: float, years: float) -> None:
    sr, benchmark = 2 / math.sqrt(periods), 1 / math.sqrt(periods)
    trl = min_track_record_length(sr, benchmark, skew, kurt, alpha=0.05)
    assert trl / periods == pytest.approx(years, abs=0.01)


def test_min_trl_needs_sharpe_above_benchmark() -> None:
    assert math.isnan(min_track_record_length(0.05, 0.05, 0, 3, alpha=0.05))


# Section 6: MinBTL, Bailey, Borwein, Lopez de Prado and Zhu (2014) pp. 9-11


def test_min_btl_paper_example() -> None:
    assert min_backtest_length(45, 1.0) == pytest.approx(4.998, abs=1e-3)
    assert min_backtest_length_bound(45, 1.0) == pytest.approx(7.613, abs=1e-3)
    assert expected_max_z(10) == pytest.approx(1.5746, abs=1e-4)
    assert min_backtest_length(1.2, 1.0) == 0.0
    assert math.isnan(min_backtest_length(45, 0.0))


def test_consistency() -> None:
    sr, skew, kurt, n = 0.08, -0.5, 6.0, 900
    assert deflated_sharpe_ratio(sr, 0.01, 1, n, skew, kurt) == probabilistic_sharpe_ratio(
        sr, 0, n, skew, kurt
    )
    trl = min_track_record_length(sr, 0.02, skew, kurt, alpha=0.05)
    assert probabilistic_sharpe_ratio(sr, 0.02, trl, skew, kurt) == pytest.approx(0.95, abs=1e-12)


# Moments


def test_moments_match_pandas_after_bias_conversion() -> None:
    r = np.array([0.01, 0.10, -0.04, 0.02, 0.03, 0.02, 0.01, -0.10])
    n = len(r)
    m = sharpe_moments(r)
    s = pd.Series(r)
    g1 = cast(float, s.skew()) * (n - 2) / math.sqrt(n * (n - 1))  # adjusted to population
    g2 = cast(float, s.kurt()) * (n - 2) * (n - 3) / ((n - 1) * (n + 1)) - 6 / (n + 1)
    assert m.skewness == pytest.approx(g1, rel=1e-12)
    assert m.kurtosis == pytest.approx(g2 + 3, rel=1e-12)  # raw, not excess
    assert m.daily_sharpe == pytest.approx(r.mean() / r.std(ddof=1), rel=1e-15)
    assert m.n == n


def test_moments_of_a_constant_series_are_nan() -> None:
    m = sharpe_moments(np.full(10, 0.01))
    assert math.isnan(m.daily_sharpe) and math.isnan(m.kurtosis)
    assert math.isnan(probabilistic_sharpe_ratio(m.daily_sharpe, 0, m.n, m.skewness, m.kurtosis))
