"""FastAPI service for local use (D016). It has no authentication: bind it to 127.0.0.1.

Run: uvicorn backtest_lab.api.main:app --host 127.0.0.1 --reload
The data directory is `data`, or BACKTEST_LAB_DATA_DIR if set; sweeps use up to four
worker processes, or BACKTEST_LAB_PROCESSES if set.
"""

import os
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from backtest_lab.api import params as P
from backtest_lab.api.jobs import REPORT_FILE, JobStore, Runner, SweepJob
from backtest_lab.api.market import Market, load_market
from backtest_lab.api.schemas import (
    BacktestRequest,
    BacktestResponse,
    Curve,
    ParamInfo,
    StrategyInfo,
    SweepCreated,
    SweepRequest,
    SweepStatus,
)
from backtest_lab.engine.backtest import Costs, run
from backtest_lab.engine.metrics import ANNUALIZATION
from backtest_lab.strategies import STRATEGIES
from backtest_lab.validation import report_schema as rs
from backtest_lab.validation.report import Settings, metrics_model, weekly_curve
from backtest_lab.validation.search import Grid, Params, ParamValue

DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # Vite dev server
# Another site's page can point its own name at 127.0.0.1 and call the API from a
# browser; the Host header it sends is that name.
LOCAL_HOSTS = ["127.0.0.1", "localhost"]
NO_MARKET = "no market data; run python -m backtest_lab.data.update"
MAX_TRIALS = 500  # CSCV peaks near 0.7 MB per trial (D017)
MAX_QUEUED = 10
DEFAULT_PROCESSES = 4
_JOB_ID = re.compile(r"[0-9a-f]{32}")


def _market(request: Request) -> Market:
    market: Market | None = request.app.state.market
    if market is None:
        raise HTTPException(503, NO_MARKET)
    return market


def _check_symbols(market: Market, strategy: str, params: list[Params]) -> None:
    """Every ticker parameter names a ticker and every series parameter a macro series."""
    kinds: list[tuple[P.SymbolKind, list[str]]] = [
        ("ticker", market.tickers),
        ("series", market.series),
    ]
    for kind, known in kinds:
        missing = sorted(P.symbols(strategy, params, kind) - set(known))
        if missing:
            raise HTTPException(422, f"no {kind} data for {missing}")


def _benchmark(body: SweepRequest, market: Market) -> str:
    """The requested benchmark, else the strategy's first ticker parameter when it is
    not an axis."""
    if body.benchmark is not None:
        name = body.benchmark
    else:
        first = next((s for s in P.specs(body.strategy) if s.symbol == "ticker"), None)
        if first is None or first.name in body.axes:
            raise HTTPException(422, "set a benchmark ticker")
        name = str(body.fixed.get(first.name, first.default))
    if name not in market.tickers:
        raise HTTPException(422, f"benchmark {name!r} is not a ticker in the cache")
    return name


def _prepare(body: SweepRequest, market: Market, job_id: str | None = None) -> SweepJob:
    """Check a sweep request completely before it is queued."""
    try:
        specs = {s.name: s for s in P.specs(body.strategy)}
        unknown = (set(body.axes) | set(body.fixed)) - set(specs)
        if unknown:
            raise P.ParamError(f"{body.strategy} has no parameter {sorted(unknown)}")
        axes: dict[str, list[ParamValue]] = {
            name: [P.check_value(specs[name], v) for v in values]
            for name, values in body.axes.items()
        }
        # Every parameter that is not an axis is fixed, defaults included, so the stored
        # trials and the report state the full configuration.
        given = P.check_params(body.strategy, body.fixed)
        fixed = {n: given.get(n, s.default) for n, s in specs.items() if n not in axes}
        grid = Grid.of(axes, fixed, body.categorical)
        if len(grid) > MAX_TRIALS:
            raise P.ParamError(f"the grid has {len(grid)} trials; the limit is {MAX_TRIALS}")
        params = grid.params()
        warmup = max(P.build(body.strategy, p).warmup for p in params)
        _check_symbols(market, body.strategy, params)
        benchmark = _benchmark(body, market)
        traded = sorted(P.symbols(body.strategy, params, "ticker"))
        data = market.between(body.start, body.end, traded, also=(benchmark,))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    # Upper bound on the aligned days: dates where every traded ticker has a price,
    # less the first date and the longest warm-up (D017). The benchmark does not limit
    # the sample: buy and hold is flat before it lists.
    estimate = int(data.prices.close[traded].notna().all(axis=1).sum()) - 1 - warmup
    needed = Settings().min_days
    if estimate < needed:
        raise HTTPException(
            422,
            f"about {max(estimate, 0)} aligned trading days in this range; a report needs at "
            f"least {needed}",
        )
    return SweepJob(
        id=job_id or uuid.uuid4().hex,
        strategy=body.strategy,
        grid=grid,
        data=data,
        costs=Costs(body.costs.fee_bps, body.costs.slippage_bps),
        benchmark=benchmark,
    )


