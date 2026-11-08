"""The engine must not let anything after the close of day t affect results up to t."""

import numpy as np
import pandas as pd
import pytest

from backtest_lab.engine.backtest import Costs, Prices, Result, run

N, K = 120, 3
CUTS = [10, 47, 80, 118]


def _market(seed: int) -> tuple[pd.DataFrame, Prices]:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2021-01-04", periods=N).as_unit("us")
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (N, K)), axis=0)), index=dates)
    open_ = close.shift(1) * np.exp(rng.normal(0, 0.005, (N, K)))
    open_.iloc[0] = close.iloc[0]
    raw = rng.normal(0, 1, (N, K))
    weights = pd.DataFrame(raw / np.abs(raw).sum(axis=1, keepdims=True), index=dates)
    return weights, Prices(open=open_, close=close)


def _upto(result: Result, t: pd.Timestamp) -> pd.DataFrame:
    return pd.concat(
        [result.returns, result.gross_returns, result.turnover, result.costs, result.weights],
        axis=1,
    ).loc[:t]


@pytest.mark.parametrize("cut", CUTS)
def test_changing_todays_signal_does_not_change_today(cut: int) -> None:
    weights, prices = _market(seed=cut)
    t = weights.index[cut]
    changed = weights.copy()
    changed.loc[t:] = changed.loc[t:].iloc[:, ::-1].to_numpy()  # different targets from t on
    pd.testing.assert_frame_equal(_upto(run(weights, prices), t), _upto(run(changed, prices), t))


@pytest.mark.parametrize("cut", CUTS)
def test_shuffling_future_prices_does_not_change_the_past(cut: int) -> None:
    weights, prices = _market(seed=cut)
    t = weights.index[cut]
    rng = np.random.default_rng(cut)
    later = prices.close.index > t
    order = rng.permutation(int(later.sum()))
    open_, close = prices.open.copy(), prices.close.copy()
    open_.loc[later] = open_.loc[later].to_numpy()[order] * 1.5
    close.loc[later] = close.loc[later].to_numpy()[order] * 0.7
    shuffled = Prices(open=open_, close=close)
    pd.testing.assert_frame_equal(_upto(run(weights, prices), t), _upto(run(weights, shuffled), t))


def test_targets_are_held_from_the_next_open() -> None:
    weights, prices = _market(seed=1)
    held = run(weights, prices).weights
    pd.testing.assert_frame_equal(held, weights.shift(1).iloc[1:])


@pytest.mark.parametrize("cut", CUTS)
def test_trade_at_an_open_ignores_that_days_close(cut: int) -> None:
    # Turnover, costs and positions at the open of day t are fixed before close t exists.
    weights, prices = _market(seed=cut)
    t = weights.index[cut]
    close = prices.close.copy()
    close.loc[t:] *= 1.3
    moved = Prices(open=prices.open, close=close)
    a, b = run(weights, prices), run(weights, moved)
    for field in ("turnover", "costs"):
        assert getattr(a, field).loc[t] == getattr(b, field).loc[t]
    pd.testing.assert_series_equal(a.weights.loc[t], b.weights.loc[t])


@pytest.mark.parametrize("cut", CUTS[:-1])
def test_new_target_does_not_earn_the_overnight_gap(cut: int) -> None:
    # With no intraday move on day t+1, its return comes only from the previous
    # positions' overnight gap, so it cannot depend on the target formed at close t.
    weights, prices = _market(seed=cut)
    t, nxt = weights.index[cut], weights.index[cut + 1]
    close = prices.close.copy()
    close.loc[nxt] = prices.open.loc[nxt]
    flat_day = Prices(open=prices.open, close=close)
    zero = Costs(fee_bps=0.0, slippage_bps=0.0)
    changed = weights.copy()
    changed.loc[t] = -changed.loc[t]
    a = run(weights, flat_day, zero).returns.loc[nxt]
    b = run(changed, flat_day, zero).returns.loc[nxt]
    assert a == pytest.approx(b, abs=1e-15)
