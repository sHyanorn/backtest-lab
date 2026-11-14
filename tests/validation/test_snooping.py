"""Reality Check, SPA and StepM (METHODS.md Section 8)."""

import math

import numpy as np
import pytest
from arch.bootstrap import SPA, StepM

from backtest_lab.validation.snooping import (
    Criterion,
    block_indices,
    bootstrap_variance,
    compare,
    holm,
    reality_check,
    resample_indices,
    resampled_means,
    spa,
    stepm,
)


def _loop_indices(new: np.ndarray, starts: np.ndarray, t: int) -> np.ndarray:
    """Sullivan, Timmermann and White (1999, Appendix C), one day at a time."""
    out = np.empty_like(starts)
    for r in range(len(new)):
        out[r, 0] = starts[r, 0]
        for i in range(1, new.shape[1]):
            out[r, i] = starts[r, i] if new[r, i] else (out[r, i - 1] + 1) % t
    return out


def test_block_indices_follow_the_algorithm_and_wrap() -> None:
    rng = np.random.default_rng(0)
    t = 7
    new = rng.random((50, 30)) < 0.2
    starts = rng.integers(t, size=(50, 30))
    got = block_indices(new, starts, t)
    np.testing.assert_array_equal(got, _loop_indices(new, starts, t))
    assert (np.diff(got, axis=1) == 1 - t).any()  # a block ran past the last day


def test_blocks_have_the_mean_length() -> None:
    t, mean_block = 100_000, 10.0
    idx = resample_indices(t, mean_block, 1, np.random.default_rng(1))[0]
    starts = np.flatnonzero(np.r_[True, np.diff(idx) % t != 1])
    lengths = np.diff(np.r_[starts, t])[:-1]  # the last block is cut at t
    se = math.sqrt(mean_block * (mean_block - 1) / len(lengths))
    assert abs(lengths.mean() - mean_block) < 3 * se


def test_resampled_means_are_means_of_the_drawn_rows() -> None:
    rng = np.random.default_rng(2)
    columns = rng.normal(size=(40, 3))
    got = resampled_means(columns, 4.0, 1_200, seed=5)
    rng = np.random.default_rng(5)
    drawn = [resample_indices(40, 4.0, n, rng) for n in (500, 500, 200)]
    expected = np.vstack([columns[idx].mean(axis=1) for idx in drawn])
    np.testing.assert_allclose(got, expected, rtol=0, atol=1e-12)


def test_variance_is_the_bootstrap_variance_of_the_mean() -> None:
    # Hansen's closed form is the stationary bootstrap's own variance of sqrt(T) times
    # the mean (Politis and Romano, 1994).
    rng = np.random.default_rng(3)
    t = 40
    x = np.cumsum(rng.normal(size=t))[:, None] * 0.1 + rng.normal(size=(t, 1))
    means = resampled_means(x, 5.0, 200_000, seed=4)
    simulated = t * means.var()
    assert bootstrap_variance(x, 5.0)[0] == pytest.approx(simulated, rel=0.02)
    assert bootstrap_variance(x, 1.0)[0] == pytest.approx(x.var(), rel=1e-12)


def test_sharpe_difference_variance_matches_memmel() -> None:
    # iid normal returns with correlation rho: 2 - 2 rho + (SR1^2 + SR2^2 - 2 SR1 SR2 rho^2) / 2
    rng = np.random.default_rng(6)
    t, rho, sr1, sr2 = 400_000, 0.5, 0.5, 0.2
    z = rng.standard_normal((t, 2))
    x = sr1 + z[:, 0]
    b = sr2 + rho * z[:, 0] + math.sqrt(1 - rho**2) * z[:, 1]
    out = compare(x[:, None], b, mean_block=1.0, reps=1, seed=0)[Criterion.SHARPE]
    expected = 2 - 2 * rho + (sr1**2 + sr2**2 - 2 * sr1 * sr2 * rho**2) / 2
    assert out.omega[0] ** 2 == pytest.approx(expected, rel=0.01)
    assert abs(out.omega[0] ** 2 - (2 - 2 * rho)) > 0.1  # the Sharpe terms matter here


