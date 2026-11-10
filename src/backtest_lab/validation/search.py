"""Parameter grid search that records the daily net returns of every trial.

Trials are aligned on the dates where all of them are live (METHODS.md, Conventions).
"""

import itertools
import json
import multiprocessing
import os
import signal
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from backtest_lab.engine.backtest import Costs, run
from backtest_lab.strategies import STRATEGIES, MarketData

type Param = bool | int | float | str
type Params = dict[str, Param]
type TrialOutput = tuple[npt.NDArray[np.float64], pd.Timestamp | None]

FORMAT_VERSION = 1
RETURNS_FILE = "returns.parquet"
META_FILE = "trials.json"


def _is_ordered(values: Sequence[Param]) -> bool:
    return not any(isinstance(v, bool | str) for v in values)


@dataclass(frozen=True)
class Grid:
    """Every combination of the axis values, enumerated with the last axis fastest.

    Numeric axes are ordered and must be strictly increasing; bool and str axes, and
    numeric axes listed in `categorical` (such as a random seed), are categorical
    (METHODS.md Section 7, D019).
    """

    axes: tuple[tuple[str, tuple[Param, ...]], ...]
    fixed: tuple[tuple[str, Param], ...] = ()
    categorical: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        names = [name for name, _ in self.axes] + [name for name, _ in self.fixed]
        if not self.axes or len(set(names)) != len(names):
            raise ValueError("need at least one axis and unique parameter names")
        unknown = set(self.categorical) - set(self.names)
        if unknown or len(set(self.categorical)) != len(self.categorical):
            raise ValueError(f"categorical must name distinct axes, got {list(self.categorical)}")
        for (name, values), ordered in zip(self.axes, self.ordered, strict=True):
            if not values:
                raise ValueError(f"axis {name!r} is empty")
            if ordered:
                if any(b <= a for a, b in itertools.pairwise(values)):  # type: ignore[operator]
                    raise ValueError(f"numeric axis {name!r} must be strictly increasing")
            elif len(set(values)) != len(values):
                raise ValueError(f"axis {name!r} has duplicate values")

    @classmethod
    def of(
        cls,
        axes: Mapping[str, Sequence[Param]],
        fixed: Mapping[str, Param] | None = None,
        categorical: Sequence[str] = (),
    ) -> Grid:
        return cls(
            axes=tuple((name, tuple(values)) for name, values in axes.items()),
            fixed=tuple((fixed or {}).items()),
            categorical=tuple(categorical),
        )

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.axes)

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(len(values) for _, values in self.axes)

    @property
    def ordered(self) -> tuple[bool, ...]:
        return tuple(
            _is_ordered(values) and name not in self.categorical for name, values in self.axes
        )

    def __len__(self) -> int:
        return int(np.prod(self.shape))

    def params(self) -> list[Params]:
        fixed = dict(self.fixed)
        return [
            {**fixed, **dict(zip(self.names, combo, strict=True))}
            for combo in itertools.product(*(values for _, values in self.axes))
        ]

    def coords(self, trial: int) -> tuple[int, ...]:
        return tuple(int(i) for i in np.unravel_index(trial, self.shape))

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "axes": {name: list(values) for name, values in self.axes},
            "fixed": dict(self.fixed),
        }
        if self.categorical:  # omitted when empty, so earlier files are unchanged
            out["categorical"] = list(self.categorical)
        return out

    @classmethod
    def from_json(cls, obj: Mapping[str, Any]) -> Grid:
        return cls.of(obj["axes"], obj["fixed"], obj.get("categorical", ()))


@dataclass(frozen=True)
class Trials:
    """Daily net returns of every trial: a T x N frame from the first date all are live."""

    strategy: str
    grid: Grid
    costs: Costs
    returns: pd.DataFrame  # columns 0..N-1 in grid order
    starts: tuple[pd.Timestamp, ...]  # each trial's own Result.start

    def __post_init__(self) -> None:
        n = len(self.grid)
        if not self.returns.columns.equals(pd.RangeIndex(n)) or len(self.starts) != n:
            raise ValueError("need one returns column and one start per grid point")

    @property
    def params(self) -> list[Params]:
        return self.grid.params()

    def save(self, directory: Path) -> None:
        """Write `returns.parquet` and `trials.json` into `directory`."""
        directory.mkdir(parents=True, exist_ok=True)
        frame = self.returns.rename(columns=str)
        frame.index.name = "date"
        frame.to_parquet(directory / RETURNS_FILE)
        meta = {
            "format_version": FORMAT_VERSION,
            "strategy": self.strategy,
            "grid": self.grid.to_json(),
            "costs": {"fee_bps": self.costs.fee_bps, "slippage_bps": self.costs.slippage_bps},
            "start": _iso(self.returns.index[0]),
            "end": _iso(self.returns.index[-1]),
            "n_days": len(self.returns),
            "trials": [
                {"params": params, "start": _iso(start)}
                for params, start in zip(self.params, self.starts, strict=True)
            ],
        }
        text = json.dumps(meta, indent=2) + "\n"
        (directory / META_FILE).write_text(text, encoding="utf-8", newline="\n")

    @classmethod
    def load(cls, directory: Path) -> Trials:
        meta = json.loads((directory / META_FILE).read_text(encoding="utf-8"))
        if meta["format_version"] != FORMAT_VERSION:
            raise ValueError(f"unsupported format version {meta['format_version']}")
        grid = Grid.from_json(meta["grid"])
        if [t["params"] for t in meta["trials"]] != grid.params():
            raise ValueError("trial parameters do not match the grid")
        returns = pd.read_parquet(directory / RETURNS_FILE)
        if list(returns.columns) != [str(i) for i in range(len(grid))]:
            raise ValueError("returns columns do not match the trials")
        returns.columns = pd.RangeIndex(len(grid))
        returns.index.name = None
        return cls(
            strategy=meta["strategy"],
            grid=grid,
            costs=Costs(**meta["costs"]),
            returns=returns,
            starts=tuple(pd.Timestamp(t["start"]) for t in meta["trials"]),
        )


