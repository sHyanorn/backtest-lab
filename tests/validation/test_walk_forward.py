import itertools
from dataclasses import replace

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest

from backtest_lab.engine.backtest import Prices
from backtest_lab.engine.metrics import ANNUALIZATION
from backtest_lab.strategies import MarketData
from backtest_lab.validation.search import Grid, run_grid
from backtest_lab.validation.selection import best_trial
from backtest_lab.validation.walk_forward import holdout, walk_forward, window_bounds
from tests.factories import synthetic_market


def _matrix(t: int, n: int, seed: int) -> pd.DataFrame:
    x = 0.01 * np.random.default_rng(seed).standard_normal((t, n))
    return pd.DataFrame(x, index=pd.bdate_range("2000-01-03", periods=t))


def _tied_except(row: int, trial: int, t: int, n: int) -> npt.NDArray[np.float64]:
    """Identical columns, so selection ties go to trial 0, except a small gain for `trial`
    on `row`. The row's common return is 0, below the positive mean, so the gain raises
    that trial's Sharpe on any rows that include `row`."""
    base = 0.0005 + 0.01 * np.random.default_rng(0).standard_normal(t)
    base[row] = 0.0
    x = np.tile(base[:, None], (1, n))
    x[row, trial] = 0.001
    return x


# Holdout (Section 2.1)


def test_holdout_boundaries() -> None:
    x = _matrix(10, 3, seed=0)
    assert holdout(x).split == x.index[7]


@pytest.mark.parametrize(("t", "first_oos"), [(90, 63), (170, 119), (8247, 5772)])
def test_holdout_split_is_exact(t: int, first_oos: int) -> None:
    x = _matrix(t, 3, seed=0)
    assert holdout(x).split == x.index[first_oos]  # floor(0.7 t) in exact arithmetic


def test_holdout_selection_ignores_even_the_first_oos_row() -> None:
    x = pd.DataFrame(_tied_except(row=350, trial=3, t=500, n=5))
    assert holdout(x).trial == 0  # IS rows [0, 350) tie
    assert best_trial(x.iloc[:351]) == 3  # one OOS row would change the choice


def test_holdout_finds_a_planted_edge() -> None:
    x = _matrix(1000, 20, seed=3)
    x[7] += 0.002
    result = holdout(x)
    assert result.trial == 7
    assert result.oos_sharpe > 0
    assert result.retention is not None and result.retention > 0


def test_holdout_of_noise_is_within_two_standard_errors() -> None:
    n_oos = 300
    se = np.sqrt(ANNUALIZATION / n_oos)
    within = [abs(holdout(_matrix(1000, 50, seed)).oos_sharpe) < 2 * se for seed in range(20)]
    assert sum(within) >= 17


def test_holdout_retention_needs_positive_is_sharpe() -> None:
    x = _matrix(100, 2, seed=4) - 0.01
    assert holdout(x).retention is None


# Walk-forward (Section 2.2)


def test_window_bounds_rolling_and_anchored() -> None:
    assert window_bounds(10, 4, 2, anchored=False) == [(0, 4, 6), (2, 6, 8), (4, 8, 10)]
    assert window_bounds(10, 4, 2, anchored=True) == [(0, 4, 6), (0, 6, 8), (0, 8, 10)]
    assert window_bounds(11, 4, 2, anchored=False)[-1] == (4, 8, 10)  # tail dropped


@pytest.mark.parametrize(("n", "is_len", "oos_len"), [(100, 30, 7), (57, 10, 10), (500, 252, 21)])
@pytest.mark.parametrize("anchored", [False, True])
def test_window_invariants(n: int, is_len: int, oos_len: int, anchored: bool) -> None:
    bounds = window_bounds(n, is_len, oos_len, anchored)
    for (_, _, end), (_, start, _) in itertools.pairwise(bounds):
        assert end == start  # OOS windows are contiguous and disjoint
    for s, e, end in bounds:
        assert s < e < end <= n
        assert e - s == (e if anchored else is_len)


