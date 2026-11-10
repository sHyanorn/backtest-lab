import json
import multiprocessing
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backtest_lab.api import jobs, main
from backtest_lab.api.jobs import STOPPED, JobStore
from backtest_lab.api.main import create_app
from backtest_lab.data.storage import write_parquet_atomic
from backtest_lab.data.store import connect, macro_series, price_panel
from backtest_lab.engine.backtest import Prices
from backtest_lab.strategies import MarketData
from backtest_lab.validation.report import Settings, build_report
from backtest_lab.validation.search import Grid, run_grid
from tests.api.conftest import N_DAYS, local_client, write_cache
from tests.factories import price_frame

SWEEP = {
    "strategy": "ma_crossover",
    "axes": {"fast": [5, 10], "slow": [50, 100]},
    "fixed": {"ticker": "SPY"},
}

# Long enough to still be running when a test stops the server.
LONG_SWEEP = {
    "strategy": "random_signal",
    "axes": {"seed": list(range(500))},
    "fixed": {"ticker": "SPY"},
    "categorical": ["seed"],
}

# The grid the API builds from SWEEP: every other parameter fixed at its default.
GRID = Grid.of(SWEEP["axes"], {"ticker": "SPY", "allow_short": False})  # type: ignore[arg-type]


def wait(client: TestClient, job_id: str, timeout: float = 120.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body: dict[str, Any] = client.get(f"/api/sweeps/{job_id}").json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.05)
    raise AssertionError("sweep did not finish")


def direct_report(data_dir: Path, grid: Grid, strategy: str, benchmark: str) -> bytes:
    """The report computed without the API, as the demo runner does."""
    con = connect(data_dir / "raw")
    tickers = [benchmark]
    raw = {f: price_panel(con, tickers, f) for f in ("open", "close", "adj_close")}
    data = MarketData(
        prices=Prices.from_raw(raw["open"], raw["close"], raw["adj_close"]),
        macro={s: macro_series(con, s) for s in ("DGS10", "DGS3MO")},
    )
    trials = run_grid(strategy, grid, data, processes=1)
    report = build_report(trials, data, benchmark, Settings())
    return (report.model_dump_json(indent=2) + "\n").encode()


@pytest.mark.parametrize("processes", [1, 2])
def test_report_is_byte_identical_to_the_direct_pipeline(data_dir: Path, processes: int) -> None:
    with local_client(create_app(data_dir, processes=processes)) as client:
        r = client.post("/api/sweeps", json=SWEEP)
        assert r.status_code == 202, r.text
        status = wait(client, r.json()["id"])
        assert status["status"] == "done", status
        assert status["done"] == status["n_trials"] == 4
        report = client.get(f"/api/sweeps/{status['id']}/report")
    assert report.content == direct_report(data_dir, GRID, "ma_crossover", "SPY")
    body = report.json()
    assert status["selected_trial"] == body["selected"]["trial"]
    assert status["selected_params"] == body["selected"]["params"]
    assert status["verdict"] == body["overall"]["verdict"]


def test_report_states_default_parameters(client: TestClient) -> None:
    sweep = {"strategy": "rate_rotation", "axes": {"threshold": [0.0, 0.5]}}
    status = wait(client, client.post("/api/sweeps", json=sweep).json()["id"])
    assert status["status"] == "done", status
    report = client.get(f"/api/sweeps/{status['id']}/report").json()
    assert report["strategy"]["fixed"] == {
        "risk_on": "SPY",
        "risk_off": "IEF",
        "long_rate": "DGS10",
        "short_rate": "DGS3MO",
        "smoothing": 1,
    }
    assert report["benchmark"]["name"] == "SPY buy and hold"


def test_benchmark_does_not_limit_the_length_check(tmp_path: Path) -> None:
    # IEF lists 800 days after SPY, so the two share fewer days than a report needs. Buy
    # and hold is flat before it lists; that is not a reason to reject the sweep.
    spy = price_frame(n=N_DAYS, start="2010-01-04", seed=0)
    for ticker, df in (("SPY", spy), ("IEF", spy.iloc[800:])):
        frame = df.reset_index().assign(ticker=ticker)
        write_parquet_atomic(frame, tmp_path / "raw" / "prices" / f"{ticker}.parquet")
    with local_client(create_app(tmp_path, processes=1)) as client:
        r = client.post("/api/sweeps", json=SWEEP | {"benchmark": "IEF"})
        assert r.status_code == 202, r.text
        assert wait(client, r.json()["id"])["status"] == "done"


