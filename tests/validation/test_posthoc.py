import json
from pathlib import Path

import numpy as np
import pytest

from backtest_lab.validation.demo import SEARCHES, Search
from backtest_lab.validation.pbo import cscv
from backtest_lab.validation.posthoc import analyse, drawdown_episodes, trial_counts
from backtest_lab.validation.report import (
    Settings,
    build_report,
    enough_trials,
    min_backtest_verdict,
    probability_verdict,
)
from backtest_lab.validation.report_schema import Report
from backtest_lab.validation.search import Grid, run_grid
from tests.factories import synthetic_market

RESULTS = Path(__file__).parents[2] / "results"


def test_drawdown_episodes_deepest_first() -> None:
    # wealth 1.1, 0.88, 0.924, 1.1088, 0.99792, 0.898128, 1.1675664
    r = np.array([0.1, -0.2, 0.05, 0.2, -0.1, -0.1, 0.3])
    first, second = drawdown_episodes(r, top=3)
    assert (first.peak, first.trough) == (0, 1)
    assert first.depth == pytest.approx(-0.2)
    assert (second.peak, second.trough) == (3, 5)
    assert second.depth == pytest.approx(0.898128 / 1.1088 - 1)
    assert drawdown_episodes(r, top=1) == [first]


def test_drawdown_from_the_start_and_unrecovered() -> None:
    (start,) = drawdown_episodes(np.array([-0.1, 0.05, 0.2]))
    assert (start.peak, start.trough) == (-1, 0)  # the starting wealth of 1 is the high
    assert start.depth == pytest.approx(-0.1)
    (episode,) = drawdown_episodes(np.array([0.1, -0.3, 0.1]))
    assert (episode.peak, episode.trough) == (0, 1)
    assert drawdown_episodes(np.array([0.01, 0.02])) == []


def test_analyse_is_consistent_with_the_registered_methods() -> None:
    data = synthetic_market(n=1500, seed=11, drift=0.0004)
    grid = Grid.of(
        {"fast": [5, 10], "slow": [40, 80], "allow_short": [False, True]}, {"ticker": "SPY"}
    )
    result = analyse(Search("ma", "ma_crossover", grid), data, processes=1)
    x = run_grid("ma_crossover", grid, data, processes=1).returns.to_numpy()
    assert result["pbo"]["full_grid"] == cscv(x).pbo
    assert result["pbo"]["long_only_half"] == cscv(x[:, ::2]).pbo  # allow_short is the last axis
    assert result["long_only_half_dsr"]["n_trials"] == 4
    assert 0 <= result["cscv"]["long_only_winner_share"] <= 1
    assert result["cscv"]["combinations"] == 12_870
    assert 0 <= result["selected_profile"]["time_in_market"] <= 1
    assert result["benchmark_profile"]["time_in_market"] == 1
    for episode in result["benchmark_drawdowns"]:
        assert episode["benchmark_return"] < 0


def test_trial_counts_agree_with_the_report() -> None:
    data = synthetic_market(n=1600, seed=5)
    grid = Grid.of({"seed": list(range(12))}, {"ticker": "SPY", "hold": 5})
    trials = run_grid("random_signal", grid, data, processes=1)
    report = build_report(trials, data, "SPY", Settings(is_days=500, oos_days=250))
    counts = trial_counts(trials.returns.to_numpy())
    dsr = report.checks.deflated_sharpe.metrics
    first, second = counts["average_correlation"], counts["eigenvalue"]
    assert first["n_effective"] == dsr.n_effective_correlation
    assert second["n_effective"] == dsr.n_effective_eigenvalue
    used = max(first, second, key=lambda e: e["n_effective"])
    assert (used["n_effective"], used["dsr"]) == (dsr.n_effective, dsr.dsr)
    btl = report.checks.min_backtest_length.metrics
    assert (used["min_backtest_years"], counts["years"]) == (btl.min_backtest_years, btl.years)


@pytest.mark.parametrize("name", [s.name for s in SEARCHES])
def test_registered_verdicts_hold_under_the_two_estimate_rule(name: str) -> None:
    # The registered reports are format 1.0 and are never rewritten (D032). The rule of D041
    # was adopted after them; a rerun of the searches shows it would have judged them alike.
    text = (RESULTS / "demo" / f"{name}.json").read_text(encoding="utf-8")
    registered = Report.model_validate_json(text)
    assert registered.schema_version == "1.0"
    counts = json.loads((RESULTS / "posthoc" / "effective_trials.json").read_text("utf-8"))
    rerun = counts["searches"][name]
    first, second = rerun["average_correlation"], rerun["eigenvalue"]

    dsr = registered.checks.deflated_sharpe
    assert dsr.metrics.n_effective_eigenvalue is None  # 1.0 has the first estimate only
    # The rerun used prices fetched later; it reproduces the registered estimate.
    assert first["n_effective"] == pytest.approx(dsr.metrics.n_effective, abs=0.01)
    assert first["dsr"] == pytest.approx(dsr.metrics.dsr, abs=0.001)

    assert enough_trials(first["n_effective"], second["n_effective"])  # PBO and DSR are judged
    used = max(first, second, key=lambda e: e["n_effective"])
    assert probability_verdict(used["dsr"]) == dsr.verdict
    btl = registered.checks.min_backtest_length
    assert min_backtest_verdict(used["min_backtest_years"], rerun["years"]) == btl.verdict
