"""The pre-registered demo (D021): run each search on the local data cache and write
its credibility report.

Usage: python -m backtest_lab.validation.demo [--data-dir data] [--out results/demo]
       [--processes N]
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtest_lab.data.store import connect, load_prices, raw_dir
from backtest_lab.engine.backtest import Prices
from backtest_lab.strategies import MarketData
from backtest_lab.validation.report import Settings, build_report
from backtest_lab.validation.search import Grid, run_grid

TICKER = "SPY"
START = pd.Timestamp("1993-01-29")
END = pd.Timestamp("2026-10-30")
SETTINGS = Settings()  # D021 uses the defaults


@dataclass(frozen=True)
class Search:
    name: str
    strategy: str
    grid: Grid


SEARCHES = (
    Search(
        "ma_crossover",
        "ma_crossover",
        Grid.of(
            {
                "fast": [5, 10, 15, 20, 25, 30, 40, 50],
                "slow": [60, 80, 100, 120, 150, 180, 200, 250],
                "allow_short": [False, True],
            },
            {"ticker": TICKER},
        ),
    ),
    Search(
        "momentum",
        "momentum",
        Grid.of(
            {"lookback": list(range(42, 379, 21)), "allow_short": [False, True]}, {"ticker": TICKER}
        ),
    ),
    Search(
        "random_signal",
        "random_signal",
        Grid.of({"seed": list(range(100))}, {"ticker": TICKER, "hold": 5}),
    ),
)


def load_sample(
    data_dir: Path, ticker: str = TICKER, start: pd.Timestamp = START, end: pd.Timestamp = END
) -> MarketData:
    """Total-return adjusted prices of one ticker between `start` and `end` inclusive."""
    prices = load_prices(connect(raw_dir(data_dir)), [ticker])
    dates = prices.close.index
    keep = (dates >= start) & (dates <= end)
    if not keep.any() or dates[keep][0] != start or dates[keep][-1] != end:
        raise ValueError(f"the cache does not cover {start:%Y-%m-%d} to {end:%Y-%m-%d}")
    return MarketData(prices=Prices(open=prices.open[keep], close=prices.close[keep]))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("results/demo"))
    parser.add_argument("--processes", type=int, default=None)
    args = parser.parse_args(argv)

    data = load_sample(args.data_dir)
    args.out.mkdir(parents=True, exist_ok=True)
    for search in SEARCHES:
        trials = run_grid(search.strategy, search.grid, data, processes=args.processes)
        report = build_report(trials, data, TICKER, SETTINGS)
        path = args.out / f"{search.name}.json"
        path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
        print(f"{search.name}: {report.overall.verdict} -> {path}")


if __name__ == "__main__":
    main()
