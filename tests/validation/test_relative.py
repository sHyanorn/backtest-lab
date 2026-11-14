"""The registered study runner on a synthetic returns-only market (D043)."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest_lab.data.store import price_file, raw_dir, write_parquet_atomic
from backtest_lab.engine.backtest import Costs, Prices, run
from backtest_lab.strategies import MarketData
from backtest_lab.validation import relative
from backtest_lab.validation.relative import (
    FRENCH_VARIANTS,
    MARKET,
    SELECTED,
    Sample,
    cash_returns,
    decision,
    prices_sha256,
    run_sample,
    yahoo_sample,
)
from tests.factories import price_frame


def test_cash_earns_the_rate_beside_the_position_earning_the_day() -> None:
    dates = pd.bdate_range("2024-01-02", periods=5).as_unit("us")
    prices = Prices.from_returns(pd.DataFrame({"M": [0.01, 0.02, -0.03, 0.04, 0.05]}, dates))
    target = pd.DataFrame({"M": [0.0, 1.0, 1.0, 0.0, 0.0]}, index=dates)
    result = run(target, prices)
    rf = pd.Series(0.001, index=dates)
    got = cash_returns(result.returns, result.weights["M"], result.costs, rf)
    c = Costs().rate
    # In cash on days 1 and 2 (entering at close 2), invested on days 3 and 4.
    expected = result.returns + np.array([0.001, 0.001 * (1 - c), 0.0, 0.0])
    pd.testing.assert_series_equal(got, expected, check_names=False)


def _sample(rf: float, seed: int = 0) -> Sample:
    dates = pd.bdate_range("1957-01-01", periods=900).as_unit("us")
    rng = np.random.default_rng(seed)
    returns = pd.DataFrame({MARKET: rng.normal(4e-4, 0.01, len(dates))}, index=dates)
    data = MarketData(prices=Prices.from_returns(returns))
    return Sample("french", MARKET, data, FRENCH_VARIANTS, 0.0125, pd.Series(rf, index=dates))


@pytest.fixture
def few_reps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(relative, "REPS", 200)


@pytest.mark.usefixtures("few_reps")
def test_runs_every_family_and_resumes_from_the_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    records = run_sample(_sample(rf=0.0), tmp_path, processes=1)
    # Per strategy: the decision at four block lengths and seven other variants at one.
    assert len(records) == 2 * (4 + 7)
    assert {r["variant"] for r in records} == {v.name for v in FRENCH_VARIANTS}
    halves = {r["variant"]: r for r in records if r["strategy"] == "momentum"}
    assert halves["before_1960"]["last"] < "1960-01-04" <= halves["from_1960"]["first"]
    for r in records:
        if "selected" in r:
            assert r["variant"] == "decision" and r["mean_block"] == 10
            assert {k: r["selected"]["params"][k] for k in SELECTED[r["strategy"]]} == (
                SELECTED[r["strategy"]]
            )

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("recomputed a cached family")

    monkeypatch.setattr(relative, "compare", fail)
    monkeypatch.setattr(relative, "run_grid", fail)
    assert run_sample(_sample(rf=0.0), tmp_path, processes=1) == records


@pytest.mark.usefixtures("few_reps")
def test_cash_at_a_zero_rate_changes_nothing(tmp_path: Path) -> None:
    records = run_sample(_sample(rf=0.0), tmp_path, processes=1)
    by = {(r["strategy"], r["variant"], r["mean_block"]): r for r in records}
    for strategy in SELECTED:
        cash, zero = by[(strategy, "cash_earns_rf", 10)], by[(strategy, "decision", 10)]
        for criterion in ("sharpe_difference", "mean_difference"):
            assert cash[criterion] == zero[criterion]


@pytest.mark.usefixtures("few_reps")
def test_cash_at_a_positive_rate_helps_the_settings_out_of_the_market(tmp_path: Path) -> None:
    records = run_sample(_sample(rf=0.0002), tmp_path, processes=1)
    by = {(r["strategy"], r["variant"], r["mean_block"]): r for r in records}
    cash, zero = by[("ma_crossover", "cash_earns_rf", 10)], by[("ma_crossover", "decision", 10)]
    best_cash = cash["mean_difference"]["best"]["annualized"]
    assert best_cash > zero["mean_difference"]["best"]["annualized"]


@pytest.mark.usefixtures("few_reps")
def test_decision_adjusts_the_deciding_families_with_holm(tmp_path: Path) -> None:
    records = run_sample(_sample(rf=0.0), tmp_path, processes=1)
    out = decision(records)
    assert [(d["strategy"], d["criterion"]) for d in out] == [
        ("ma_crossover", "sharpe_difference"),
        ("ma_crossover", "mean_difference"),
        ("momentum", "sharpe_difference"),
        ("momentum", "mean_difference"),
    ]
    smallest = min(out, key=lambda d: d["p"])
    assert smallest["holm"] == pytest.approx(min(1.0, 4 * smallest["p"]))
    assert all(d["finding"] == (d["holm"] <= 0.05) for d in out)


def test_price_digest_covers_the_rows_used_and_stops_a_changed_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frame = price_frame(n=10, start="2026-10-26")  # five rows up to 2026-10-30, five after
    path = price_file(raw_dir(tmp_path), "QQQ")
    write_parquet_atomic(frame.reset_index(), path)
    used = frame.loc[: pd.Timestamp("2026-10-30")]
    text = "".join(
        f"{d:%Y-%m-%d},{float(o)!r},{float(c)!r},{float(a)!r}\n"
        for d, o, c, a in used[["open", "close", "adj_close"]].itertuples()
    )
    digest = prices_sha256(tmp_path, "QQQ")
    assert len(used) == 5 and digest == hashlib.sha256(text.encode()).hexdigest()
    later = frame.copy()
    later.loc[later.index[-1], "close"] *= 1.01
    write_parquet_atomic(later.reset_index(), path)
    assert prices_sha256(tmp_path, "QQQ") == digest
    revised = frame.copy()
    revised.loc[revised.index[0], "adj_close"] *= 1.0001
    write_parquet_atomic(revised.reset_index(), path)
    monkeypatch.setitem(relative.ETF_ROWS_SHA256, "QQQ", digest)
    with pytest.raises(ValueError, match="differ from those registered"):
        yahoo_sample(tmp_path, "QQQ", "etf", 0.05)
