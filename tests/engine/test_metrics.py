import warnings

import empyrical as ep
import numpy as np
import pytest

from backtest_lab.engine import metrics

# METHODS.md Section 1 test vector
R = [0.01, 0.10, -0.04, 0.02, 0.03, 0.02, 0.01, -0.10]


def test_methods_test_vector() -> None:
    assert float(np.prod(1 + np.array(R))) == pytest.approx(1.0389310917, abs=1e-10)
    expected = {
        "cagr": 2.3302927973,
        "annual_volatility": 0.9136465400,
        "sharpe": 1.7238613962,
        "sortino": 2.6055312517,
        "max_drawdown": -0.10,
        "calmar": 23.302927973,
    }
    got = metrics.summarize(R)
    for name, value in expected.items():
        assert got[name] == pytest.approx(value, abs=1e-9), name
    assert metrics.downside_deviation(R) == pytest.approx(0.6044832504, abs=1e-10)


def test_first_day_loss_is_a_drawdown() -> None:
    assert metrics.max_drawdown([-0.05, 0.02]) == pytest.approx(-0.05)


def test_constant_returns_give_nan_ratios_without_warnings() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        got = metrics.summarize([0.01] * 20)
    assert got["annual_volatility"] == 0.0
    assert np.isnan(got["sharpe"])
    assert np.isnan(got["sortino"])
    assert np.isnan(got["calmar"])


def test_wiped_out_wealth_has_nan_cagr() -> None:
    assert np.isnan(metrics.cagr([0.1, -1.0, 0.0]))


def test_rejects_nan() -> None:
    with pytest.raises(ValueError):
        metrics.sharpe([0.01, float("nan")])


def _pairs(r: np.ndarray) -> list[tuple[float, float]]:
    return [
        (metrics.cagr(r), ep.annual_return(r)),
        (metrics.annual_volatility(r), ep.annual_volatility(r)),
        (metrics.sharpe(r), ep.sharpe_ratio(r)),
        (metrics.downside_deviation(r), ep.downside_risk(r)),
        (metrics.sortino(r), ep.sortino_ratio(r)),
        (metrics.max_drawdown(r), ep.max_drawdown(r)),
        (metrics.calmar(r), ep.calmar_ratio(r)),
    ]


@pytest.mark.parametrize("seed", range(5))
def test_matches_empyrical(seed: int) -> None:
    r = np.random.default_rng(seed).normal(0.0004, 0.012, 1000)
    for ours, theirs in _pairs(r):
        assert ours == pytest.approx(float(theirs), abs=1e-10)


def test_matches_empyrical_on_methods_vector() -> None:
    for ours, theirs in _pairs(np.array(R)):
        assert ours == pytest.approx(float(theirs), abs=1e-10)