def test_a_gap_in_the_traded_ticker_keeps_the_traded_dates(tmp_path: Path) -> None:
    # QQQ misses a bar on which the benchmark trades. The sweep runs on QQQ's own dates,
    # as /api/backtests does, instead of a NaN row that blanks the averages (D039).
    spy = price_frame(n=N_DAYS, start="2010-01-04", seed=0)
    for ticker, df in (("SPY", spy), ("QQQ", spy.drop(spy.index[900]))):
        frame = df.reset_index().assign(ticker=ticker)
        write_parquet_atomic(frame, tmp_path / "raw" / "prices" / f"{ticker}.parquet")
    sweep = SWEEP | {"fixed": {"ticker": "QQQ"}, "benchmark": "SPY"}
    with local_client(create_app(tmp_path, processes=1)) as client:
        status = wait(client, client.post("/api/sweeps", json=sweep).json()["id"])
        assert status["status"] == "done", status
        report = client.get(f"/api/sweeps/{status['id']}/report")

    con = connect(tmp_path / "raw")
    raw = {f: price_panel(con, ["QQQ", "SPY"], f) for f in ("open", "close", "adj_close")}
    prices = Prices.from_raw(raw["open"], raw["close"], raw["adj_close"])
    traded = prices.close["QQQ"].notna()
    data = MarketData(prices=Prices(open=prices.open[traded], close=prices.close[traded]))
    grid = Grid.of(SWEEP["axes"], {"ticker": "QQQ", "allow_short": False})  # type: ignore[arg-type]
    expected = build_report(run_grid("ma_crossover", grid, data, processes=1), data, "SPY")
    assert report.content == (expected.model_dump_json(indent=2) + "\n").encode()


def test_categorical_axis_reaches_the_report(client: TestClient) -> None:
    sweep = {
        "strategy": "random_signal",
        "axes": {"seed": [3, 1, 2]},
        "fixed": {"ticker": "SPY"},
        "categorical": ["seed"],
    }
    status = wait(client, client.post("/api/sweeps", json=sweep).json()["id"])
    assert status["status"] == "done", status
    sensitivity = client.get(f"/api/sweeps/{status['id']}/report").json()["checks"]["sensitivity"]
    assert sensitivity["details"]["heatmap"] is None  # seeds have no neighbours (D019)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"strategy": "nope"}, "unknown strategy"),
        ({"axes": {"window": [5]}}, "no parameter"),
        ({"axes": {"fast": [5.5]}}, "must be int"),
        ({"axes": {"fast": [10, 5]}}, "strictly increasing"),
        ({"axes": {"fast": [60], "slow": [50]}}, "fast < slow"),
        ({"axes": {"fast": list(range(1, 31)), "slow": list(range(31, 61))}}, "limit is 500"),
        ({"categorical": ["slow2"]}, "categorical"),
        ({"fixed": {"ticker": "QQQ"}}, "no ticker data"),
        ({"fixed": {"ticker": "DGS10"}, "benchmark": "SPY"}, "no ticker data"),
        ({"axes": {"slow": [50, 2**62]}}, "within"),
        ({"start": "2015-01-01"}, "at least 1512"),
        ({"benchmark": "DGS10"}, "not a ticker"),
        ({"axes": {"ticker": ["SPY", "IEF"]}, "fixed": {}}, "set a benchmark"),
        ({"surprise": True}, "Extra inputs"),
    ],
)
def test_invalid_sweeps_are_rejected_before_queueing(
    client: TestClient, change: dict[str, Any], message: str
) -> None:
    r = client.post("/api/sweeps", json=SWEEP | change)
    assert r.status_code == 422
    assert message in r.text


@pytest.mark.parametrize("job_id", ["nope", "..%2F..%2Fjobs.sqlite3", "A" * 32, "0" * 33])
def test_malformed_ids_are_404_without_a_lookup(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, job_id: str
) -> None:
    looked_up: list[str] = []
    monkeypatch.setattr(JobStore, "get", lambda self, i: looked_up.append(i))
    assert client.get(f"/api/sweeps/{job_id}").status_code == 404
    assert client.get(f"/api/sweeps/{job_id}/report").status_code == 404
    assert looked_up == []


def test_unknown_id_is_404(client: TestClient) -> None:
    assert client.get(f"/api/sweeps/{'0' * 32}").status_code == 404
    assert client.get(f"/api/sweeps/{'0' * 32}/report").status_code == 404


def test_queue_limit_is_429(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "MAX_QUEUED", 0)
    assert client.post("/api/sweeps", json=SWEEP).status_code == 429