def test_sharpe_variance_has_the_skewness_term() -> None:
    # iid, sd 1, skewness 2, kurtosis 9: Var(sqrt(T) SR) = 1 - SR skew + SR^2 (kurt - 1) / 4
    # = 1 - 0.6 + 0.18 = 0.58 for SR = 0.3. The benchmark is independent with Sharpe 0: + 1.
    rng = np.random.default_rng(11)
    t, sr = 400_000, 0.3
    x = sr + rng.exponential(1.0, t) - 1.0
    b = rng.standard_normal(t)
    out = compare(x[:, None], b, mean_block=1.0, reps=1, seed=0)[Criterion.SHARPE]
    assert out.omega[0] ** 2 == pytest.approx(1.58, rel=0.03)


def test_reality_check_by_hand() -> None:
    t = 4
    f = np.array([0.1, -0.2])
    fb = np.array([[0.15, -0.2], [0.30, -0.1], [0.05, 0.1], [0.1, -0.3]])
    # sqrt(T) (fb - f) maxima: 0.1, 0.4, 0.6, 0; the statistic is 0.2.
    assert reality_check(f, fb, t) == 0.5


# Resampled deviations sqrt(T)(f* - f) / omega, with T = 100 and omega = 1.
CENTRED = np.array([[0.5, 1.5, 1.2], [1.2, 0.3, 0.5], [0.2, 2.5, 0.0], [-0.3, 0.8, 1.1]])


def _spa(z: list[float]) -> tuple[float, tuple[float, float, float]]:
    f = np.array(z) / 10
    stat, p = spa(f, f + CENTRED / 10, np.ones(3), 100)
    return stat, (p.lower, p.consistent, p.upper)


def test_spa_by_hand() -> None:
    # -sqrt(2 ln ln 100) = -1.748: setting 2 is clearly worse, setting 3 is not.
    stat, p = _spa([1.0, -2.0, -1.0])
    assert stat == pytest.approx(1.0)
    assert p == pytest.approx((0.25, 0.75, 1.0))
    # Studentized: a setting ten times as noisy, with ten times the omega, changes nothing.
    f, scale = np.array([1.0, -2.0, -1.0]) / 10, np.array([1.0, 10.0, 1.0])
    _, scaled = spa(f * scale, (f + CENTRED / 10) * scale, scale, 100)
    assert (scaled.lower, scaled.consistent, scaled.upper) == pytest.approx(p)


def test_consistent_recentring_switches_at_the_threshold() -> None:
    assert _spa([1.0, -1.8, -1.0])[1][1] == pytest.approx(0.75)  # below: kept at its mean
    assert _spa([1.0, -1.7, -1.0])[1][1] == pytest.approx(1.0)  # above: recentred at 0


def test_stepm_steps_down() -> None:
    # Step 1: maxima 3.0, 2.5, 2.2, 0.4 give d = 2.5 and reject setting 0 only. Without it
    # the maxima are 1.0, 1.5, 1.8, 0.2, d = 1.5, and setting 1 (z = 2.0) is rejected too.
    centred = np.array([[3.0, 1.0, 0.5], [2.5, 1.5, 0.4], [2.2, 1.8, 0.3], [0.4, 0.2, 0.1]])
    f = np.array([5.0, 2.0, 0.0]) / 10
    assert stepm(f, f + centred / 10, np.ones(3), 100, alpha=0.25) == [0, 1]


def test_stepm_critical_value_is_the_inverted_cdf_quantile() -> None:
    # B = 5 and alpha = 0.3: the smallest x with F(x) >= 0.7 is the 4th of 5 maxima, 0.4.
    # numpy's default (linear) gives 0.38 and would reject z = 0.39.
    centred = np.array([[0.1], [0.2], [0.3], [0.4], [0.5]])
    f = np.array([0.039])
    assert stepm(f, f + centred / 10, np.ones(1), 100, alpha=0.3) == []
    f = np.array([0.041])
    assert stepm(f, f + centred / 10, np.ones(1), 100, alpha=0.3) == [0]


def test_holm_by_hand() -> None:
    assert holm([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.03, 0.06, 0.06, 0.02])


def _null_family(rng: np.random.Generator, t: int, n: int) -> tuple[np.ndarray, np.ndarray]:
    """n settings with the benchmark's mean and volatility, correlated with it."""
    z = rng.standard_normal((t, n + 1))
    b = 0.0005 + 0.01 * z[:, 0]
    x = 0.0005 + 0.01 * (0.8 * z[:, :1] + 0.6 * z[:, 1:])
    return x, b


