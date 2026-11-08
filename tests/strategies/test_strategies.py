import numpy as np
import pandas as pd
import pytest

from backtest_lab.data.macro import Frequency, available_dates
from backtest_lab.engine.backtest import Prices, run
from backtest_lab.strategies import (
    MarketData,
    MeanReversion,
    MovingAverageCrossover,
    RandomSignal,
    RateRotation,
    Strategy,
    TimeSeriesMomentum,
)

N = 400
DATES = pd.bdate_range("2022-01-03", periods=N).as_unit("us")


def _macro(series_id: str, values: np.ndarray) -> pd.DataFrame:
    dates = pd.DatetimeIndex(DATES)
    return pd.DataFrame(
        {
            "series": series_id,
            "date": dates,
            "value": values,
            "available_date": available_dates(dates, Frequency.DAILY),
        }
    )


def _market(seed: int = 0) -> MarketData:
    rng = np.random.default_rng(seed)
    close = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0, 0.01, (N, 2)), axis=0)),
        index=DATES,
        columns=["SPY", "IEF"],
    )
    open_ = (close.shift(1) * np.exp(rng.normal(0, 0.003, (N, 2)))).fillna(close)
    spread_path = np.cumsum(rng.normal(0, 0.05, N))
    return MarketData(
        prices=Prices(open=open_, close=close),
        macro={
            "DGS10": _macro("DGS10", 3.0 + spread_path),
            "DGS3MO": _macro("DGS3MO", np.full(N, 3.0)),
        },
    )


def _trend(direction: float) -> MarketData:
    close = pd.DataFrame(
        {"SPY": 100 * np.exp(direction * 0.001 * np.arange(N)), "IEF": 100.0}, index=DATES
    )
    return MarketData(prices=Prices(open=close, close=close))


STRATEGIES: list[Strategy] = [
    MovingAverageCrossover(fast=10, slow=50),
    MovingAverageCrossover(fast=5, slow=20, allow_short=True),
    TimeSeriesMomentum(lookback=60),
    TimeSeriesMomentum(lookback=20, allow_short=False),
    MeanReversion(lookback=20, entry_z=1.0),
    MeanReversion(lookback=10, entry_z=0.5, allow_short=False),
    RateRotation(),
    RateRotation(threshold=0.2, smoothing=5),
    RandomSignal(seed=3, hold=5),
]


@pytest.mark.parametrize("strategy", STRATEGIES, ids=repr)
def test_warmup_is_the_leading_nan_rows(strategy: Strategy) -> None:
    data = _market()
    weights = strategy.weights(data)
    valid = weights.notna().all(axis=1).to_numpy()
    first = int(np.argmax(valid))
    extra = 1 if isinstance(strategy, RateRotation) else 0  # first rate is published a day later
    assert first == strategy.warmup + extra
    assert valid[first:].all()
    assert run(weights, data.prices).start == DATES[first + 1]


@pytest.mark.parametrize("strategy", STRATEGIES, ids=repr)
@pytest.mark.parametrize("cut", [80, 200, 350])
def test_future_data_does_not_change_past_weights(strategy: Strategy, cut: int) -> None:
    data = _market(seed=cut)
    t = DATES[cut]
    rng = np.random.default_rng(cut)
    later = t < DATES
    order = rng.permutation(int(later.sum()))
    open_, close = data.prices.open.copy(), data.prices.close.copy()
    open_.loc[later] = open_.loc[later].to_numpy()[order] * 2.0
    close.loc[later] = close.loc[later].to_numpy()[order] * 0.5
    macro = {}
    for sid, df in data.macro.items():
        df = df.copy()
        unknown = df["available_date"] > t
        df.loc[unknown, "value"] = rng.normal(0, 5, int(unknown.sum()))
        macro[sid] = df
    perturbed = MarketData(prices=Prices(open=open_, close=close), macro=macro)
    pd.testing.assert_frame_equal(
        strategy.weights(data).loc[:t], strategy.weights(perturbed).loc[:t]
    )


@pytest.mark.parametrize("strategy", STRATEGIES, ids=repr)
@pytest.mark.parametrize("cut", [80, 350])
def test_weights_are_scale_invariant(strategy: Strategy, cut: int) -> None:
    # Back-adjusting for a later dividend rescales all earlier prices by one factor;
    # weights up to that point must not change. Halving is exact in floating point.
    data = _market(seed=cut)
    t = DATES[cut]
    open_, close = data.prices.open.copy(), data.prices.close.copy()
    open_.loc[:t] *= 0.5
    close.loc[:t] *= 0.5
    rescaled = MarketData(prices=Prices(open=open_, close=close), macro=data.macro)
    pd.testing.assert_frame_equal(
        strategy.weights(data).loc[:t], strategy.weights(rescaled).loc[:t]
    )


