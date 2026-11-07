"""Data quality checks. Thresholds and their basis are in D011."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

import numpy as np
import pandas as pd

PRICE_FIELDS = ["open", "high", "low", "close", "adj_close"]
ADJ_TOL = 1e-5  # relative error allowed in the adjustment factor
OHLC_TOL = 1e-6  # relative slack for rounding in high/low bounds
JUMP_Z = 10.0  # robust z-score of a daily log return that is flagged for review
GAP_SHARE = 0.5  # a date is a trading day if at least this share of live tickers has a bar


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    check: str
    severity: Severity
    symbol: str
    date: str | None
    detail: str


def _dates(idx: pd.Index) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.DatetimeIndex(idx)]


def _issues(
    check: str, severity: Severity, symbol: str, mask: pd.Series, detail: pd.Series | str
) -> list[Issue]:
    hits = mask[mask.fillna(False).astype(bool)].index
    details = [detail] * len(hits) if isinstance(detail, str) else list(detail.loc[hits])
    return [
        Issue(check, severity, symbol, d, str(x))
        for d, x in zip(_dates(hits), details, strict=True)
    ]


def _check_ticker(ticker: str, df: pd.DataFrame) -> list[Issue]:
    issues: list[Issue] = []
    err = Severity.ERROR
    if df.index.has_duplicates:
        issues.append(Issue("duplicate_dates", err, ticker, None, "index has duplicates"))
        return issues
    prices = df[PRICE_FIELDS]
    issues += _issues("missing_price", err, ticker, prices.isna().any(axis=1), "NaN price")
    issues += _issues("nonpositive_price", err, ticker, (prices <= 0).any(axis=1), "price <= 0")
    body_lo = df[["open", "close"]].min(axis=1)
    body_hi = df[["open", "close"]].max(axis=1)
    bad_ohlc = (body_lo < df["low"] * (1 - OHLC_TOL)) | (body_hi > df["high"] * (1 + OHLC_TOL))
    issues += _issues("ohlc", err, ticker, bad_ohlc, "open/close outside low-high")

    # Adj Close / Close may only change on ex-dividend dates, by 1 - D / C[t-1].
    factor = df["adj_close"] / df["close"]
    step = factor.shift(1) / factor
    expected = 1 - df["dividends"] / df["close"].shift(1)
    deviation = (step - expected).abs()
    issues += _issues(
        "adjustment",
        err,
        ticker,
        deviation > ADJ_TOL,
        deviation.map(lambda x: f"factor step off by {x:.2e}"),
    )

    log_ret = pd.Series(np.log(df["adj_close"]), index=df.index).diff()
    centered = log_ret - log_ret.median()
    scale = 1.4826 * centered.abs().median()
    if scale > 0:
        z = centered.abs() / scale
        issues += _issues(
            "jump",
            Severity.WARNING,
            ticker,
            z > JUMP_Z,
            log_ret.map(lambda r: f"log return {r:+.3f}"),
        )
    return issues


def _check_gaps(frames: Mapping[str, pd.DataFrame]) -> list[Issue]:
    present = (
        pd.DataFrame({t: pd.Series(True, index=df.index) for t, df in frames.items() if len(df)})
        .astype("boolean")
        .fillna(False)
        .astype(bool)
    )
    if present.empty:
        return []
    live = pd.DataFrame(
        {
            t: (present.index >= frames[t].index.min()) & (present.index <= frames[t].index.max())
            for t in present.columns
        },
        index=present.index,
    )
    share = present.sum(axis=1) / live.sum(axis=1)
    trading = share >= GAP_SHARE
    issues: list[Issue] = []
    for t in present.columns:
        missing = trading & live[t] & ~present[t]
        issues += _issues("gap", Severity.WARNING, t, missing, "no bar on a trading day")
    return issues


def check_prices(frames: Mapping[str, pd.DataFrame]) -> list[Issue]:
    """Check normalized price frames keyed by ticker."""
    issues: list[Issue] = []
    for ticker, df in frames.items():
        if df.empty:
            issues.append(Issue("empty", Severity.ERROR, ticker, None, "no rows"))
            continue
        issues += _check_ticker(ticker, df)
    return issues + _check_gaps(frames)


def check_macro(frames: Mapping[str, pd.DataFrame]) -> list[Issue]:
    """Check macro frames (columns date, value, available_date) keyed by series id."""
    issues: list[Issue] = []
    err = Severity.ERROR
    for series_id, df in frames.items():
        if df.empty:
            issues.append(Issue("empty", err, series_id, None, "no rows"))
        elif df["date"].duplicated().any():
            issues.append(Issue("duplicate_dates", err, series_id, None, "dates repeat"))
        elif df["value"].isna().any():
            issues.append(Issue("missing_value", err, series_id, None, "NaN value"))
    return issues


def build_report(issues: list[Issue], fetch_failures: Mapping[str, str]) -> dict[str, Any]:
    """JSON-ready summary; the run fails on any fetch failure or error."""
    errors = sum(i.severity is Severity.ERROR for i in issues)
    return {
        "ok": not fetch_failures and errors == 0,
        "fetch_failures": dict(fetch_failures),
        "errors": errors,
        "warnings": len(issues) - errors,
        "issues": [asdict(i) for i in issues],
    }
