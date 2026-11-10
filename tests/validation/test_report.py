import json
import math
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from backtest_lab.engine.metrics import ANNUALIZATION, max_drawdown, summarize
from backtest_lab.strategies import MarketData
from backtest_lab.validation.pbo import cscv
from backtest_lab.validation.report import (
    Settings,
    build_report,
    buy_and_hold,
    enough_trials,
    logit_histogram,
    min_backtest_verdict,
    overall_summary,
    pbo_verdict,
    probability_verdict,
    retention_verdict,
    sensitivity_verdict,
    worst,
)
from backtest_lab.validation.report_schema import CheckVerdict, Report, json_schema
from backtest_lab.validation.search import Grid, Trials, run_grid
from backtest_lab.validation.selection import best_trial, ranking_daily_sharpe
from backtest_lab.validation.sharpe_stats import (
    average_correlation,
    deflated_sharpe_ratio,
    effective_trials,
    mean_squared_correlation,
    min_backtest_length,
    min_track_record_length,
    probabilistic_sharpe_ratio,
    sharpe_moments,
)
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
    assert worst(["green", "not_assessable"]) == "yellow"  # never green (D041)
    assert worst(["not_assessable", "red"]) == "red"


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


def test_statistics_receive_the_documented_inputs() -> None:
    # METHODS Sections 5-7: the selected trial's daily Sharpe ratio, skewness and raw
    # kurtosis over all T rows, the variance of all N daily Sharpe ratios, N-hat in DSR and
    # MinBTL, and an annualized MinBTL target compared with T / 252 years.
    trials, _, report = _ma_case()
    x = trials.returns.to_numpy()
    n_days, n_trials = x.shape
    sr = ranking_daily_sharpe(x)
    m = sharpe_moments(x[:, best_trial(x)])
    variance = float(np.var(sr, ddof=1))
    by_correlation = effective_trials(average_correlation(x), n_trials)
    by_eigenvalue = effective_trials(mean_squared_correlation(x), n_trials)
    n_eff = max(by_correlation, by_eigenvalue)
    assert by_correlation != by_eigenvalue
    target = float(np.sqrt(ANNUALIZATION) * m.daily_sharpe)

    dsr = report.checks.deflated_sharpe.metrics
    assert dsr.n_effective_correlation == by_correlation
    assert dsr.n_effective_eigenvalue == by_eigenvalue
    assert (dsr.n_trials, dsr.n_effective, dsr.sharpe_variance) == (n_trials, n_eff, variance)
    assert (dsr.skewness, dsr.kurtosis) == (m.skewness, m.kurtosis)
    assert dsr.dsr == deflated_sharpe_ratio(
        m.daily_sharpe, variance, n_eff, n_days, m.skewness, m.kurtosis
    )
    assert dsr.dsr is not None and 0.05 < dsr.dsr < 0.95  # not saturated, so N vs N-hat shows

    track = report.checks.track_record.metrics
    assert track.psr == probabilistic_sharpe_ratio(
        m.daily_sharpe, 0.0, n_days, m.skewness, m.kurtosis
    )
    trl = min_track_record_length(m.daily_sharpe, 0.0, m.skewness, m.kurtosis, 0.05)
    assert track.min_track_record_years == trl / ANNUALIZATION

    btl = report.checks.min_backtest_length.metrics
    assert btl.years == n_days / ANNUALIZATION
    assert btl.n_effective == n_eff
    assert btl.target_sharpe == target
    assert btl.min_backtest_years == min_backtest_length(n_eff, target)

    assert report.checks.sensitivity.metrics.best_sharpe == np.sqrt(ANNUALIZATION) * sr.max()


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
    assert report.checks.deflated_sharpe.verdict in ("yellow", "red")
    assert report.checks.pbo.verdict != "not_assessable"  # 50 unrelated trials can be judged
    assert report.overall.verdict != "green"


