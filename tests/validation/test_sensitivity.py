import math

import numpy as np
import pytest

from backtest_lab.validation.search import Grid
from backtest_lab.validation.sensitivity import heatmap, neighbours, sensitivity

GRID_5X5 = Grid.of({"a": list(range(5)), "b": list(range(5))})


def _surface(values: np.ndarray) -> np.ndarray:
    return values.reshape(-1)  # row-major, as trials are numbered


def test_constant_surface() -> None:
    result = sensitivity(np.ones(25), GRID_5X5)
    assert GRID_5X5.coords(result.best) == (0, 0)
    assert len(result.neighbours) == 3
    assert result.std == 0
    assert result.retention == 1


def test_spike() -> None:
    p = np.zeros((5, 5))
    p[2, 2] = 1
    result = sensitivity(_surface(p), GRID_5X5)
    assert len(result.neighbours) == 8
    assert result.mean == 0
    assert result.retention == 0


def test_corner_neighbourhoods() -> None:
    assert len(neighbours(GRID_5X5, 0)) == 3
    grid_3d = Grid.of({"a": [1, 2, 3], "b": [1, 2, 3], "c": [1, 2, 3]})
    assert len(neighbours(grid_3d, 0)) == 7
    assert len(neighbours(grid_3d, 13)) == 26  # interior: 3^3 - 1


def test_linear_surface() -> None:
    i, j = np.meshgrid(range(5), range(5), indexing="ij")
    result = sensitivity(_surface((i + j).astype(float)), GRID_5X5)
    assert GRID_5X5.coords(result.best) == (4, 4)
    assert sorted(GRID_5X5.coords(n) for n in result.neighbours) == [(3, 3), (3, 4), (4, 3)]
    assert result.mean == pytest.approx(20 / 3)
    assert result.retention == pytest.approx(5 / 6)


def test_categorical_axes_stay_fixed() -> None:
    grid = Grid.of({"a": [1, 2, 3], "short": [False, True]})
    near = neighbours(grid, grid.params().index({"a": 2, "short": True}))
    assert sorted(grid.params()[n]["a"] for n in near) == [1, 3]
    assert all(grid.params()[n]["short"] is True for n in near)


def test_radius_two_and_nan_counts_as_zero() -> None:
    p = np.full(25, np.nan)
    p[12] = 2.0
    result = sensitivity(p, GRID_5X5, radius=2)
    assert len(result.neighbours) == 24
    assert result.mean == 0
    assert result.retention == 0


def test_retention_needs_positive_best() -> None:
    assert sensitivity(-np.ones(25), GRID_5X5).retention is None
    single = Grid.of({"a": [1]})
    result = sensitivity([1.0], single)
    assert result.neighbours == () and math.isnan(result.mean) and result.retention is None


def test_heatmap_fixes_other_axes_at_the_best_trial() -> None:
    grid = Grid.of({"fast": [5, 10], "slow": [20, 40, 60], "short": [False, True]})
    p = np.arange(12, dtype=float)
    best = 9  # fast 10, slow 40, short True
    hm = heatmap(p, grid, best, ("slow", "fast"))
    assert hm.axis_values == ((20, 40, 60), (5, 10))
    assert hm.sharpe.shape == (2, 3)  # rows: fast; columns: slow
    assert all(grid.params()[t]["short"] is True for t in hm.trials.ravel())
    assert hm.trials[1, 1] == best
    np.testing.assert_array_equal(hm.sharpe, p[hm.trials])


def test_one_axis_heatmap_is_a_single_row() -> None:
    grid = Grid.of({"lookback": [21, 42, 63], "short": [False, True]})
    hm = heatmap(np.arange(6, dtype=float), grid, 3, ("lookback",))
    assert hm.sharpe.tolist() == [[1.0, 3.0, 5.0]]
