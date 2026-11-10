"""Parameter sensitivity around the best grid point (METHODS.md Section 7)."""

import itertools
import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from backtest_lab.validation.search import Grid, Param
from backtest_lab.validation.selection import Matrix


@dataclass(frozen=True)
class Sensitivity:
    neighbours: tuple[int, ...]
    best_sharpe: float  # P(i*), annualized
    mean: float  # m, NaN without neighbours
    std: float  # s, population form
    radius: int

    @property
    def retention(self) -> float | None:
        if self.best_sharpe <= 0 or math.isnan(self.mean):
            return None
        return self.mean / self.best_sharpe


def neighbours(grid: Grid, trial: int, radius: int = 1) -> tuple[int, ...]:
    """Trials within `radius` steps along every ordered axis, with categorical axes fixed."""
    centre = grid.coords(trial)
    ranges = [
        range(max(c - radius, 0), min(c + radius, n - 1) + 1) if ordered else range(c, c + 1)
        for c, n, ordered in zip(centre, grid.shape, grid.ordered, strict=True)
    ]
    return tuple(
        int(np.ravel_multi_index(point, grid.shape))
        for point in itertools.product(*ranges)
        if point != centre
    )


def sensitivity(sharpe: npt.ArrayLike, grid: Grid, best: int, radius: int = 1) -> Sensitivity:
    """Mean and spread of the annualized Sharpe ratios around the trial `best`.

    NaN Sharpe ratios count as 0 (METHODS.md, Conventions).
    """
    p = np.nan_to_num(np.asarray(sharpe, dtype=np.float64), nan=0.0)
    if p.shape != (len(grid),) or radius < 1:
        raise ValueError("need one Sharpe ratio per grid point and radius >= 1")
    near = neighbours(grid, best, radius)
    values = p[list(near)]
    return Sensitivity(
        neighbours=near,
        best_sharpe=float(p[best]),
        mean=float(values.mean()) if near else math.nan,
        std=float(values.std()) if near else math.nan,
        radius=radius,
    )


@dataclass(frozen=True)
class Heatmap:
    """Sharpe over one or two axes, with every other axis fixed at the best trial."""

    axes: tuple[str, ...]  # (x,) or (x, y)
    axis_values: tuple[tuple[Param, ...], ...]  # grid values along each axis
    sharpe: Matrix  # shape (len(y values), len(x values)); one row for a single axis
    trials: npt.NDArray[np.intp]  # trial number of each cell, same shape


def heatmap(sharpe: npt.ArrayLike, grid: Grid, best: int, axes: tuple[str, ...]) -> Heatmap:
    if not 1 <= len(axes) <= 2 or len(set(axes)) != len(axes):
        raise ValueError("need one or two distinct axes")
    p = np.nan_to_num(np.asarray(sharpe, dtype=np.float64), nan=0.0)
    position = {name: k for k, name in enumerate(grid.names)}
    centre = grid.coords(best)
    x = position[axes[0]]
    y = position[axes[1]] if len(axes) == 2 else None
    rows = range(grid.shape[y]) if y is not None else range(1)
    trials = np.empty((len(rows), grid.shape[x]), dtype=np.intp)
    for r in rows:
        for c in range(grid.shape[x]):
            point = list(centre)
            point[x] = c
            if y is not None:
                point[y] = r
            trials[r, c] = np.ravel_multi_index(tuple(point), grid.shape)
    axis_values = tuple(dict(grid.axes)[name] for name in axes)
    return Heatmap(axes=axes, axis_values=axis_values, sharpe=p[trials], trials=trials)
