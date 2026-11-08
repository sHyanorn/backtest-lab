"""Holdout split and walk-forward analysis (METHODS.md Section 2)."""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtest_lab.engine.backtest import run
from backtest_lab.engine.metrics import ANNUALIZATION, sharpe
from backtest_lab.strategies import STRATEGIES, MarketData
from backtest_lab.validation.search import Trials
from backtest_lab.validation.selection import best_trial


def _positive_ratio(num: float, den: float) -> float | None:
    """num / den, reported only when den is positive and both are finite."""
    if not (math.isfinite(num) and math.isfinite(den)) or den <= 0:
        return None
    return num / den


@dataclass(frozen=True)
class Holdout:
    split: pd.Timestamp  # first OOS date
    trial: int  # selected on the IS rows
    is_sharpe: float  # annualized
    oos_sharpe: float  # annualized

    @property
    def retention(self) -> float | None:
        return _positive_ratio(self.oos_sharpe, self.is_sharpe)


def holdout(returns: pd.DataFrame, fraction: float = 0.7) -> Holdout:
    """Select on the first `fraction` of the rows and evaluate on the rest."""
    n = len(returns)
    split = math.floor(fraction * n)
    if not (0 < fraction < 1 and 2 <= split <= n - 2):
        raise ValueError("need 0 < fraction < 1 and at least two rows on each side")
    x = returns.to_numpy(dtype=np.float64)
    trial = best_trial(x[:split])
    return Holdout(
        split=pd.Timestamp(returns.index[split]),
        trial=trial,
        is_sharpe=sharpe(x[:split, trial]),
        oos_sharpe=sharpe(x[split:, trial]),
    )


def window_bounds(n: int, is_len: int, oos_len: int, anchored: bool) -> list[tuple[int, int, int]]:
    """(IS start, IS end = OOS start, OOS end) row bounds, half-open; the tail is dropped."""
    if is_len < 2 or oos_len < 1:
        raise ValueError("need is_len >= 2 and oos_len >= 1")
    bounds = []
    end = is_len
    while end + oos_len <= n:
        bounds.append((0 if anchored else end - is_len, end, end + oos_len))
        end += oos_len
    return bounds


@dataclass(frozen=True)
class Window:
    is_start: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp  # last OOS date
    trial: int
    is_sharpe: float  # annualized, selected trial on the IS rows
    is_return: float  # annualized arithmetic return, A x mean
    oos_sharpe: float  # annualized, stitched OOS returns in this window


@dataclass(frozen=True)
class WalkForward:
    windows: tuple[Window, ...]
    returns: pd.Series  # stitched OOS net returns

    @property
    def is_return(self) -> float:
        """Mean over windows of the selected trial's annualized IS return."""
        return float(np.mean([w.is_return for w in self.windows]))

    @property
    def oos_return(self) -> float:
        return float(ANNUALIZATION * self.returns.mean())

    @property
    def efficiency(self) -> float | None:
        """Walk-forward efficiency, reported only when the mean IS return is positive."""
        return _positive_ratio(self.oos_return, self.is_return)


def walk_forward(
    trials: Trials,
    data: MarketData,
    is_len: int = 1260,
    oos_len: int = 252,
    *,
    anchored: bool = False,
) -> WalkForward:
    """Re-select on each IS window and trade the selection on the next OOS window.

    The selected trials' target weights are stitched into one series and run
    through the engine once, so parameter switches pay trading costs.
    """
    x = trials.returns.to_numpy(dtype=np.float64)
    dates = trials.returns.index
    bounds = window_bounds(len(x), is_len, oos_len, anchored)
    if not bounds:
        raise ValueError("sample too short for one walk-forward window")
    price_dates = data.prices.close.index
    pos = price_dates.get_indexer(dates)
    if (pos < 1).any():
        raise ValueError("trial dates must be price dates after the first")

    picks = [best_trial(x[s:e]) for s, e, _ in bounds]
    weights = {i: STRATEGIES[trials.strategy](**trials.params[i]).weights(data) for i in set(picks)}
    columns = list(dict.fromkeys(c for w in weights.values() for c in w.columns))
    targets = pd.DataFrame(np.nan, index=price_dates, columns=columns)
    for (_, e, end), i in zip(bounds, picks, strict=True):
        # The return of OOS day d comes from the target set at the previous close.
        rows = pos[e:end] - 1
        frame = weights[i].reindex(columns=columns, fill_value=0.0)
        targets.iloc[rows] = frame.iloc[rows].to_numpy()
    result = run(targets, data.prices, trials.costs)
    oos = result.returns.loc[dates[bounds[0][1] : bounds[-1][2]]]

    windows = []
    for (s, e, end), i in zip(bounds, picks, strict=True):
        windows.append(
            Window(
                is_start=pd.Timestamp(dates[s]),
                oos_start=pd.Timestamp(dates[e]),
                oos_end=pd.Timestamp(dates[end - 1]),
                trial=i,
                is_sharpe=sharpe(x[s:e, i]),
                is_return=float(ANNUALIZATION * x[s:e, i].mean()),
                oos_sharpe=sharpe(oos.iloc[e - bounds[0][1] : end - bounds[0][1]]),
            )
        )
    return WalkForward(windows=tuple(windows), returns=oos)
