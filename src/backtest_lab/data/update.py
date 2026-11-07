"""Fetch all data, run quality checks and write a report.

Usage: python -m backtest_lab.data.update [--data-dir data] [--full]

Exits non-zero if any fetch failed or any quality check found an error.
"""

import argparse
import json
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

from backtest_lab.data import macro, prices
from backtest_lab.data.fetch import FetchError
from backtest_lab.data.quality import build_report, check_macro, check_prices
from backtest_lab.data.universe import TICKERS

PAUSE_SECONDS = 1.0  # between Yahoo requests, to stay under its rate limit


def _update_price(ticker: str, raw: Path, full: bool) -> prices.UpdateKind:
    return prices.update_ticker(ticker, raw, full=full)


def run(
    data_dir: Path,
    *,
    full: bool = False,
    tickers: Sequence[str] = TICKERS,
    series: Sequence[str] = tuple(macro.SERIES),
    update_price: Callable[[str, Path, bool], object] = _update_price,
    update_macro: Callable[[str, Path], None] = macro.update_series,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    raw = data_dir / "raw"
    failures: dict[str, str] = {}
    for i, ticker in enumerate(tickers):
        if i:
            sleep(PAUSE_SECONDS)
        try:
            kind = update_price(ticker, raw, full)
            print(f"{ticker}: {kind}")
        except FetchError as exc:
            failures[ticker] = exc.reason
            print(f"{ticker}: FAILED {exc.reason}")
    for series_id in series:
        try:
            update_macro(series_id, raw)
            print(f"{series_id}: full")
        except FetchError as exc:
            failures[series_id] = exc.reason
            print(f"{series_id}: FAILED {exc.reason}")

    price_frames = {
        t: df
        for t in tickers
        if (df := prices.read_cached(raw / "prices" / f"{t}.parquet")) is not None
    }
    macro_frames = {
        s: pd.read_parquet(path)
        for s in series
        if (path := raw / "macro" / f"{s}.parquet").exists()
    }
    issues = check_prices(price_frames) + check_macro(macro_frames)
    return build_report(issues, failures)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--full", action="store_true", help="ignore the cache")
    args = parser.parse_args(argv)

    report = run(args.data_dir, full=args.full)
    path = args.data_dir / "reports" / "quality.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"errors: {report['errors']}, warnings: {report['warnings']}, report: {path}")
    for issue in report["issues"]:
        if issue["severity"] == "error":
            print(f"ERROR {issue['check']} {issue['symbol']} {issue['date']}: {issue['detail']}")
    for source, reason in report["fetch_failures"].items():
        print(f"FETCH FAILED {source}: {reason}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
