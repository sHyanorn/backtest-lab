import json
import math
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest_lab.engine.metrics import max_drawdown, summarize
from backtest_lab.strategies import MarketData
from backtest_lab.validation.pbo import cscv
from backtest_lab.validation.report import (
    Settings,
    build_report,
    buy_and_hold,
    logit_histogram,
    min_backtest_verdict,
    pbo_verdict,
    probability_verdict,
    retention_verdict,
    sensitivity_verdict,
    worst,
)
from backtest_lab.validation.report_schema import Report, json_schema
from backtest_lab.validation.search import Grid, Trials, run_grid
from backtest_lab.validation.selection import best_trial
from tests.factories import synthetic_market

SCHEMA = Path(__file__).parents[2] / "docs" / "report.schema.json"
SETTINGS = Settings(is_days=500, oos_days=250)


@cache
def _ma_case() -> tuple[Trials, MarketData, Report]:
    data = synthetic_market(n=2600, seed=3, drift=0.0003)
    grid = Grid.of(
        {"fast": [5, 10, 20], "slow": [40, 60, 100], "allow_short": [False, True]},
        {"ticker": "SPY"},
    )
    trials = run_grid("ma_crossover", grid, data, processes=1)
    return trials, data, build_report(trials, data, "SPY", SETTINGS)


def test_retention_verdict() -> None:
    assert retention_verdict(0.1, 0.5) == "green"
    assert retention_verdict(0.1, 0.4999) == "yellow"
    assert retention_verdict(0.1, 0.0001) == "yellow"
    assert retention_verdict(0.0, 0.9) == "red"
    assert retention_verdict(-0.1, 0.9) == "red"
    assert retention_verdict(0.1, None) == "red"
    assert retention_verdict(float("nan"), 0.9) == "red"


def test_pbo_verdict() -> None:
    assert pbo_verdict(0.0) == pbo_verdict(0.10) == "green"
    assert pbo_verdict(0.1001) == pbo_verdict(0.30) == "yellow"
    assert pbo_verdict(0.3001) == pbo_verdict(1.0) == "red"


def test_probability_verdict() -> None:
    assert probability_verdict(0.95) == "green"
    assert probability_verdict(0.9499) == probability_verdict(0.5) == "yellow"
    assert probability_verdict(0.4999) == probability_verdict(None) == "red"


def test_min_backtest_verdict() -> None:
    assert min_backtest_verdict(5.0, 5.0) == "green"
    assert min_backtest_verdict(5.0, 4.99) == "red"
    assert min_backtest_verdict(None, 30.0) == "red"


def test_sensitivity_verdict() -> None:
    assert sensitivity_verdict(1.0, 0.75, True) == "green"
    assert sensitivity_verdict(1.0, 0.7499, True) == sensitivity_verdict(1.0, 0.5, True) == "yellow"
    assert sensitivity_verdict(1.0, 0.4999, True) == "red"
    assert sensitivity_verdict(0.0, 1.0, True) == sensitivity_verdict(1.0, None, True) == "red"
    assert sensitivity_verdict(1.0, None, False) == "yellow"


@pytest.mark.parametrize("n", [5, 18, 34, 100, 128])
def test_logit_histogram_counts_every_combination(n: int) -> None:
    # The winner ranks first or last OOS in many splits; those logits are +-ln N.
    x = 0.01 * np.random.default_rng(0).standard_normal((1000, n)) + np.linspace(0, 0.002, n)
    result = cscv(x)
    counts, edges = logit_histogram(result.logits, n)
    assert counts.sum() == len(result.logits) == 12_870
    assert edges[0] == -edges[-1] == pytest.approx(-math.log(n))


def test_worst() -> None:
    assert worst(["green", "yellow", "green"]) == "yellow"
    assert worst(["green", "red", "yellow"]) == "red"
    assert worst(["green"]) == "green"


def test_committed_schema_matches_the_models() -> None:
    assert SCHEMA.read_text(encoding="utf-8") == json_schema(), (
        "regenerate with: python -m backtest_lab.validation.report_schema > docs/report.schema.json"
    )


def test_report_is_deterministic_and_round_trips() -> None:
    trials, data, report = _ma_case()
    again = build_report(trials, data, "SPY", SETTINGS)
    text = report.model_dump_json(indent=2)
    assert again.model_dump_json(indent=2) == text
    assert Report.model_validate_json(text) == report
    assert "NaN" not in text and "Infinity" not in text


