"""FastAPI service for local use (D016). It has no authentication: bind it to 127.0.0.1.

Run: uvicorn backtest_lab.api.main:app --host 127.0.0.1 --reload
The data directory is `data`, or BACKTEST_LAB_DATA_DIR if set.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backtest_lab.api import params as P
from backtest_lab.api.market import Market, load_market
from backtest_lab.api.schemas import (
    BacktestRequest,
    BacktestResponse,
    Curve,
    ParamInfo,
    StrategyInfo,
)
from backtest_lab.engine.backtest import Costs, run
from backtest_lab.strategies import STRATEGIES
from backtest_lab.validation.report import metrics_model, weekly_curve

DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # Vite dev server


def _market(request: Request) -> Market:
    market: Market | None = request.app.state.market
    if market is None:
        raise HTTPException(503, "no market data; run python -m backtest_lab.data.update")
    return market


def _check_symbols(market: Market, names: set[str]) -> None:
    missing = sorted(names - set(market.tickers) - set(market.series))
    if missing:
        raise HTTPException(422, f"no data for {missing}")


def create_app(data_dir: Path | None = None) -> FastAPI:
    root = data_dir or Path(os.environ.get("BACKTEST_LAB_DATA_DIR", "data"))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.market = load_market(root / "raw")
        yield

    app = FastAPI(title="backtest-lab", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["GET", "POST"])

    @app.get("/api/strategies")
    def strategies() -> list[StrategyInfo]:
        return [
            StrategyInfo(
                name=name,
                description=(cls.__doc__ or "").strip().split("\n\n")[0].replace("\n", " "),
                params=[
                    ParamInfo(name=s.name, type=s.type, default=s.default) for s in P.specs(name)
                ],
            )
            for name, cls in STRATEGIES.items()
        ]

    @app.post("/api/backtests")
    def backtest(body: BacktestRequest, request: Request) -> BacktestResponse:
        market = _market(request)
        try:
            params = P.check_params(body.strategy, body.params)
            strategy = P.build(body.strategy, params)
            _check_symbols(market, P.symbols(body.strategy, [params]))
            data = market.between(body.start, body.end)
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
        weeks, curve = weekly_curve(
            pd.DatetimeIndex(returns.index), returns.to_numpy(dtype=np.float64)
        )
        return BacktestResponse(
            strategy=body.strategy,
            params=params,
            costs=body.costs,
            start=result.start.date(),
            end=returns.index[-1].date(),
            n_days=len(returns),
            metrics=metrics_model(returns.to_numpy(dtype=np.float64)),
            annual_turnover=float(result.turnover.loc[result.start :].mean() * 252),
            series=Curve(
                dates=[date.fromisoformat(d) for d in weeks],
                equity=curve.equity,
                drawdown=curve.drawdown,
            ),
        )

    return app


app = create_app()
