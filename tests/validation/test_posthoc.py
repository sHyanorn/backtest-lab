import numpy as np
import pytest

from backtest_lab.validation.demo import Search
from backtest_lab.validation.pbo import cscv
from backtest_lab.validation.posthoc import analyse, drawdown_episodes
from backtest_lab.validation.search import Grid, run_grid
from tests.factories import synthetic_market


def test_drawdown_episodes_deepest_first() -> None:
    # wealth 1.1, 0.88, 0.924, 1.1088, 0.99792, 0.898128, 1.1675664
    r = np.array([0.1, -0.2, 0.05, 0.2, -0.1, -0.1, 0.3])
    first, second = drawdown_episodes(r, top=3)
    assert (first.peak, first.trough) == (0, 1)
    assert first.depth == pytest.approx(-0.2)
    assert (second.peak, second.trough) == (3, 5)
    assert second.depth == pytest.approx(0.898128 / 1.1088 - 1)
    assert drawdown_episodes(r, top=1) == [first]


def test_drawdown_from_the_start_and_unrecovered() -> None:
    (start,) = drawdown_episodes(np.array([-0.1, 0.05, 0.2]))
    assert (start.peak, start.trough) == (-1, 0)  # the starting wealth of 1 is the high
    assert start.depth == pytest.approx(-0.1)
    (episode,) = drawdown_episodes(np.array([0.1, -0.3, 0.1]))
    assert (episode.peak, episode.trough) == (0, 1)
    assert drawdown_episodes(np.array([0.01, 0.02])) == []


def test_analyse_is_consistent_with_the_registered_methods() -> None:
    data = synthetic_market(n=1500, seed=11, drift=0.0004)
    grid = Grid.of(
        {"fast": [5, 10], "slow": [40, 80], "allow_short": [False, True]}, {"ticker": "SPY"}
    )
    result = analyse(Search("ma", "ma_crossover", grid), data, processes=1)
    x = run_grid("ma_crossover", grid, data, processes=1).returns.to_numpy()
    assert result["pbo"]["full_grid"] == cscv(x).pbo
    assert result["pbo"]["long_only_half"] == cscv(x[:, ::2]).pbo  # allow_short is the last axis
    assert result["long_only_half_dsr"]["n_trials"] == 4
    assert 0 <= result["cscv"]["long_only_winner_share"] <= 1
    assert result["cscv"]["combinations"] == 12_870
    assert 0 <= result["selected_profile"]["time_in_market"] <= 1
    assert result["benchmark_profile"]["time_in_market"] == 1
    for episode in result["benchmark_drawdowns"]:
        assert episode["benchmark_return"] < 0
