"""Background parameter sweeps: state in SQLite, results on disk, one sweep at a time
(D017, D018)."""

import json
import logging
import os
import queue
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from backtest_lab.engine.backtest import Costs
from backtest_lab.strategies import MarketData
from backtest_lab.validation.report import Settings, build_report
from backtest_lab.validation.search import Grid, run_grid

log = logging.getLogger(__name__)

type Status = Literal["queued", "running", "done", "failed"]
REPORT_FILE = "report.json"
TRIALS_DIR = "trials"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    strategy TEXT NOT NULL,
    request TEXT NOT NULL,
    n_trials INTEGER NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    selected_trial INTEGER,
    selected_params TEXT,
    verdict TEXT
)
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class JobStore:
    """Job rows in `<root>/jobs.sqlite3` and each job's files in `<root>/<id>/`."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        # One connection shared by the request threads and the runner, serialized by a lock.
        self._db = sqlite3.connect(
            root / "jobs.sqlite3", check_same_thread=False, isolation_level=None
        )
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._db.execute(_SCHEMA)

    def _execute(self, sql: str, args: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._db.execute(sql, args)

    def directory(self, job_id: str) -> Path:
        return self.root / job_id

    def fail_unfinished(self, reason: str) -> int:
        """Mark jobs left queued or running by a previous server process as failed."""
        cur = self._execute(
            "UPDATE jobs SET status = 'failed', error = ?, finished_at = ? "
            "WHERE status IN ('queued', 'running')",
            (reason, _now()),
        )
        return cur.rowcount

    def enqueue(
        self, job_id: str, strategy: str, request: str, n_trials: int, max_queued: int
    ) -> bool:
        """Add a queued job unless `max_queued` jobs are already waiting."""
        with self._lock:
            (waiting,) = self._db.execute(
                "SELECT COUNT(*) FROM jobs WHERE status = 'queued'"
            ).fetchone()
            if waiting >= max_queued:
                return False
            self._db.execute(
                "INSERT INTO jobs (id, status, strategy, request, n_trials, created_at) "
                "VALUES (?, 'queued', ?, ?, ?, ?)",
                (job_id, strategy, request, n_trials, _now()),
            )
            return True

    def get(self, job_id: str) -> dict[str, Any] | None:
        row = self._execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        out = dict(row)
        out["selected_params"] = (
            json.loads(out["selected_params"]) if out["selected_params"] else None
        )
        return out

    def started(self, job_id: str) -> None:
        self._execute(
            "UPDATE jobs SET status = 'running', started_at = ? WHERE id = ?", (_now(), job_id)
        )

    def progress(self, job_id: str, done: int) -> None:
        self._execute("UPDATE jobs SET done = ? WHERE id = ?", (done, job_id))

    def finished(self, job_id: str, trial: int, params: dict[str, Any], verdict: str) -> None:
        self._execute(
            "UPDATE jobs SET status = 'done', finished_at = ?, selected_trial = ?, "
            "selected_params = ?, verdict = ? WHERE id = ?",
            (_now(), trial, json.dumps(params), verdict, job_id),
        )

    def failed(self, job_id: str, error: str) -> None:
        self._execute(
            "UPDATE jobs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
            (error, _now(), job_id),
        )

    def close(self) -> None:
        with self._lock:
            self._db.close()


@dataclass(frozen=True)
class SweepJob:
    id: str
    strategy: str
    grid: Grid
    data: MarketData
    costs: Costs
    benchmark: str


class Runner:
    """Runs queued sweeps one at a time on a background thread; each sweep uses a
    process pool (run_grid)."""

    def __init__(self, store: JobStore, processes: int | None = None) -> None:
        self.store = store
        self.processes = processes
        self._queue: queue.Queue[SweepJob | None] = queue.Queue()
        self._thread = threading.Thread(target=self._loop, name="sweep-runner", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def submit(self, job: SweepJob) -> None:
        self._queue.put(job)

    def stop(self, timeout: float = 1.0) -> bool:
        """Ask the thread to stop after the current sweep; True if it has stopped.

        A sweep still running is abandoned with the process and marked failed by the
        next server start.
        """
        self._queue.put(None)
        self._thread.join(timeout)
        return not self._thread.is_alive()

    def _loop(self) -> None:
        while (job := self._queue.get()) is not None:
            self._run(job)

    def _run(self, job: SweepJob) -> None:
        store = self.store
        store.started(job.id)
        try:
            trials = run_grid(
                job.strategy,
                job.grid,
                job.data,
                job.costs,
                processes=self.processes,
                progress=lambda done, _total: store.progress(job.id, done),
            )
            report = build_report(trials, job.data, job.benchmark, Settings())
            directory = store.directory(job.id)
            trials.save(directory / TRIALS_DIR)
            tmp = directory / (REPORT_FILE + ".tmp")
            tmp.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
            os.replace(tmp, directory / REPORT_FILE)
            store.finished(
                job.id, report.selected.trial, dict(report.selected.params), report.overall.verdict
            )
        except ValueError as exc:  # an expected limit, such as too few aligned days
            log.warning("sweep %s failed: %s", job.id, exc)
            store.failed(job.id, str(exc))
        except Exception as exc:
            log.exception("sweep %s failed", job.id)
            store.failed(job.id, f"internal error ({type(exc).__name__}); see the server log")
