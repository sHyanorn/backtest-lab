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
from backtest_lab.data.store import connect, macro_series, price_panel
from backtest_lab.engine.backtest import Prices
from backtest_lab.strategies import MarketData
from backtest_lab.validation.report import Settings, build_report
from backtest_lab.validation.search import Grid, run_grid
from tests.api.conftest import write_cache

SWEEP = {
    "strategy": "ma_crossover",
    "axes": {"fast": [5, 10], "slow": [50, 100]},
    "fixed": {"ticker": "SPY"},
}


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
    tickers = ["IEF", "SPY"]
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
    with TestClient(create_app(data_dir, processes=processes)) as client:
        r = client.post("/api/sweeps", json=SWEEP)
        assert r.status_code == 202, r.text
        status = wait(client, r.json()["id"])
        assert status["status"] == "done", status
        assert status["done"] == status["n_trials"] == 4
        report = client.get(f"/api/sweeps/{status['id']}/report")
    grid = Grid.of(SWEEP["axes"], SWEEP["fixed"])  # type: ignore[arg-type]
    assert report.content == direct_report(data_dir, grid, "ma_crossover", "SPY")
    body = report.json()
    assert status["selected_trial"] == body["selected"]["trial"]
    assert status["selected_params"] == body["selected"]["params"]
    assert status["verdict"] == body["overall"]["verdict"]


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


@pytest.mark.parametrize("job_id", ["nope", "0" * 32, "..%2F..%2Fjobs.sqlite3", "A" * 32])
def test_unknown_or_malformed_ids_are_404(client: TestClient, job_id: str) -> None:
    assert client.get(f"/api/sweeps/{job_id}").status_code == 404
    assert client.get(f"/api/sweeps/{job_id}/report").status_code == 404


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
    with TestClient(create_app(late_macro_dir, processes=1)) as client:
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


def test_restart_fails_unfinished_sweeps_and_keeps_finished_ones(tmp_path: Path) -> None:
    write_cache(tmp_path)
    with TestClient(create_app(tmp_path, processes=1)) as client:
        done = wait(client, client.post("/api/sweeps", json=SWEEP).json()["id"])
    store = JobStore(tmp_path / "jobs")
    assert store.enqueue("f" * 32, "ma_crossover", "{}", 4, max_queued=10)
    store.close()
    with TestClient(create_app(tmp_path, processes=1)) as client:
        assert client.get(f"/api/sweeps/{done['id']}/report").status_code == 200
        orphan = client.get(f"/api/sweeps/{'f' * 32}").json()
        assert orphan["status"] == "failed"
        assert "restarted" in orphan["error"]


def test_store_enqueue_respects_the_limit(tmp_path: Path) -> None:
    store = JobStore(tmp_path)
    assert store.enqueue("a" * 32, "momentum", "{}", 2, max_queued=1)
    assert not store.enqueue("b" * 32, "momentum", "{}", 2, max_queued=1)
    assert store.get("b" * 32) is None
    store.close()


def test_stopping_the_server_cancels_the_sweep_and_its_workers(tmp_path: Path) -> None:
    write_cache(tmp_path)
    sweep = {
        "strategy": "random_signal",
        "axes": {"seed": list(range(500))},
        "fixed": {"ticker": "SPY"},
        "categorical": ["seed"],
    }
    with TestClient(create_app(tmp_path, processes=2)) as client:
        job = client.post("/api/sweeps", json=sweep).json()["id"]
        queued = client.post("/api/sweeps", json=sweep).json()["id"]
        deadline = time.monotonic() + 60
        while client.get(f"/api/sweeps/{job}").json()["done"] == 0:
            assert time.monotonic() < deadline, "sweep did not start"
            time.sleep(0.02)
        runner = client.app.state.runner  # type: ignore[attr-defined]
    assert not runner._thread.is_alive()
    assert multiprocessing.active_children() == []
    store = JobStore(tmp_path / "jobs")
    for job_id in (job, queued):
        row = store.get(job_id)
        assert row is not None
        assert (row["status"], row["error"]) == ("failed", STOPPED)
    store.close()
