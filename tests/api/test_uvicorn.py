"""A sweep through a real uvicorn server whose grid search uses worker processes, with
the platform's default start method (forkserver on Linux, spawn on Windows)."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx2
import pytest

from tests.api.conftest import write_cache
from tests.api.test_sweeps import GRID, SWEEP, direct_report

SCRIPTS = Path(sys.executable).parent
UVICORN = SCRIPTS / ("uvicorn.exe" if sys.platform == "win32" else "uvicorn")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


@pytest.mark.parametrize(
    "launcher", [[str(UVICORN)], [sys.executable, "-m", "uvicorn"]], ids=["script", "module"]
)
def test_sweep_under_uvicorn_with_worker_processes(tmp_path: Path, launcher: list[str]) -> None:
    write_cache(tmp_path)
    port = _free_port()
    env = os.environ | {"BACKTEST_LAB_DATA_DIR": str(tmp_path), "BACKTEST_LAB_PROCESSES": "2"}
    cmd = [*launcher, "backtest_lab.api.main:app", "--host", "127.0.0.1", "--port", str(port)]
    server = subprocess.Popen(
        cmd, env=env, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    base = f"http://127.0.0.1:{port}"
    try:
        with httpx2.Client(base_url=base, timeout=30) as client:
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
    finally:
        server.terminate()
        output, _ = server.communicate(timeout=30)
    assert report == direct_report(tmp_path, GRID, "ma_crossover", "SPY"), output