def test_macro_as_of_keeps_the_newest_period() -> None:
    data = _market()
    obs = pd.DataFrame(
        {
            "series": "X",
            "date": pd.to_datetime(["2022-08-01", "2022-09-01", "2022-10-01"]).as_unit("us"),
            "value": [1.0, 2.0, 3.0],
            # September is published late, after October.
            "available_date": pd.to_datetime(["2022-09-30", "2022-11-21", "2022-11-15"]).as_unit(
                "us"
            ),
        }
    )
    with_x = MarketData(prices=data.prices, macro={"X": obs})
    s = with_x.macro_as_of("X")
    assert s.loc["2022-11-14"] == 1.0
    assert s.loc["2022-11-15"] == 3.0
    assert s.loc["2022-11-21"] == 3.0


def test_trend_followers_are_long_in_an_uptrend_and_out_in_a_downtrend() -> None:
    for strategy in (MovingAverageCrossover(fast=10, slow=50), TimeSeriesMomentum(lookback=60)):
        up = strategy.weights(_trend(1.0))["SPY"].dropna()
        down = strategy.weights(_trend(-1.0))["SPY"].dropna()
        assert (up == 1.0).all()
        assert (down <= 0.0).all()
    assert (TimeSeriesMomentum(lookback=60).weights(_trend(-1.0))["SPY"].dropna() == -1.0).all()


def test_mean_reversion_fades_a_spike() -> None:
    close = pd.Series(100.0 + 0.1 * np.sin(np.arange(N)), index=DATES)
    close.iloc[-1] = 110.0
    close.iloc[-30] = 90.0
    frame = pd.DataFrame({"SPY": close})
    data = MarketData(prices=Prices(open=frame, close=frame))
    w = MeanReversion(lookback=20, entry_z=2.0).weights(data)["SPY"]
    assert w.iloc[-1] == -1.0
    assert w.iloc[-30] == 1.0
    assert w.iloc[-10] == 0.0
    assert (
        MeanReversion(lookback=20, entry_z=2.0, allow_short=False).weights(data)["SPY"].iloc[-1]
        == 0.0
    )


def test_rotation_uses_a_rate_only_once_published() -> None:
    data = _market()
    spread = np.where(np.arange(N) < 200, 1.0, -1.0)
    macro = {
        "DGS10": _macro("DGS10", 3.0 + spread),
        "DGS3MO": _macro("DGS3MO", np.full(N, 3.0)),
    }
    w = RateRotation().weights(MarketData(prices=data.prices, macro=macro))
    # The curve inverts in the observation for day 200 (2022-10-10, Columbus Day),
    # which the Fed publishes on 2022-10-12.
    published = macro["DGS10"]["available_date"].iloc[200]
    assert published == pd.Timestamp("2022-10-12")
    assert w.loc[:published].iloc[-2]["SPY"] == 1.0
    assert w.loc[published, "SPY"] == 0.0
    assert w.loc[published, "IEF"] == 1.0


@pytest.mark.parametrize(
    "make",
    [
        lambda: MovingAverageCrossover(fast=20, slow=20),
        lambda: TimeSeriesMomentum(lookback=0),
        lambda: MeanReversion(lookback=1),
        lambda: RateRotation(smoothing=0),
        lambda: RandomSignal(hold=0),
        lambda: RandomSignal(seed=-1),
    ],
)
def test_invalid_parameters_are_rejected(make: object) -> None:
    with pytest.raises(ValueError):
        make()  # type: ignore[operator]


def test_rotation_waits_until_both_assets_trade() -> None:
    data = _market()
    close = data.prices.close.copy()
    open_ = data.prices.open.copy()
    close.loc[DATES[:100], "IEF"] = np.nan
    open_.loc[DATES[:100], "IEF"] = np.nan
    late = MarketData(prices=Prices(open=open_, close=close), macro=data.macro)
    w = RateRotation().weights(late)
    assert w.loc[DATES[:100]].isna().all().all()
    assert run(w, late.prices).start == DATES[101]


def test_random_signal_does_not_depend_on_the_sample_length() -> None:
    data = _market()
    short = MarketData(prices=Prices(open=data.prices.open[:123], close=data.prices.close[:123]))
    strategy = RandomSignal(seed=7, hold=4)
    full = strategy.weights(data)
    pd.testing.assert_frame_equal(strategy.weights(short), full.iloc[:123])
    w = full["SPY"].to_numpy()
    assert set(np.unique(w)) == {-1.0, 1.0}
    assert (w.reshape(-1, 4) == w.reshape(-1, 4)[:, :1]).all()  # one direction per block