def _iso(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%d")


def backtest(strategy: str, params: Params, data: MarketData, costs: Costs) -> TrialOutput:
    """Net returns over all price dates after the first, and the first live date."""
    result = run(STRATEGIES[strategy](**params).weights(data), data.prices, costs)
    return result.returns.to_numpy(dtype=np.float64), result.start


# Market data and costs in each worker process, set once by the pool initializer
# so they are pickled once per worker instead of once per trial.
_worker_state: tuple[MarketData, Costs] | None = None


def _exit_with_parent() -> None:
    parent = multiprocessing.parent_process()
    assert parent is not None
    parent.join()  # returns once the process that started the pool is gone
    os._exit(1)


def _init_worker(data: MarketData, costs: Costs) -> None:
    global _worker_state
    _worker_state = (data, costs)
    # Ctrl+C reaches every process in the console; the parent decides what to stop.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    # A killed parent cannot terminate its workers, and under forkserver they would
    # wait for work forever.
    threading.Thread(target=_exit_with_parent, daemon=True).start()


class GridCancelled(Exception):
    """`cancel()` returned True before every trial had run."""


def _worker_backtest(job: tuple[str, Params]) -> TrialOutput:
    assert _worker_state is not None
    return backtest(*job, *_worker_state)


def run_grid(
    strategy: str,
    grid: Grid,
    data: MarketData,
    costs: Costs = Costs(),  # noqa: B008 (immutable)
    *,
    processes: int | None = None,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
) -> Trials:
    """Backtest every grid point; results do not depend on `processes`.

    Each trial is a deterministic function of its parameters, and results are
    collected in grid order. `progress(done, total)` is called after each trial.
    `cancel()` is checked after each trial; when it returns True the worker processes
    are terminated and GridCancelled is raised. Workers are also terminated when
    collecting fails for any other reason, so none outlive the call.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}")
    params = grid.params()
    for p in params:  # fail on an invalid combination before any work
        STRATEGIES[strategy](**p)
    workers = min(processes or os.process_cpu_count() or 1, len(params))
    jobs = [(strategy, p) for p in params]

    outputs: list[TrialOutput] = []

    def collect(results: Iterable[TrialOutput]) -> None:
        for out in results:
            outputs.append(out)
            if progress is not None:
                progress(len(outputs), len(jobs))
            if cancel is not None and cancel() and len(outputs) < len(jobs):
                raise GridCancelled(f"cancelled after {len(outputs)} of {len(jobs)} trials")

    if workers == 1:
        collect(backtest(s, p, data, costs) for s, p in jobs)
    else:
        chunksize = max(1, len(jobs) // (4 * workers))
        before = set(multiprocessing.active_children())
        pool = ProcessPoolExecutor(workers, initializer=_init_worker, initargs=(data, costs))
        try:
            collect(pool.map(_worker_backtest, jobs, chunksize=chunksize))
        except BaseException:
            pool.terminate_workers()  # do not wait for trials already handed out
            for proc in set(multiprocessing.active_children()) - before:
                proc.join(timeout=10)
            raise
        finally:
            pool.shutdown(wait=True, cancel_futures=True)

    starts = [start for _, start in outputs]
    never = [i for i, start in enumerate(starts) if start is None]
    if never:
        raise ValueError(f"trials {never} never have a valid signal")
    live = [s for s in starts if s is not None]
    dates = data.prices.close.index[1:]
    keep = dates >= max(live)
    matrix = np.column_stack([r for r, _ in outputs])[keep]
    returns = pd.DataFrame(matrix, index=dates[keep], columns=pd.RangeIndex(len(params)))
    return Trials(strategy=strategy, grid=grid, costs=costs, returns=returns, starts=tuple(live))