def _job(request: Request, job_id: str) -> dict[str, object]:
    store: JobStore = request.app.state.store
    row = store.get(job_id) if _JOB_ID.fullmatch(job_id) else None
    if row is None:
        raise HTTPException(404, "no such sweep")
    return row


def _requeue(store: JobStore, runner: Runner, market: Market | None) -> None:
    """Queue again the sweeps a previous server process left waiting."""
    for job_id, request in store.queued():
        try:
            if market is None:
                raise ValueError(NO_MARKET)
            job = _prepare(SweepRequest.model_validate_json(request), market, job_id)
        except HTTPException as exc:  # the cache no longer supports the request
            store.failed(job_id, str(exc.detail))
        except ValueError as exc:
            store.failed(job_id, str(exc))
        else:
            runner.submit(job)


def create_app(data_dir: Path | None = None, processes: int | None = None) -> FastAPI:
    root = data_dir or Path(os.environ.get("BACKTEST_LAB_DATA_DIR", "data"))
    if processes is None:
        env = os.environ.get("BACKTEST_LAB_PROCESSES")
        # Each worker holds a copy of the market data and the engine's buffers (D017).
        processes = int(env) if env else min(os.process_cpu_count() or 1, DEFAULT_PROCESSES)
    if processes < 1:
        raise ValueError("BACKTEST_LAB_PROCESSES must be at least 1")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.market = load_market(root / "raw")
        store = JobStore(root / "jobs")
        store.fail_running("the server restarted before this sweep finished")
        runner = Runner(store, processes)
        runner.start()
        _requeue(store, runner, app.state.market)
        app.state.store, app.state.runner = store, runner
        yield
        if runner.stop():
            store.close()

    app = FastAPI(title="backtest-lab", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["GET", "POST"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS)

    @app.get("/api/strategies")
    def strategies() -> list[StrategyInfo]:
        return [
            StrategyInfo(
                name=name,
                description=(cls.__doc__ or "").strip().split("\n\n")[0].replace("\n", " "),
                params=[
                    ParamInfo(name=s.name, type=s.type, default=s.default, symbol=s.symbol)
                    for s in P.specs(name)
                ],
            )
            for name, cls in STRATEGIES.items()
        ]

    @app.post("/api/backtests")
    def backtest(body: BacktestRequest, request: Request) -> BacktestResponse:
        market = _market(request)
        try:
            given = P.check_params(body.strategy, body.params)
            params = {s.name: given.get(s.name, s.default) for s in P.specs(body.strategy)}
            strategy = P.build(body.strategy, params)
            _check_symbols(market, body.strategy, [params])
            tickers = sorted(P.symbols(body.strategy, [params], "ticker"))
            data = market.between(body.start, body.end, tickers)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        costs = Costs(body.costs.fee_bps, body.costs.slippage_bps)
        try:
            result = run(strategy.weights(data), data.prices, costs)
        except ValueError as exc:  # e.g. a position in a ticker before it lists
            raise HTTPException(422, str(exc)) from exc
        if result.start is None:
            raise HTTPException(422, "the strategy has no valid signal in this date range")
        returns = result.returns.loc[result.start :]
        values = returns.to_numpy(dtype=np.float64)
        weeks, curve = weekly_curve(pd.DatetimeIndex(returns.index), values)
        return BacktestResponse(
            strategy=body.strategy,
            params=params,
            costs=body.costs,
            start=result.start.date(),
            end=returns.index[-1].date(),
            n_days=len(returns),
            metrics=metrics_model(values),
            annual_turnover=float(result.turnover.loc[result.start :].mean() * ANNUALIZATION),
            series=Curve(
                dates=[date.fromisoformat(d) for d in weeks],
                equity=curve.equity,
                drawdown=curve.drawdown,
            ),
        )

    @app.post("/api/sweeps", status_code=202)
    def create_sweep(body: SweepRequest, request: Request) -> SweepCreated:
        job = _prepare(body, _market(request))
        store: JobStore = request.app.state.store
        if not store.enqueue(
            job.id, job.strategy, body.model_dump_json(), len(job.grid), MAX_QUEUED
        ):
            raise HTTPException(429, f"{MAX_QUEUED} sweeps are already waiting; try again later")
        request.app.state.runner.submit(job)
        return SweepCreated(id=job.id)

    @app.get("/api/sweeps/{job_id}")
    def sweep_status(job_id: str, request: Request) -> SweepStatus:
        row = _job(request, job_id)
        return SweepStatus.model_validate({k: row[k] for k in SweepStatus.model_fields})

    @app.get(
        "/api/sweeps/{job_id}/report",
        response_class=Response,
        responses={200: {"model": rs.Report, "content": {"application/json": {}}}},
    )
    def sweep_report(job_id: str, request: Request) -> Response:
        row = _job(request, job_id)
        if row["status"] != "done":
            raise HTTPException(409, f"the sweep is {row['status']}")
        store: JobStore = request.app.state.store
        path = store.directory(job_id) / REPORT_FILE
        # The stored bytes, so the response is identical to the file (REPORT.md).
        return Response(path.read_bytes(), media_type="application/json")

    return app


app = create_app()