def test_too_few_independent_trials_get_no_pbo_or_dsr_verdict() -> None:
    data = synthetic_market(n=2600, seed=3, drift=0.0003)
    grid = Grid.of({"fast": [5, 10], "slow": [60, 100]}, {"ticker": "SPY"})
    trials = run_grid("ma_crossover", grid, data, processes=1)
    report = build_report(trials, data, "SPY", SETTINGS)
    checks = report.checks
    dsr = checks.deflated_sharpe.metrics
    assert dsr.n_effective_correlation is not None and dsr.n_effective_eigenvalue is not None
    fewest = min(dsr.n_effective_correlation, dsr.n_effective_eigenvalue)
    for check in (checks.pbo, checks.deflated_sharpe):
        assert check.verdict == "not_assessable"
        assert check.summary == (
            f"Only about {fewest:.1f} of the 4 settings tried are independent; "
            "this check needs at least 10."
        )
    assert dsr.dsr is not None  # the figures stay in the report
    others = [c.verdict for key, c in checks if key not in ("pbo", "deflated_sharpe")]
    assert "not_assessable" not in others
    assert set(others) == {"green", "yellow"}
    assert report.overall.verdict == "yellow"
    assert report.overall.summary.startswith(
        "No check fails, but 2 of 8 are borderline (Walk-forward analysis, Parameter "
        "sensitivity) and 2 cannot be assessed (Probability of backtest overfitting, "
        "Deflated Sharpe ratio):"
    )


def test_trials_that_never_trade_do_not_count_towards_the_floor() -> None:
    data = synthetic_market(n=2600, seed=3, drift=0.0003)
    grid = Grid.of(
        {"entry_z": [1.0, *(float(z) for z in range(5, 15))]},
        {"ticker": "SPY", "lookback": 20, "allow_short": False},
    )
    trials = run_grid("mean_reversion", grid, data, processes=1)
    x = trials.returns.to_numpy()
    assert (x.std(axis=0) > 0).sum() == 1 and x.shape[1] == 11
    dsr = build_report(trials, data, "SPY", SETTINGS).checks.deflated_sharpe
    assert dsr.metrics.dsr is not None and dsr.metrics.dsr >= 0.5  # yellow if it were judged
    assert dsr.verdict == "not_assessable"
    assert dsr.summary.startswith("Only about 1.0 of the 11 settings tried")


def test_a_fail_still_counts_with_too_few_independent_trials() -> None:
    data = synthetic_market(n=2600, seed=1, drift=0.0005)
    grid = Grid.of({"fast": [5, 10, 20], "slow": [40, 60, 100]}, {"ticker": "SPY"})
    report = build_report(run_grid("ma_crossover", grid, data, processes=1), data, "SPY", SETTINGS)
    checks = report.checks
    assert checks.pbo.metrics.pbo > 0.30
    assert checks.pbo.verdict == "red"
    assert checks.pbo.summary.startswith("In 41% of 12,870 ways")
    dsr = checks.deflated_sharpe
    assert dsr.metrics.dsr is not None and dsr.metrics.dsr >= 0.95  # a pass is withheld
    assert dsr.verdict == "not_assessable"
    assert "red" not in [c.verdict for key, c in checks if key != "pbo"]
    assert report.overall.verdict == "red"
    assert report.overall.summary.startswith(
        "1 of 8 checks fail (Probability of backtest overfitting):"
    )


def test_the_reported_count_is_not_rounded_up_to_the_floor() -> None:
    data = synthetic_market(n=8000, seed=2)  # a PBO under 0.10, which the floor withholds
    grid = Grid.of({"seed": list(range(10))}, {"ticker": "SPY", "hold": 5})
    trials = run_grid("random_signal", grid, data, processes=1)
    report = build_report(trials, data, "SPY", SETTINGS)
    assert report.checks.deflated_sharpe.metrics.n_effective > 9.95
    summary = report.checks.pbo.summary
    assert summary == (
        "Only about 9.9 of the 10 settings tried are independent; this check needs at least 10."
    )


def test_ten_independent_trials_by_the_smaller_estimate_are_enough() -> None:
    assert not enough_trials(9.99, 50.0)
    assert not enough_trials(50.0, 9.99)
    assert enough_trials(10.0, 50.0)


@pytest.mark.parametrize(
    ("verdicts", "summary"),
    [
        (
            {"pbo": "not_assessable", "deflated_sharpe": "not_assessable"},
            "No check fails, but 2 of 8 cannot be assessed (Probability of backtest "
            "overfitting, Deflated Sharpe ratio): treat the selected setting's performance "
            "with caution.",
        ),
        (
            {"holdout": "yellow", "pbo": "not_assessable"},
            "No check fails, but 1 of 8 are borderline (Holdout split) and 1 cannot be "
            "assessed (Probability of backtest overfitting): treat the selected setting's "
            "performance with caution.",
        ),
    ],
)
def test_overall_summary_names_the_checks_that_cannot_be_assessed(
    verdicts: dict[str, CheckVerdict], summary: str
) -> None:
    _, _, report = _ma_case()
    changed = {
        key: check.model_copy(update={"verdict": verdicts.get(key, "green")})
        for key, check in report.checks
    }
    overall = overall_summary(report.checks.model_copy(update=changed))
    assert overall == ("yellow", summary)


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
