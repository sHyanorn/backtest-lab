"""SPA p-values when no setting is above the benchmark (D046)."""

from typing import Any

import numpy as np

from backtest_lab.validation.relative import decision
from backtest_lab.validation.snooping import Criterion, compare, spa


def test_spa_by_hand_when_every_statistic_is_negative() -> None:
    # T = 100 and omega = 1: t = (-3, -4), both below -sqrt(2 ln ln 100) = -1.748.
    f = np.array([-0.3, -0.4])
    centred = np.array([[0.5, 1.0], [-0.2, 0.3], [1.2, -0.5], [0.1, 0.9]])
    stat, p = spa(f, f + centred / 10, np.ones(2), 100)
    assert stat == 0.0
    # No setting is above the benchmark: nothing speaks against H0, so p = 1.
    # Counting T* > T would give (0.0, 0.0, 1.0).
    assert (p.lower, p.consistent, p.upper) == (1.0, 1.0, 1.0)


def test_a_grid_far_below_the_benchmark_is_not_a_finding() -> None:
    rng = np.random.default_rng(0)
    t, n = 500, 8
    b = 0.0005 + 0.01 * rng.standard_normal(t)
    x = b[:, None] - 0.003 + 0.004 * rng.standard_normal((t, n))  # about 17 s.e. below
    out = compare(x, b, mean_block=5, reps=500, seed=0)
    record: dict[str, Any] = {
        "instrument": "X",
        "strategy": "ma_crossover",
        "variant": "decision",
        "mean_block": 10.0,
    }
    for c in Criterion:
        assert (out[c].statistic < 0).all()
        assert out[c].spa_statistic == 0.0 and out[c].stepm == []
        record[c.value] = {"spa": {"consistent": out[c].spa.consistent}}
    # Counting T* > T would give a consistent p of 0.0 under both criteria, so Holm 0.0
    # and a finding in both families.
    assert all(out[c].spa.consistent == 1.0 for c in Criterion)
    assert not any(d["finding"] for d in decision([record]))


def test_one_setting_further_below_the_benchmark_has_no_smaller_p_value() -> None:
    rng = np.random.default_rng(1)
    t = 1_000
    b = 0.0005 + 0.01 * rng.standard_normal(t)
    noise = 0.006 * rng.standard_normal(t)
    noise -= noise.mean()  # the mean difference is exactly the shift; its s.e. is about 0.00019

    def p(shift: float) -> float:
        x = (b + noise + shift)[:, None]
        return compare(x, b, mean_block=5, reps=1_000, seed=0)[Criterion.MEAN].spa.consistent

    # About -5.3 and -1.05 standard errors; -sqrt(2 ln ln 1000) = -1.966 lies between.
    # Counting T* > T gives about 0.0 for the first and about 0.5 for the second.
    assert p(-0.001) >= p(-0.0002)
