import numpy as np
import pandas as pd
import pytest

from backtest_lab.data.quality import Severity, build_report, check_macro, check_prices
from tests.factories import price_frame


def _day(df: pd.DataFrame, i: int) -> str:
    return pd.Timestamp(df.index[i]).strftime("%Y-%m-%d")


def _checks(frames: dict[str, pd.DataFrame]) -> set[tuple[str, str, str | None]]:
    return {(i.check, i.symbol, i.date) for i in check_prices(frames)}


def test_clean_data_has_no_issues() -> None:
    assert check_prices({"SPY": price_frame(seed=0), "TLT": price_frame(seed=1)}) == []


def test_missing_and_nonpositive_prices_are_errors() -> None:
    df = price_frame()
    df.loc[df.index[5], "close"] = np.nan
    df.loc[df.index[7], "open"] = -1.0
    found = _checks({"SPY": df})
    assert ("missing_price", "SPY", _day(df, 5)) in found
    assert ("nonpositive_price", "SPY", _day(df, 7)) in found


def test_close_above_high_is_an_error() -> None:
    df = price_frame()
    d = df.index[3]
    ratio = df.loc[d, "high"] * 1.01 / df.loc[d, "close"]
    df.loc[d, ["close", "adj_close"]] *= ratio  # keeps the adjustment factor intact
    assert ("ohlc", "SPY", _day(df, 3)) in _checks({"SPY": df})


def test_adjustment_factor_change_without_dividend_is_an_error() -> None:
    df = price_frame()
    df.loc[df.index[10:], "adj_close"] *= 1.001
    issues = [i for i in check_prices({"SPY": df}) if i.check == "adjustment"]
    assert [i.date for i in issues] == [_day(df, 10)]
    assert issues[0].severity is Severity.ERROR


def test_wrong_dividend_adjustment_is_an_error() -> None:
    df = price_frame()
    div_day = int(np.flatnonzero(df["dividends"].to_numpy())[0])
    df.loc[df.index[div_day], "dividends"] = 1.5
    assert ("adjustment", "SPY", _day(df, div_day)) in _checks({"SPY": df})


def test_open_repeating_the_previous_close_at_a_range_edge_is_a_warning() -> None:
    df = price_frame()
    for i, edge in ((10, "low"), (20, "high"), (40, None)):
        d, prev = df.index[i], df["close"].iloc[i - 1]
        df.loc[d, "open"] = prev
        df.loc[d, "low"] = min(df.loc[d, "low"], 0.99 * prev)
        df.loc[d, "high"] = max(df.loc[d, "high"], 1.01 * prev)
        if edge is not None:
            df.loc[d, edge] = prev  # the open is also the day's low or high
    df.loc[df.index[30], "open"] = df.loc[df.index[30], "low"]  # at the low, not the close
    (issue,) = [i for i in check_prices({"SPY": df}) if i.check == "stale_open"]
    assert (issue.severity, issue.date) == (Severity.WARNING, None)  # one summary per ticker
    first, last = _day(df, 10), _day(df, 20)
    assert issue.detail == (
        "2 opens equal the previous close and the day's high or low, "
        f"{first} to {last}; by decade: 2020s 2"
    )


def test_jump_is_a_warning() -> None:
    df = price_frame(n=200)
    df.loc[df.index[150:], ["open", "high", "low", "close", "adj_close"]] *= 1.3
    issues = [i for i in check_prices({"SPY": df}) if i.check == "jump"]
    assert [i.date for i in issues] == [_day(df, 150)]
    assert issues[0].severity is Severity.WARNING


def test_missing_trading_day_is_a_gap() -> None:
    frames = {t: price_frame(seed=i) for i, t in enumerate(["SPY", "TLT", "GLD"])}
    dropped = _day(frames["GLD"], 20)
    frames["GLD"] = frames["GLD"].drop(pd.Timestamp(dropped))
    gaps = [i for i in check_prices(frames) if i.check == "gap"]
    assert [(i.symbol, i.date) for i in gaps] == [("GLD", dropped)]


def test_dividend_after_a_missing_bar_is_only_a_warning() -> None:
    frames = {t: price_frame(seed=i) for i, t in enumerate(["SPY", "TLT", "GLD"])}
    gld = frames["GLD"]
    div_day = int(np.flatnonzero(gld["dividends"].to_numpy())[0])
    frames["GLD"] = gld.drop(gld.index[div_day - 1])
    adjustment = [i for i in check_prices(frames) if i.check == "adjustment"]
    assert [(i.symbol, i.severity) for i in adjustment] == [("GLD", Severity.WARNING)]


def test_ticker_that_stops_updating_is_an_error() -> None:
    frames = {"SPY": price_frame(n=60), "TLT": price_frame(n=20, seed=1)}
    stale = [i for i in check_prices(frames) if i.check == "stale"]
    assert [(i.symbol, i.severity, i.date) for i in stale] == [
        ("TLT", Severity.ERROR, _day(frames["TLT"], 19))
    ]


def test_dates_outside_a_tickers_history_are_not_gaps() -> None:
    frames = {"SPY": price_frame(n=60), "NEW": price_frame(n=30, start="2024-02-01")}
    assert [i for i in check_prices(frames) if i.check == "gap"] == []


def test_macro_checks() -> None:
    good = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-02-01"]),
            "value": [1.0, 2.0],
            "available_date": pd.to_datetime(["2024-02-29", "2024-03-31"]),
        }
    )
    dup = pd.concat([good, good.iloc[[0]]])
    freqs = {"OK": "monthly", "DUP": "monthly", "EMPTY": "monthly", "OLD": "daily"}
    frames = {"OK": good, "DUP": dup, "EMPTY": good.iloc[:0], "OLD": good}
    issues = check_macro(frames, freqs, pd.Timestamp("2024-03-15"))
    assert {(i.check, i.symbol, i.severity) for i in issues} == {
        ("duplicate_dates", "DUP", Severity.ERROR),
        ("empty", "EMPTY", Severity.ERROR),
        ("stale", "OLD", Severity.WARNING),
    }


@pytest.mark.parametrize(("failures", "ok"), [({}, True), ({"SPY": "FetchError: 429"}, False)])
def test_report_fails_on_fetch_failure(failures: dict[str, str], ok: bool) -> None:
    report = build_report([], failures)
    assert report["ok"] is ok
    assert report["fetch_failures"] == failures
