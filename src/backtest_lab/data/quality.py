"""Data quality checks. Thresholds and their basis are in D011."""

from collections import Counter
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
# Macro series older than this (days before the latest price date) are flagged.
MACRO_MAX_AGE = {"daily": 7, "monthly": 75}


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


def _same(a: pd.Series, b: pd.Series) -> pd.Series:
    """Equal within the OHLC rounding tolerance; False where either is NaN."""
    return (a - b).abs() <= OHLC_TOL * b.abs()


def _check_ticker(ticker: str, df: pd.DataFrame, trading: pd.DatetimeIndex) -> list[Issue]:
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
    # After a missing bar C[t-1] is unknown, so a dividend step there is only a warning.
    factor = df["adj_close"] / df["close"]
    step = factor.shift(1) / factor
    expected = 1 - df["dividends"] / df["close"].shift(1)
    deviation = (step - expected).abs()
    pos = pd.Series(trading.get_indexer(df.index), index=df.index)
    after_gap = (pos.diff() != 1) & (df["dividends"] > 0)
    detail = deviation.map(lambda x: f"factor step off by {x:.2e}")
    bad = deviation > ADJ_TOL
    issues += _issues("adjustment", err, ticker, bad & ~after_gap, detail)
    issues += _issues("adjustment", Severity.WARNING, ticker, bad & after_gap, detail)

    # An open that repeats the previous close and sits at the day's high or low is likely
    # stale; a fill there is a fill at the close that formed the signal. Old histories have
    # thousands, so they are summarized in one warning per ticker (D038).
    stale = _same(df["open"], df["close"].shift(1)) & (
        _same(df["open"], df["high"]) | _same(df["open"], df["low"])
    )
    if stale.any():
        days = pd.DatetimeIndex(df.index[stale.to_numpy()])
        decades = Counter(f"{year // 10 * 10}s" for year in days.year)
        by_decade = ", ".join(f"{d} {n}" for d, n in sorted(decades.items()))
        issues.append(
            Issue(
                "stale_open",
                Severity.WARNING,
                ticker,
                None,
                f"{len(days)} opens equal the previous close and the day's high or low, "
                f"{days[0]:%Y-%m-%d} to {days[-1]:%Y-%m-%d}; by decade: {by_decade}",
            )
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


def _trading_days(frames: Mapping[str, pd.DataFrame]) -> pd.DatetimeIndex:
    """Dates on which at least GAP_SHARE of the tickers trading at the time have a bar."""
    present = (
        pd.DataFrame({t: pd.Series(True, index=df.index.unique()) for t, df in frames.items()})
        .astype("boolean")
        .fillna(False)
        .astype(bool)
    )
    live = pd.DataFrame(
        {
            t: (present.index >= frames[t].index.min()) & (present.index <= frames[t].index.max())
            for t in present.columns
        },
        index=present.index,
    )
    share = present.sum(axis=1) / live.sum(axis=1)
    return pd.DatetimeIndex(present.index[share >= GAP_SHARE])


def check_prices(frames: Mapping[str, pd.DataFrame]) -> list[Issue]:
    """Check normalized price frames keyed by ticker."""
    issues = [
        Issue("empty", Severity.ERROR, t, None, "no rows") for t, df in frames.items() if df.empty
    ]
    frames = {t: df for t, df in frames.items() if not df.empty}
    if not frames:
        return issues
    trading = _trading_days(frames)
    latest = max(df.index.max() for df in frames.values())
    for ticker, df in frames.items():
        issues += _check_ticker(ticker, df, trading)
        if df.index.has_duplicates:
            continue
        window = trading[(trading >= df.index.min()) & (trading <= df.index.max())]
        missing = window.difference(df.index)
        issues += [
            Issue("gap", Severity.WARNING, ticker, d, "no bar on a trading day")
            for d in _dates(missing)
        ]
        last = pd.Timestamp(df.index.max())
        if last < latest:
            issues.append(
                Issue(
                    "stale",
                    Severity.ERROR,
                    ticker,
                    _dates(pd.Index([last]))[0],
                    f"last bar before the latest date {latest:%Y-%m-%d}",
                )
            )
    return issues


def check_macro(
    frames: Mapping[str, pd.DataFrame], frequencies: Mapping[str, str], as_of: pd.Timestamp
) -> list[Issue]:
    """Check macro frames (columns date, value, available_date) keyed by series id."""
    issues: list[Issue] = []
    err = Severity.ERROR
    for series_id, df in frames.items():
        if df.empty:
            issues.append(Issue("empty", err, series_id, None, "no rows"))
            continue
        if df["date"].duplicated().any():
            issues.append(Issue("duplicate_dates", err, series_id, None, "dates repeat"))
        if df["value"].isna().any():
            issues.append(Issue("missing_value", err, series_id, None, "NaN value"))
        last = pd.Timestamp(df["date"].max())
        max_age = MACRO_MAX_AGE[frequencies[series_id]]
        if (as_of - last).days > max_age:
            issues.append(
                Issue(
                    "stale",
                    Severity.WARNING,
                    series_id,
                    f"{last:%Y-%m-%d}",
                    f"older than {max_age} days at {as_of:%Y-%m-%d}",
                )
            )
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
