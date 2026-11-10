import json
from pathlib import Path
from typing import Any

import pytest

from backtest_lab.data import update
from backtest_lab.data.fetch import FetchError
from backtest_lab.data.store import write_parquet_atomic
from tests.factories import price_frame


def _fake_price(fail: set[str]) -> Any:
    def fn(ticker: str, raw: Path, full: bool) -> str:
        if ticker in fail:
            raise FetchError(ticker, "YFRateLimitError: Too Many Requests")
        df = price_frame(seed=len(ticker)).reset_index()
        df.insert(0, "ticker", ticker)
        write_parquet_atomic(df, raw / "prices" / f"{ticker}.parquet")
        return "full"

    return fn


def test_failed_ticker_is_reported_and_others_still_update(tmp_path: Path) -> None:
    pauses: list[float] = []
    report = update.run(
        tmp_path,
        tickers=["SPY", "TLT", "GLD"],
        series=[],
        update_price=_fake_price({"TLT"}),
        sleep=pauses.append,
    )
    assert report["ok"] is False
    assert report["fetch_failures"] == {"TLT": "YFRateLimitError: Too Many Requests"}
    assert sorted(p.stem for p in (tmp_path / "raw" / "prices").iterdir()) == ["GLD", "SPY"]
    assert pauses == [update.PAUSE_SECONDS] * 2


def test_clean_run_is_ok(tmp_path: Path) -> None:
    report = update.run(
        tmp_path, tickers=["SPY"], series=[], update_price=_fake_price(set()), sleep=lambda s: None
    )
    assert report == {"ok": True, "fetch_failures": {}, "errors": 0, "warnings": 0, "issues": []}


@pytest.mark.parametrize(("ok", "code"), [(True, 0), (False, 1)])
def test_main_writes_report_and_sets_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, ok: bool, code: int
) -> None:
    report = {"ok": ok, "fetch_failures": {} if ok else {"SPY": "boom"}, "errors": 0}
    report |= {"warnings": 0, "issues": []}
    monkeypatch.setattr(update, "run", lambda data_dir, full: report)
    assert update.main(["--data-dir", str(tmp_path)]) == code
    written = json.loads((tmp_path / "reports" / "quality.json").read_text(encoding="utf-8"))
    assert written == report


def test_macro_failure_and_corrupt_cache_are_reported(tmp_path: Path) -> None:
    (tmp_path / "raw" / "prices").mkdir(parents=True)
    (tmp_path / "raw" / "prices" / "TLT.parquet").write_bytes(b"not parquet")

    def broken_macro(series_id: str, raw: Path) -> None:
        raise FetchError(series_id, "HTTPError: 503")

    report = update.run(
        tmp_path,
        tickers=["SPY", "TLT"],
        series=["DGS10"],
        update_price=lambda t, r, f: _fake_price(set())(t, r, f) if t == "SPY" else "full",
        update_macro=broken_macro,
        sleep=lambda s: None,
    )
    assert report["ok"] is False
    assert set(report["fetch_failures"]) == {"TLT", "DGS10"}
    assert report["fetch_failures"]["DGS10"] == "HTTPError: 503"
