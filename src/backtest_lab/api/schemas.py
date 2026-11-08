"""Request and response models; requests reject unknown fields."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
)

from backtest_lab.api.params import SymbolKind, TypeName
from backtest_lab.validation import report_schema as rs

type Value = StrictBool | StrictInt | StrictFloat | Annotated[str, StringConstraints(max_length=32)]


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)


class _Response(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CostsIn(_Request):
    fee_bps: float = Field(default=1.0, ge=0, le=1000)
    slippage_bps: float = Field(default=5.0, ge=0, le=1000)


class BacktestRequest(_Request):
    strategy: str
    params: dict[str, Value] = {}
    start: date | None = None
    end: date | None = None
    costs: CostsIn = CostsIn()


class ParamInfo(_Response):
    name: str
    type: TypeName
    default: Value
    symbol: SymbolKind | None  # for a string parameter: names a ticker or a macro series


class StrategyInfo(_Response):
    name: str
    description: str
    params: list[ParamInfo]


class Curve(_Response):
    dates: list[date]  # last trading date of each week
    equity: list[float]
    drawdown: list[float]


class BacktestResponse(_Response):
    strategy: str
    params: dict[str, Value]
    costs: CostsIn
    start: date  # first date whose return follows a valid signal
    end: date
    n_days: int
    metrics: rs.Metrics
    annual_turnover: float
    series: Curve


class SweepRequest(_Request):
    strategy: str
    axes: dict[str, list[Value]] = Field(min_length=1)
    fixed: dict[str, Value] = {}
    categorical: list[str] = []
    start: date | None = None
    end: date | None = None
    costs: CostsIn = CostsIn()
    benchmark: str | None = None  # default: the strategy's ticker (D017)


class SweepCreated(_Response):
    id: str


class SweepStatus(_Response):
    id: str
    status: Literal["queued", "running", "done", "failed"]
    strategy: str
    n_trials: int
    done: int  # trials backtested so far
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    selected_trial: int | None  # set when done
    selected_params: dict[str, Value] | None
    verdict: rs.Verdict | None