def test_poor_settings_raise_the_reality_check_but_not_the_spa() -> None:
    rng = np.random.default_rng(7)
    x, b = _null_family(rng, 1_000, 10)
    poor = b[:, None] - 0.003 + 0.004 * rng.standard_normal((1_000, 50))
    small = compare(x, b, mean_block=5, reps=2_000, seed=0)[Criterion.MEAN]
    large = compare(np.hstack([x, poor]), b, mean_block=5, reps=2_000, seed=0)[Criterion.MEAN]
    assert large.reality_check > small.reality_check + 0.1
    assert large.spa.upper > small.spa.upper
    assert large.spa.consistent == small.spa.consistent


@pytest.mark.parametrize("criterion", list(Criterion))
def test_size_and_power(criterion: Criterion) -> None:
    rejected, found = 0, 0
    for seed in range(200):
        rng = np.random.default_rng(seed)
        x, b = _null_family(rng, 500, 20)
        null = compare(x, b, mean_block=5, reps=500, seed=seed)[criterion]
        rejected += null.spa.consistent <= 0.05
        x[:, 0] += 0.0013  # a planted edge in setting 0, about 4.6 standard errors
        edge = compare(x, b, mean_block=5, reps=500, seed=seed)[criterion]
        found += 0 in edge.stepm
        for r in (null, edge):  # a StepM rejection at 0.05 implies an upper p of at most 0.05
            assert not r.stepm or r.spa.upper <= 0.05
    assert rejected <= 16  # 8% of 200
    assert found >= 180


def test_a_setting_equal_to_the_benchmark_is_left_out_of_the_studentized_tests() -> None:
    x, b = _null_family(np.random.default_rng(8), 300, 3)
    x[:, 1] = b
    out = compare(x, b, mean_block=5, reps=200, seed=0)
    for comparison in out.values():
        assert comparison.studentized == [0, 2]
        assert comparison.omega[1] == pytest.approx(0.0, abs=1e-12)


def test_rejects_misaligned_or_missing_returns() -> None:
    x, b = _null_family(np.random.default_rng(9), 50, 2)
    with pytest.raises(ValueError, match="finite"):
        compare(x, b[:-1], mean_block=5, reps=10, seed=0)
    x[3, 1] = np.nan
    with pytest.raises(ValueError, match="finite"):
        compare(x, b, mean_block=5, reps=10, seed=0)


def _arch_family(edges: tuple[float, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Ten settings, the first with the given edges, and five far below the benchmark."""
    rng = np.random.default_rng(0)
    x, b = _null_family(rng, 2_000, 10)
    x[:, : len(edges)] += edges
    poor = b[:, None] - 0.003 + 0.006 * rng.standard_normal((2_000, 5))
    return np.hstack([x, poor]), b


def test_matches_arch_on_the_mean_difference() -> None:
    # arch tests losses, so the benchmark and the settings enter negated. Its SPA
    # studentizes inside every resample and Hansen's does not; on these data the two
    # differ by under 0.01, against a bootstrap error of about 0.005.
    reps = 20_000
    x, b = _arch_family((0.0004,))
    ours = compare(x, b, mean_block=10, reps=reps, seed=0)[Criterion.MEAN]
    plain = SPA(-b, -x, block_size=10, reps=reps, studentize=False, seed=1)
    plain.compute()
    se = math.sqrt(2 * ours.reality_check * (1 - ours.reality_check) / reps)
    assert ours.reality_check == pytest.approx(plain.pvalues["upper"], abs=4 * se)
    studentized = SPA(-b, -x, block_size=10, reps=reps, seed=1)
    studentized.compute()
    p = ours.spa
    assert p.consistent < p.upper - 0.03  # the poor settings matter here
    for kind, value in (("lower", p.lower), ("consistent", p.consistent), ("upper", p.upper)):
        assert value == pytest.approx(studentized.pvalues[kind], abs=0.02)
    x, b = _arch_family((0.0015, 0.0015, 0.0015))
    ours = compare(x, b, mean_block=10, reps=5_000, seed=0)[Criterion.MEAN]
    step = StepM(-b, -x, size=0.05, block_size=10, reps=5_000, seed=1)
    step.compute()
    assert ours.stepm == list(step.superior_models) == [0, 1, 2]
