"""Sweeps through a real uvicorn server whose grid search uses worker processes, with
the platform's default start method (forkserver on Linux, spawn on Windows)."""

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx2
import pytest

from tests.api.conftest import write_cache
from tests.api.test_sweeps import GRID, LONG_SWEEP, SWEEP, direct_report

SCRIPTS = Path(sys.executable).parent
UVICORN = SCRIPTS / ("uvicorn.exe" if sys.platform == "win32" else "uvicorn")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@contextmanager
def _serve(
    tmp_path: Path, launcher: list[str]
) -> Iterator[tuple[subprocess.Popen[bytes], httpx2.Client]]:
    """A server on a synthetic cache with two worker processes, once it answers."""
    write_cache(tmp_path)
    port = _free_port()
    env = os.environ | {"BACKTEST_LAB_DATA_DIR": str(tmp_path), "BACKTEST_LAB_PROCESSES": "2"}
    cmd = [*launcher, "backtest_lab.api.main:app", "--host", "127.0.0.1", "--port", str(port)]
    # A file, not a pipe, so the server never blocks on output.
    with (tmp_path / "server.log").open("w", encoding="utf-8") as out:
        server = subprocess.Popen(
            [*cmd, "--no-access-log"], env=env, cwd=tmp_path, stdout=out, stderr=subprocess.STDOUT
        )
        try:
            with httpx2.Client(base_url=f"http://127.0.0.1:{port}", timeout=30) as client:
                deadline = time.monotonic() + 60
                while True:
                    try:
                        if client.get("/api/strategies").status_code == 200:
                            break
                    except httpx2.TransportError:
                        pass
                    if server.poll() is not None or time.monotonic() > deadline:
                        raise AssertionError("server did not start")
                    time.sleep(0.2)
                yield server, client
        finally:
            server.terminate()
            server.wait(timeout=30)


@pytest.mark.parametrize(
    "launcher", [[str(UVICORN)], [sys.executable, "-m", "uvicorn"]], ids=["script", "module"]
)
def test_sweep_under_uvicorn_with_worker_processes(tmp_path: Path, launcher: list[str]) -> None:
    with _serve(tmp_path, launcher) as (_, client):
        r = client.post("/api/sweeps", json=SWEEP)
        assert r.status_code == 202, r.text
        job = r.json()["id"]
        deadline = time.monotonic() + 120
        while (status := client.get(f"/api/sweeps/{job}").json())["status"] not in (
            "done",
            "failed",
        ):
            assert time.monotonic() < deadline, "sweep did not finish"
            time.sleep(0.2)
        assert status["status"] == "done", status
        report = client.get(f"/api/sweeps/{job}/report").content
    output = (tmp_path / "server.log").read_text(encoding="utf-8")
    assert report == direct_report(tmp_path, GRID, "ma_crossover", "SPY"), output


def _running() -> dict[int, int]:
    """Parent pid of every process that has not exited (zombies have)."""
    rows = subprocess.run(
        ["ps", "-A", "-o", "pid=,ppid=,stat="], capture_output=True, text=True, check=True
    ).stdout.splitlines()
    return {int(pid): int(ppid) for pid, ppid, stat in map(str.split, rows) if stat[0] != "Z"}


def _descendants(root: int) -> set[int]:
    parents = _running()
    found = {root}
    while more := {pid for pid, ppid in parents.items() if ppid in found} - found:
        found |= more
    return found - {root}


@pytest.mark.skipif(sys.platform == "win32", reason="lists processes with ps")
def test_killing_the_server_stops_its_workers(tmp_path: Path) -> None:
    with _serve(tmp_path, [str(UVICORN)]) as (server, client):
        job = client.post("/api/sweeps", json=LONG_SWEEP).json()["id"]
        deadline = time.monotonic() + 60
        while client.get(f"/api/sweeps/{job}").json()["done"] == 0:
            assert time.monotonic() < deadline, "sweep did not start"
            time.sleep(0.02)
        children = _descendants(server.pid)
        assert len(children) >= 2  # at least the two workers
        server.kill()
        server.wait(timeout=30)
        deadline = time.monotonic() + 10
        while left := children & _running().keys():
            assert time.monotonic() < deadline, f"still running after 10 s: {sorted(left)}"
            time.sleep(0.1)