@pytest.fixture
def late_macro_dir(tmp_path: Path) -> Path:
    """Rates that start 600 days after the prices: the length check passes on prices,
    but the trials share too few days for a report."""
    write_cache(tmp_path)
    for series_id in ("DGS10", "DGS3MO"):
        path = tmp_path / "raw" / "macro" / f"{series_id}.parquet"
        frame = pd.read_parquet(path)
        frame.iloc[600:].to_parquet(path, index=False)
    return tmp_path


def test_failed_sweep_reports_a_short_reason(late_macro_dir: Path) -> None:
    sweep = {"strategy": "rate_rotation", "axes": {"threshold": [0.0, 0.5]}}
    with local_client(create_app(late_macro_dir, processes=1)) as client:
        status = wait(client, client.post("/api/sweeps", json=sweep).json()["id"])
        assert status["status"] == "failed"
        assert "need at least 1512" in status["error"]
        assert client.get(f"/api/sweeps/{status['id']}/report").status_code == 409


def test_internal_errors_hide_details(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("/home/someone/secret/path")

    monkeypatch.setattr(jobs, "run_grid", boom)
    status = wait(client, client.post("/api/sweeps", json=SWEEP).json()["id"])
    assert status["status"] == "failed"
    assert status["error"] == "internal error (RuntimeError); see the server log"


def test_restart_keeps_finished_sweeps_fails_the_interrupted_one_and_runs_the_queued(
    tmp_path: Path,
) -> None:
    write_cache(tmp_path)
    with local_client(create_app(tmp_path, processes=1)) as client:
        done = wait(client, client.post("/api/sweeps", json=SWEEP).json()["id"])
    # What a killed server leaves behind: one sweep running, others waiting.
    running, waiting, stale = "a" * 32, "b" * 32, "c" * 32
    store = JobStore(tmp_path / "jobs")
    for job_id, request in [(running, SWEEP), (waiting, SWEEP), (stale, {})]:
        assert store.enqueue(job_id, "ma_crossover", json.dumps(request), 4, max_queued=10)
    store.started(running)
    store.close()
    with local_client(create_app(tmp_path, processes=1)) as client:
        assert client.get(f"/api/sweeps/{done['id']}/report").status_code == 200
        interrupted = client.get(f"/api/sweeps/{running}").json()
        assert interrupted["status"] == "failed"
        assert "restarted" in interrupted["error"]
        assert wait(client, waiting)["status"] == "done"
        assert client.get(f"/api/sweeps/{waiting}/report").content == direct_report(
            tmp_path, GRID, "ma_crossover", "SPY"
        )
        # A stored request the server can no longer check fails instead of blocking the start.
        assert client.get(f"/api/sweeps/{stale}").json()["status"] == "failed"


def test_store_enqueue_respects_the_limit(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    assert store.enqueue("a" * 32, "momentum", "{}", 2, max_queued=1)
    assert not store.enqueue("b" * 32, "momentum", "{}", 2, max_queued=1)
    assert store.get("b" * 32) is None
    store.close()


def test_stopping_the_server_cancels_the_sweep_and_its_workers(tmp_path: Path) -> None:
    write_cache(tmp_path)
    with local_client(create_app(tmp_path, processes=2)) as client:
        job = client.post("/api/sweeps", json=LONG_SWEEP).json()["id"]
        queued = client.post("/api/sweeps", json=LONG_SWEEP).json()["id"]
        deadline = time.monotonic() + 60
        while client.get(f"/api/sweeps/{job}").json()["done"] == 0:
            assert time.monotonic() < deadline, "sweep did not start"
            time.sleep(0.02)
        runner = client.app.state.runner  # type: ignore[attr-defined]
    assert not runner._thread.is_alive()
    assert multiprocessing.active_children() == []
    store = JobStore(tmp_path / "jobs")
    stopped, kept = store.get(job), store.get(queued)
    store.close()
    assert stopped is not None and kept is not None
    assert (stopped["status"], stopped["error"]) == ("failed", STOPPED)
    assert kept["status"] == "queued"  # the next start runs it


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost"])
def test_local_host_headers_are_served(client: TestClient, host: str) -> None:
    assert client.get("/api/strategies", headers={"Host": host}).status_code == 200


@pytest.mark.parametrize("host", ["attacker.example", "127.0.0.1.attacker.example"])
def test_other_host_headers_are_rejected(client: TestClient, host: str) -> None:
    # A page on another site that resolves its own name to 127.0.0.1 sends that name.
    assert client.get("/api/strategies", headers={"Host": host}).status_code == 400
