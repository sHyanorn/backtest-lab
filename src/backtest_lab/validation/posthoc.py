"""Post hoc analysis of the pre-registered demo (D029, docs/DEMO.md).

These questions were chosen after seeing the registered results, to explain them. The
numbers are exploratory: choosing a subset of the grid after seeing which half wins is
itself a selection, so they carry no confirmatory weight.

Usage: python -m backtest_lab.validation.posthoc [--data-dir data] [--out results/posthoc]
       [--processes N]
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from backtest_lab.engine.backtest import run
from backtest_lab.engine.metrics import ANNUALIZATION, drawdown_curve, summarize
from backtest_lab.strategies import STRATEGIES, MarketData
from backtest_lab.validation.demo import SEARCHES, SETTINGS, TICKER, Search, load_market
from backtest_lab.validation.pbo import cscv
from backtest_lab.validation.report import buy_and_hold, finite
from backtest_lab.validation.search import Trials, run_grid
from backtest_lab.validation.selection import annualize, best_trial, ranking_daily_sharpe
from backtest_lab.validation.sharpe_stats import (
    average_correlation,
    deflated_sharpe_ratio,
    dsr_inputs,
    effective_trials,
    mean_squared_correlation,
    min_backtest_length,
)

type Returns = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Episode:
    """A drawdown from a high to the lowest wealth before the next high."""

    peak: int  # position of the last return at the high; -1 for the starting wealth of 1
    trough: int  # position of the lowest wealth
    depth: float  # trough / peak - 1


def drawdown_episodes(returns: Returns, top: int = 3) -> list[Episode]:
    """The `top` deepest drawdown episodes, deepest first."""
    wealth, drawdown = drawdown_curve(returns)
    under = drawdown < 0
    episodes = []
    t = 0
    while t < len(wealth):
        if not under[t]:
            t += 1
            continue
        end = t
        while end < len(wealth) and under[end]:
            end += 1
        trough = t + int(np.argmin(wealth[t:end]))
        episodes.append(Episode(peak=t - 1, trough=trough, depth=drawdown[trough]))
        t = end
    return sorted(episodes, key=lambda e: e.depth)[:top]


def _profile(r: Returns, in_market: float) -> dict[str, float | None]:
    m = summarize(r)
    return {
        "annual_mean_return": finite(ANNUALIZATION * float(r.mean())),
        "annual_volatility": finite(m["annual_volatility"]),
        "sharpe": finite(m["sharpe"]),
        "cagr": finite(m["cagr"]),
        "max_drawdown": finite(m["max_drawdown"]),
        "time_in_market": in_market,
    }


def analyse(
    search: Search, data: MarketData, processes: int | None = None, trials: Trials | None = None
) -> dict[str, Any]:
    """Long-only vs long/short halves of a grid with an `allow_short` axis, and the
    selected trial against buy and hold. `trials` saves running the search again."""
    if trials is None:
        trials = run_grid(search.strategy, search.grid, data, processes=processes)
    x = trials.returns.to_numpy(dtype=np.float64)
    dates = trials.returns.index
    long_only = np.array([p["allow_short"] is False for p in trials.params])
    annual_sharpe = annualize(ranking_daily_sharpe(x))

    full = cscv(x, SETTINGS.blocks)
    half = x[:, long_only]
    m, half_variance = dsr_inputs(half)
    n_eff = effective_trials(average_correlation(half), half.shape[1])
    dsr = deflated_sharpe_ratio(m.daily_sharpe, half_variance, n_eff, m.n, m.skewness, m.kurtosis)

    best = best_trial(x)
    chosen = x[:, best]
    bench = buy_and_hold(TICKER, data, trials.costs).loc[dates].to_numpy(dtype=np.float64)
    strategy = STRATEGIES[search.strategy](**trials.params[best])
    held = run(strategy.weights(data), data.prices, trials.costs).weights.loc[dates]
    in_market = float((held.abs().sum(axis=1) > 0).mean())

    def window(e: Episode) -> dict[str, Any]:
        span = slice(e.peak + 1, e.trough + 1)
        return {
            "peak": None if e.peak < 0 else dates[e.peak].strftime("%Y-%m-%d"),
            "trough": dates[e.trough].strftime("%Y-%m-%d"),
            "benchmark_return": e.depth,
            "selected_return": float(np.prod(1 + chosen[span]) - 1),
        }

    return {
        "n_trials": x.shape[1],
        "annual_sharpe_range": {
            "long_only": [
                float(annual_sharpe[long_only].min()),
                float(annual_sharpe[long_only].max()),
            ],
            "long_short": [
                float(annual_sharpe[~long_only].min()),
                float(annual_sharpe[~long_only].max()),
            ],
        },
        "cscv": {
            "combinations": len(full.winners),
            "long_only_winner_share": float(long_only[full.winners].mean()),
            "distinct_winners": len(set(full.winners.tolist())),
        },
        "pbo": {"full_grid": full.pbo, "long_only_half": cscv(half, SETTINGS.blocks).pbo},
        "long_only_half_dsr": {
            "n_trials": half.shape[1],
            "n_effective": n_eff,
            "dsr": finite(dsr),
        },
        "selected": {"trial": best, "params": trials.params[best]},
        "selected_profile": _profile(chosen, in_market),
        "benchmark_profile": _profile(bench, 1.0),
        "benchmark_drawdowns": [window(e) for e in drawdown_episodes(bench)],
    }


def trial_counts(x: Returns) -> dict[str, Any]:
    """DSR and MinBTL of the selected trial under each estimate of the independent
    trials (METHODS.md Section 5, D041)."""
    n_trials = x.shape[1]
    moments, variance = dsr_inputs(x)

    def under(n_effective: float) -> dict[str, float]:
        return {
            "n_effective": n_effective,
            "dsr": deflated_sharpe_ratio(
                moments.daily_sharpe,
                variance,
                n_effective,
                moments.n,
                moments.skewness,
                moments.kurtosis,
            ),
            "min_backtest_years": min_backtest_length(n_effective, annualize(moments.daily_sharpe)),
        }

    return {
        "n_trials": n_trials,
        "years": len(x) / ANNUALIZATION,
        "average_correlation": under(effective_trials(average_correlation(x), n_trials)),
        "eigenvalue": under(effective_trials(mean_squared_correlation(x), n_trials)),
    }


def _write(path: Path, note: str, searches: dict[str, Any]) -> None:
    result = {"post_hoc": True, "note": note, "searches": searches}
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results/posthoc"))
    parser.add_argument("--processes", type=int, default=None)
    args = parser.parse_args(argv)

    data = load_market(args.data_dir)
    runs = {s.name: run_grid(s.strategy, s.grid, data, processes=args.processes) for s in SEARCHES}
    args.out.mkdir(parents=True, exist_ok=True)
    _write(
        args.out / "long_only.json",
        "Chosen after seeing the pre-registered demo results (D021) to explain them; "
        "exploratory, with no confirmatory weight (D029).",
        {
            s.name: analyse(s, data, trials=runs[s.name])
            for s in SEARCHES
            if "allow_short" in s.grid.names
        },
    )
    _write(
        args.out / "effective_trials.json",
        "The registered searches under the rule adopted after them (D041): the selected "
        "trial's deflated Sharpe ratio and minimum backtest length with each estimate of "
        "the independent trials. The registered reports keep their verdicts (D032).",
        {name: trial_counts(t.returns.to_numpy(dtype=np.float64)) for name, t in runs.items()},
    )


if __name__ == "__main__":
    main()