def test_report_contents() -> None:
    trials, data, report = _ma_case()
    x = trials.returns.to_numpy()
    best = best_trial(x)
    assert report.selected.trial == best
    assert report.selected.params == trials.params[best]
    assert report.strategy.n_trials == 18
    assert report.sample.n_days == len(x)
    assert report.selected.metrics.sharpe == pytest.approx(summarize(x[:, best])["sharpe"])

    bench = buy_and_hold("SPY", data, trials.costs).loc[trials.returns.index].to_numpy()
    assert report.benchmark.metrics.cagr == pytest.approx(summarize(bench)["cagr"])
    assert report.benchmark.difference.sharpe == pytest.approx(
        summarize(x[:, best])["sharpe"] - summarize(bench)["sharpe"]
    )

    checks = report.checks.model_dump()
    assert report.overall.verdict == worst([c["verdict"] for c in checks.values()])
    assert all(c["summary"].endswith(".") for c in checks.values())

    assert sum(report.checks.pbo.details.logits.counts) == report.checks.pbo.metrics.n_combinations

    heat = report.checks.sensitivity.details.heatmap
    assert heat is not None and (heat.x.name, heat.y and heat.y.name) == ("fast", "slow")
    assert heat.trials[heat.best.y][heat.best.x] == best


def test_weekly_series() -> None:
    trials, _, report = _ma_case()
    series = report.series
    best = trials.returns[report.selected.trial].to_numpy()
    assert len(series.dates) == len(series.selected.equity) == len(series.benchmark.drawdown)
    assert all(a < b for a, b in zip(series.dates, series.dates[1:], strict=False))
    assert series.dates[-1] == trials.returns.index[-1].date()
    assert series.selected.equity[-1] == pytest.approx(np.prod(1 + best), abs=1e-6)
    # the weekly minimum keeps the deepest daily drawdown
    assert min(series.selected.drawdown) == pytest.approx(max_drawdown(best), abs=1e-6)
    weeks = pd.DatetimeIndex(trials.returns.index).to_period("W").nunique()
    assert len(series.dates) == weeks


def test_random_signals_do_not_pass() -> None:
    data = synthetic_market(n=1500, seed=1000)
    grid = Grid.of({"seed": list(range(50))}, {"ticker": "SPY", "hold": 5})
    trials = run_grid("random_signal", grid, data, processes=1)
    report = build_report(trials, data, "SPY", Settings(is_days=250, oos_days=125))
    assert report.checks.deflated_sharpe.verdict != "green"
    assert report.overall.verdict != "green"


def test_sensitivity_without_neighbours_cannot_be_assessed() -> None:
    data = synthetic_market(n=1600, seed=4)
    grid = Grid.of({"fast": [10], "slow": [40], "allow_short": [False, True]}, {"ticker": "SPY"})
    trials = run_grid("ma_crossover", grid, data, processes=1)
    check = build_report(trials, data, "SPY", SETTINGS).checks.sensitivity
    assert check.verdict == "yellow"
    assert check.metrics.n_neighbours == 0 and check.metrics.retention is None
    assert check.details.heatmap is None
    assert check.summary.startswith("No ordered parameter takes more than one value")


def test_report_states_the_minimum_sample() -> None:
    data = synthetic_market(n=1400)
    trials = run_grid("ma_crossover", Grid.of({"fast": [5, 10], "slow": [40]}), data, processes=1)
    assert Settings().min_days == 1260 + 252
    with pytest.raises(ValueError, match="share 1360 days; these settings need at least 1512"):
        build_report(trials, data, "SPY")


def test_benchmark_takes_no_part_in_the_verdicts() -> None:
    data = synthetic_market(n=2000, tickers=("SPY", "IEF"), seed=5, drift=(0.0003, 0.0))
    grid = Grid.of({"fast": [5, 10], "slow": [40, 60]}, {"ticker": "SPY"})
    trials = run_grid("ma_crossover", grid, data, processes=1)
    spy = build_report(trials, data, "SPY", SETTINGS)
    ief = build_report(trials, data, "IEF", SETTINGS)
    assert spy.benchmark.metrics != ief.benchmark.metrics
    assert spy.checks == ief.checks
    assert spy.overall.verdict == ief.overall.verdict
    assert spy.overall.summary == ief.overall.summary


def test_report_needs_two_trials() -> None:
    data = synthetic_market(n=300)
    trials = run_grid("ma_crossover", Grid.of({"fast": [5], "slow": [20]}), data, processes=1)
    with pytest.raises(ValueError, match="two trials"):
        build_report(trials, data, "SPY")


def test_json_keeps_check_order_for_the_dashboard() -> None:
    _, _, report = _ma_case()
    keys = list(json.loads(report.model_dump_json())["checks"])
    assert keys == [
        "holdout",
        "walk_forward",
        "purged_cv",
        "pbo",
        "deflated_sharpe",
        "track_record",
        "min_backtest_length",
        "sensitivity",
    ]