def test_fixed_parameters_reproduce_the_trial_after_entry() -> None:
    data = synthetic_market(n=600, seed=5)
    trials = run_grid("ma_crossover", Grid.of({"fast": [5], "slow": [20]}), data, processes=1)
    result = walk_forward(trials, data, is_len=200, oos_len=100)
    assert len(result.windows) == 3
    expected = trials.returns[0].loc[result.returns.index]
    # The first OOS day enters from cash; afterwards no parameter ever changes.
    np.testing.assert_allclose(result.returns.iloc[1:], expected.iloc[1:], rtol=0, atol=1e-15)


def _shift_prices_after(data: MarketData, row: int, seed: int) -> MarketData:
    shock = np.ones(data.prices.close.shape)
    shock[row:] = np.exp(np.random.default_rng(seed).normal(0, 0.05, shock[row:].shape))
    close = data.prices.close * shock
    open_ = data.prices.open * shock
    return MarketData(prices=Prices(open=open_, close=close))


def test_walk_forward_has_no_look_ahead() -> None:
    data = synthetic_market(n=900, tickers=("A", "B"), seed=6)
    grid = Grid.of({"ticker": ["A", "B"], "fast": [5, 10], "slow": [20, 40]})
    base_trials = run_grid("ma_crossover", grid, data, processes=1)
    base = walk_forward(base_trials, data, is_len=200, oos_len=100)
    k = 2
    last = base.windows[k].oos_end
    row = int(data.prices.close.index.searchsorted(last)) + 1
    changed_data = _shift_prices_after(data, row, seed=7)
    changed = walk_forward(
        run_grid("ma_crossover", grid, changed_data, processes=1), changed_data, 200, 100
    )
    assert [w.trial for w in changed.windows[: k + 1]] == [w.trial for w in base.windows[: k + 1]]
    pd.testing.assert_series_equal(changed.returns.loc[:last], base.returns.loc[:last])
    assert not changed.returns.loc[last:].iloc[1:].equals(base.returns.loc[last:].iloc[1:])


def test_walk_forward_selection_ignores_its_own_oos_rows() -> None:
    data = synthetic_market(n=900, tickers=("A", "B"), seed=6)
    grid = Grid.of({"ticker": ["A", "B"], "fast": [5, 10], "slow": [20, 40]})
    trials = run_grid("ma_crossover", grid, data, processes=1)
    k = 2
    first_oos = window_bounds(len(trials.returns), 200, 100, anchored=False)[k][1]
    x = _tied_except(row=first_oos, trial=5, t=len(trials.returns), n=len(grid))
    rigged = replace(trials, returns=pd.DataFrame(x, index=trials.returns.index))
    picks = [w.trial for w in walk_forward(rigged, data, 200, 100).windows]
    assert picks[: k + 1] == [0] * (k + 1)
    assert picks[k + 1] == 5  # the next IS window contains the row


def test_walk_forward_finds_a_planted_edge() -> None:
    tickers = ("A", "B", "C", "D")
    data = synthetic_market(n=1500, tickers=tickers, seed=8, drift=(0.0, 0.0, 0.0, 0.002))
    grid = Grid.of({"ticker": list(tickers), "lookback": [20, 60]}, {"allow_short": False})
    trials = run_grid("momentum", grid, data, processes=1)
    result = walk_forward(trials, data, is_len=250, oos_len=125)
    picks = [trials.params[w.trial]["ticker"] for w in result.windows]
    assert picks.count("D") > len(picks) / 2
    assert result.returns.mean() > 0
    assert result.efficiency is not None and result.efficiency > 0


def test_walk_forward_of_noise_is_within_two_standard_errors() -> None:
    grid = Grid.of({"fast": [5, 10, 20], "slow": [40, 60]}, {"allow_short": True})
    within = []
    for seed in range(10):
        data = synthetic_market(n=1200, seed=seed)
        result = walk_forward(run_grid("ma_crossover", grid, data, processes=1), data, 250, 125)
        oos = result.returns
        se = np.sqrt(ANNUALIZATION / len(oos))
        within.append(abs(np.sqrt(ANNUALIZATION) * oos.mean() / oos.std()) < 2 * se)
    assert sum(within) >= 8


def test_walk_forward_needs_one_window() -> None:
    data = synthetic_market(n=100)
    trials = run_grid("ma_crossover", Grid.of({"fast": [5], "slow": [20]}), data, processes=1)
    with pytest.raises(ValueError, match="too short"):
        walk_forward(trials, data, is_len=60, oos_len=30)
