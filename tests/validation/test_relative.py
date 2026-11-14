"""The registered study runner on a synthetic returns-only market (D043)."""

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, NoReturn

import numpy as np
import pandas as pd
import pytest

from backtest_lab.data import french
from backtest_lab.data.store import price_file, raw_dir, write_parquet_atomic
from backtest_lab.engine.backtest import Costs, Prices, run
from backtest_lab.strategies import MarketData
from backtest_lab.validation import relative
from backtest_lab.validation.relative import (
    ETFS,
    FRENCH_VARIANTS,
    GRIDS,
    MARKET,
    SELECTED,
    YAHOO_VARIANTS,
    Sample,
    cash_returns,
    decision,
    etfs,
    french_sample,
    prices_sha256,
    run_sample,
    yahoo_sample,
)
from backtest_lab.validation.snooping import Criterion
from tests.factories import french_zip, price_frame

CODE = "commit a"


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
    records = run_sample(_sample(rf=0.0), tmp_path, CODE, processes=1)
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
    assert run_sample(_sample(rf=0.0), tmp_path, CODE, processes=1) == records


class Computed(Exception):
    pass


@pytest.mark.usefixtures("few_reps")
def test_the_cache_serves_only_the_same_code_settings_and_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_sample(_sample(rf=0.0), tmp_path, CODE, processes=1)

    def compute(*args: object) -> NoReturn:
        raise Computed

    monkeypatch.setattr(relative, "matrices", compute)

    def computes(sample: Sample, code: str = CODE, reps: int = 200, seed: int = 0) -> bool:
        with monkeypatch.context() as m:
            m.setattr(relative, "REPS", reps)
            m.setattr(relative, "SEED", seed)
            try:
                run_sample(sample, tmp_path, code, processes=1)
            except Computed:
                return True
            return False

    assert not computes(_sample(rf=0.0))
    assert computes(_sample(rf=0.0), code="commit b")
    assert computes(_sample(rf=0.0), reps=300)
    assert computes(_sample(rf=0.0), seed=1)
    assert computes(replace(_sample(rf=0.0), stepm_alpha=0.05))
    assert computes(_sample(rf=0.0, seed=1))  # other returns
    assert computes(_sample(rf=0.0002))


@pytest.mark.usefixtures("few_reps")
def test_cash_at_a_zero_rate_changes_nothing(tmp_path: Path) -> None:
    records = run_sample(_sample(rf=0.0), tmp_path, CODE, processes=1)
    by = {(r["strategy"], r["variant"], r["mean_block"]): r for r in records}
    for strategy in SELECTED:
        cash, zero = by[(strategy, "cash_earns_rf", 10)], by[(strategy, "decision", 10)]
        for criterion in ("sharpe_difference", "mean_difference"):
            assert cash[criterion] == zero[criterion]


@pytest.mark.usefixtures("few_reps")
def test_cash_at_a_positive_rate_helps_the_settings_out_of_the_market(tmp_path: Path) -> None:
    records = run_sample(_sample(rf=0.0002), tmp_path, CODE, processes=1)
    by = {(r["strategy"], r["variant"], r["mean_block"]): r for r in records}
    cash, zero = by[("ma_crossover", "cash_earns_rf", 10)], by[("ma_crossover", "decision", 10)]
    best_cash = cash["mean_difference"]["best"]["annualized"]
    assert best_cash > zero["mean_difference"]["best"]["annualized"]


@pytest.mark.usefixtures("few_reps")
def test_decision_adjusts_the_deciding_families_with_holm(tmp_path: Path) -> None:
    records = run_sample(_sample(rf=0.0), tmp_path, CODE, processes=1)
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


def test_the_eight_etfs_share_one_holm_adjustment_and_stepm_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    market = _sample(rf=0.0).data
    monkeypatch.setattr(
        relative,
        "yahoo_sample",
        lambda data_dir, ticker, name, alpha: Sample(name, ticker, market, YAHOO_VARIANTS, alpha),
    )
    levels = {}

    def run(sample: Sample, cache: Path, code: str, processes: int | None) -> list[dict[str, Any]]:
        levels[sample.instrument] = sample.stepm_alpha
        family = {"instrument": sample.instrument, "variant": "decision", "mean_block": 10.0}
        p = {c.value: {"spa": {"consistent": 0.001}} for c in Criterion}
        return [{**family, "strategy": s, **p} for s in GRIDS]

    monkeypatch.setattr(relative, "run_sample", run)
    out = etfs(tmp_path, tmp_path, CODE, processes=1)
    assert levels == dict.fromkeys(ETFS, 0.05 / 32)
    # Holm over all 32 deciding families: 32 p; separately per ETF it would be 4 p.
    assert [d["holm"] for d in out["decision"]] == pytest.approx([0.032] * 32)


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


def test_french_digest_stops_a_changed_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [
        "19930127,    0.10,    0.20,   -0.10,    0.010",
        "19930128,   -0.30,    0.10,    0.00,    0.010",
    ]
    path = french.zip_file(raw_dir(tmp_path))
    path.parent.mkdir(parents=True)
    path.write_bytes(french_zip(rows))
    digest = french.rows_sha256(path.read_bytes(), relative.FRENCH_END)
    monkeypatch.setattr(relative, "FRENCH_ROWS_SHA256", digest)
    assert french_sample(tmp_path)[1]["rows"] == 2
    path.write_bytes(french_zip([rows[0], rows[1].replace("-0.30", "-0.31")]))
    with pytest.raises(ValueError, match="differ from those registered"):
        french_sample(tmp_path)


def test_french_sample_counts_saturday_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [  # a Friday, a Saturday and a Monday
        "19260709,    0.10,    0.20,   -0.10,    0.010",
        "19260710,   -0.30,    0.10,    0.00,    0.010",
        "19260712,    0.20,    0.00,    0.10,    0.010",
    ]
    path = french.zip_file(raw_dir(tmp_path))
    path.parent.mkdir(parents=True)
    path.write_bytes(french_zip(rows))
    digest = french.rows_sha256(path.read_bytes(), relative.FRENCH_END)
    monkeypatch.setattr(relative, "FRENCH_ROWS_SHA256", digest)
    assert french_sample(tmp_path)[1]["saturday_rows"] == 1
