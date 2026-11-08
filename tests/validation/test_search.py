from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest_lab.engine.backtest import Costs, run
from backtest_lab.strategies import MovingAverageCrossover
from backtest_lab.validation.search import Grid, Trials, run_grid
from tests.factories import synthetic_market

GRID = Grid.of({"fast": [5, 10], "slow": [20, 40], "allow_short": [False, True]}, {"ticker": "SPY"})


def test_grid_enumerates_last_axis_fastest() -> None:
    params = GRID.params()
    assert len(GRID) == len(params) == 8
    assert GRID.shape == (2, 2, 2)
    assert params[0] == {"ticker": "SPY", "fast": 5, "slow": 20, "allow_short": False}
    assert params[1] == {"ticker": "SPY", "fast": 5, "slow": 20, "allow_short": True}
    assert params[2]["slow"] == 40
    assert params[7] == {"ticker": "SPY", "fast": 10, "slow": 40, "allow_short": True}
    assert GRID.coords(6) == (1, 1, 0)
    assert GRID.ordered == (True, True, False)


@pytest.mark.parametrize(
    ("axes", "fixed"),
    [
        ({}, {}),
        ({"fast": []}, {}),
        ({"fast": [10, 5]}, {}),
        ({"fast": [5, 5]}, {}),
        ({"allow_short": [True, True]}, {}),
        ({"fast": [5]}, {"fast": 5}),
    ],
)
def test_grid_rejects_invalid_axes(axes: dict[str, list[int]], fixed: dict[str, int]) -> None:
    with pytest.raises(ValueError, match=r"axis|axes"):
        Grid.of(axes, fixed)


def test_grid_json_round_trip() -> None:
    assert Grid.from_json(GRID.to_json()) == GRID


def test_trials_are_backtests_aligned_on_the_latest_start() -> None:
    data = synthetic_market(n=200)
    trials = run_grid("ma_crossover", GRID, data, processes=1)
    assert trials.returns.shape[1] == 8
    # slow = 40 has the longest warm-up, so every trial is live from its start
    slow = run(MovingAverageCrossover(fast=5, slow=40).weights(data), data.prices)
    assert slow.start is not None
    assert trials.returns.index[0] == slow.start == max(trials.starts)
    for i, params in enumerate(trials.params):
        result = run(MovingAverageCrossover(**params).weights(data), data.prices)  # type: ignore[arg-type]
        assert trials.starts[i] == result.start
        expected = result.returns[result.returns.index >= slow.start].to_numpy()
        np.testing.assert_array_equal(trials.returns[i].to_numpy(), expected)


def test_results_do_not_depend_on_the_number_of_processes() -> None:
    data = synthetic_market(n=200)
    one = run_grid("ma_crossover", GRID, data, processes=1)
    two = run_grid("ma_crossover", GRID, data, processes=2)
    pd.testing.assert_frame_equal(one.returns, two.returns, check_exact=True)
    assert one.starts == two.starts


def test_progress_reports_every_trial() -> None:
    calls: list[tuple[int, int]] = []
    run_grid(
        "ma_crossover",
        GRID,
        synthetic_market(n=100),
        processes=1,
        progress=lambda *a: calls.append(a),
    )
    assert calls == [(i, 8) for i in range(1, 9)]


def test_costs_are_on_by_default() -> None:
    data = synthetic_market(n=100)
    trials = run_grid("ma_crossover", GRID, data, processes=1)
    free = run_grid("ma_crossover", GRID, data, Costs(0.0, 0.0), processes=1)
    assert trials.costs == Costs()
    assert (trials.returns.sum() < free.returns.sum()).all()


def test_invalid_combination_fails_before_running() -> None:
    grid = Grid.of({"fast": [5, 30], "slow": [20]})
    with pytest.raises(ValueError, match="fast < slow"):
        run_grid("ma_crossover", grid, synthetic_market(n=50), processes=1)
    with pytest.raises(ValueError, match="unknown strategy"):
        run_grid("nope", grid, synthetic_market(n=50), processes=1)


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    trials = run_grid("ma_crossover", GRID, synthetic_market(n=100), Costs(2.0, 3.0), processes=1)
    trials.save(tmp_path / "job")
    loaded = Trials.load(tmp_path / "job")
    pd.testing.assert_frame_equal(
        loaded.returns, trials.returns, check_exact=True, check_freq=False
    )
    assert loaded.grid == trials.grid
    assert loaded.costs == trials.costs
    assert loaded.strategy == trials.strategy
    assert loaded.starts == trials.starts
