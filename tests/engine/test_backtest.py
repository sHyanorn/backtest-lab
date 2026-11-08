import numpy as np
import pandas as pd
import pytest

from backtest_lab.engine.backtest import Prices, run

DATES = pd.bdate_range("2024-01-02", periods=4).as_unit("us")


def _prices(open_: list[list[float]], close: list[list[float]]) -> Prices:
    cols = ["A", "B"]
    return Prices(
        open=pd.DataFrame(open_, index=DATES, columns=cols),
        close=pd.DataFrame(close, index=DATES, columns=cols),
    )


PRICES = _prices(
    open_=[[100, 50], [102, 49], [103, 52], [101, 52]],
    close=[[100, 50], [104, 51], [101, 52], [99, 53]],
)
WEIGHTS = pd.DataFrame(
    [[0.5, 0.5], [0.5, 0.5], [1.0, 0.0], [0.0, 0.0]], index=DATES, columns=["A", "B"]
)


def simulate(weights: pd.DataFrame, prices: Prices, cost_rate: float = 0.0) -> np.ndarray:
    """Reference: track shares and cash, trade at each open to the previous close's target."""
    o, c = prices.open.to_numpy(), prices.close.to_numpy()
    w = weights.fillna(0.0).to_numpy()
    shares = np.zeros(o.shape[1])
    cash, value = 1.0, 1.0
    out = []
    for t in range(1, len(o)):
        at_open = cash + shares @ np.nan_to_num(o[t])
        target = w[t - 1] * at_open
        traded = np.abs(target - shares * np.nan_to_num(o[t])).sum()
        at_open -= cost_rate * traded
        with np.errstate(divide="ignore", invalid="ignore"):
            shares = np.where(w[t - 1] != 0, w[t - 1] * at_open / o[t], 0.0)
        cash = at_open - shares @ np.nan_to_num(o[t])
        new_value = cash + shares @ np.nan_to_num(c[t])
        out.append(new_value / value - 1)
        value = new_value
    return np.array(out)


def test_hand_example_compounds_overnight_and_intraday() -> None:
    result = run(WEIGHTS, PRICES)
    day1 = 0.5 * (104 / 102) + 0.5 * (51 / 49) - 1
    # Day 2: shares bought at day 1's open are valued at day 2's open, then rebalanced 50/50.
    v1 = 0.5 / 102 * 104 + 0.5 / 49 * 51
    v2_open = 0.5 / 102 * 103 + 0.5 / 49 * 52
    v2 = v2_open * (0.5 * 101 / 103 + 0.5 * 52 / 52)
    # Day 3: the 50/50 shares from day 2 are valued at the open, then all go into A.
    held_a = v2_open * 0.5 / 103
    held_b = v2_open * 0.5 / 52
    v3_open = held_a * 101 + held_b * 52
    v3 = v3_open * 99 / 101
    expected = [day1, v2 / v1 - 1, v3 / v2 - 1]
    assert result.returns.to_numpy() == pytest.approx(expected, rel=1e-12)
    assert result.returns.to_numpy() == pytest.approx(simulate(WEIGHTS, PRICES), rel=1e-12)


def test_signal_fills_at_next_open_not_same_close() -> None:
    weights = pd.DataFrame(0.0, index=DATES, columns=["A", "B"])
    weights.loc[DATES[1], "A"] = 1.0
    result = run(weights, PRICES)
    assert result.returns.loc[DATES[1]] == 0.0
    assert result.returns.loc[DATES[2]] == pytest.approx(101 / 103 - 1)
    assert result.returns.loc[DATES[3]] == pytest.approx(0.0)


def test_cash_earns_zero() -> None:
    flat = pd.DataFrame(0.0, index=DATES, columns=["A", "B"])
    assert (run(flat, PRICES).returns == 0.0).all()
    half = flat.assign(A=0.5)
    assert run(half, PRICES).returns.loc[DATES[1]] == pytest.approx(0.5 * (104 / 102 - 1))


def test_matches_share_simulation_with_shorts_and_listing() -> None:
    rng = np.random.default_rng(0)
    n, k = 300, 4
    dates = pd.bdate_range("2020-01-01", periods=n).as_unit("us")
    close = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (n, k)), axis=0)), index=dates)
    open_ = close.shift(1) * np.exp(rng.normal(0, 0.005, (n, k)))
    open_.iloc[0] = close.iloc[0]
    close.iloc[:50, 3] = np.nan  # ticker 3 lists on day 50
    open_.iloc[:50, 3] = np.nan
    raw = rng.normal(0, 1, (n, k))
    raw[:50, 3] = 0.0
    weights = pd.DataFrame(raw / np.abs(raw).sum(axis=1, keepdims=True), index=dates)
    prices = Prices(open=open_, close=close)
    result = run(weights, prices)
    assert result.returns.to_numpy() == pytest.approx(
        simulate(weights, prices), rel=1e-9, abs=1e-12
    )


def test_warmup_rows_are_flat_and_start_is_reported() -> None:
    weights = WEIGHTS.copy()
    weights.iloc[:2] = np.nan
    result = run(weights, PRICES)
    assert result.start == DATES[3]
    assert (result.returns.loc[: DATES[2]] == 0.0).all()


def test_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="gross exposure"):
        run(WEIGHTS * 2, PRICES)
    with pytest.raises(ValueError, match="no prices"):
        run(WEIGHTS.rename(columns={"B": "C"}), PRICES)
    open_ = PRICES.open.copy()
    open_.loc[DATES[2], "A"] = np.nan
    gap = Prices(open=open_, close=PRICES.close)
    with pytest.raises(ValueError, match="without overnight prices"):
        run(WEIGHTS, gap)


def test_ruin_stops_the_backtest() -> None:
    prices = _prices(
        open_=[[100, 50], [100, 50], [250, 50], [250, 50]],
        close=[[100, 50], [100, 50], [250, 50], [300, 50]],
    )
    short = pd.DataFrame([[-1.0, 0.0]] * 4, index=DATES, columns=["A", "B"])
    returns = run(short, prices).returns.to_numpy()
    assert list(returns) == [0.0, -1.0, 0.0]
