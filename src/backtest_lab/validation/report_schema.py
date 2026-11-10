"""Credibility report models; their JSON schema is docs/report.schema.json (docs/REPORT.md).

Print the schema with `python -m backtest_lab.validation.report_schema`.
"""

import json
from datetime import date
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION: Final = "1.1"

type Verdict = Literal["green", "yellow", "red"]
# A check with too few independent trials to judge has no colour (D041).
type CheckVerdict = Verdict | Literal["not_assessable"]
type Param = bool | int | float | str


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Metrics(_Model):
    """METHODS.md Section 1 metrics of net daily returns; null when undefined."""

    cagr: float | None
    annual_volatility: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float | None
    calmar: float | None


class StrategyInfo(_Model):
    name: str
    fixed: dict[str, Param]
    grid: dict[str, list[Param]]
    n_trials: int


class Sample(_Model):
    start: date  # first date of the aligned trial returns
    end: date
    n_days: int
    years: float  # n_days / 252


class CostInfo(_Model):
    fee_bps: float
    slippage_bps: float


class Selected(_Model):
    """The trial with the highest Sharpe ratio over the whole sample."""

    trial: int
    params: dict[str, Param]
    metrics: Metrics


class Difference(_Model):
    """Selected trial minus benchmark."""

    sharpe: float | None
    cagr: float | None
    max_drawdown: float | None
    annual_volatility: float | None


class Benchmark(_Model):
    """Buy and hold over the same dates; a reference that takes no part in any verdict."""

    name: str
    metrics: Metrics
    difference: Difference


class Overall(_Model):
    verdict: Verdict  # the worst among the checks; one that is not assessable counts as yellow
    summary: str
    benchmark_summary: str


class Check(_Model):
    title: str
    verdict: CheckVerdict
    summary: str


class HoldoutMetrics(_Model):
    split_date: date  # first out-of-sample date
    is_sharpe: float | None
    oos_sharpe: float | None
    retention: float | None


class HoldoutDetails(_Model):
    fraction: float
    trial: int
    params: dict[str, Param]


class HoldoutCheck(Check):
    metrics: HoldoutMetrics
    details: HoldoutDetails


class WalkForwardMetrics(_Model):
    n_windows: int
    is_return: float  # mean over windows of the selected trial's annualized IS return
    oos_return: float  # annualized arithmetic return of the stitched OOS series
    efficiency: float | None
    oos_sharpe: float | None


class WalkForwardWindow(_Model):
    is_start: date
    oos_start: date
    oos_end: date
    trial: int
    is_sharpe: float | None
    oos_sharpe: float | None


class WalkForwardDetails(_Model):
    is_days: int
    oos_days: int
    anchored: bool
    windows: list[WalkForwardWindow]


class WalkForwardCheck(Check):
    metrics: WalkForwardMetrics
    details: WalkForwardDetails


class PurgedCVMetrics(_Model):
    folds: int
    embargo_days: int
    cv_sharpe: float  # mean test-fold Sharpe of the trials selected on training folds
    train_sharpe: float
    retention: float | None


class PurgedCVFold(_Model):
    test_start: date
    test_end: date
    n_train: int
    trial: int
    train_sharpe: float | None
    test_sharpe: float | None


class PurgedCVDetails(_Model):
    folds: list[PurgedCVFold]


class PurgedCVCheck(Check):
    metrics: PurgedCVMetrics
    details: PurgedCVDetails


class PBOMetrics(_Model):
    pbo: float
    n_combinations: int
    n_blocks: int
    degradation_slope: float | None
    prob_oos_loss: float


class Histogram(_Model):
    edges: list[float]  # len(counts) + 1
    counts: list[int]


class PBODetails(_Model):
    logits: Histogram


class PBOCheck(Check):
    metrics: PBOMetrics
    details: PBODetails


class DeflatedSharpeMetrics(_Model):
    dsr: float | None
    sharpe: float | None  # annualized, selected trial
    expected_max_sharpe: float  # annualized SR_0
    n_trials: int
    n_effective: float  # the estimate used: the larger of the two below (1.0: the first)
    n_effective_correlation: float | None = None  # from the average correlation; absent in 1.0
    n_effective_eigenvalue: float | None = None  # Nyholt (2004); absent in 1.0
    average_correlation: float
    sharpe_variance: float  # across trials, non-annualized
    skewness: float | None
    kurtosis: float | None  # raw


class DeflatedSharpeCheck(Check):
    metrics: DeflatedSharpeMetrics


class TrackRecordMetrics(_Model):
    psr: float | None  # PSR(0)
    sharpe: float | None  # annualized
    min_track_record_years: float | None
    years: float
    alpha: float


class TrackRecordCheck(Check):
    metrics: TrackRecordMetrics


class MinBacktestMetrics(_Model):
    min_backtest_years: float | None
    upper_bound_years: float | None
    years: float
    target_sharpe: float | None  # annualized Sharpe of the selected trial
    n_effective: float


class MinBacktestCheck(Check):
    metrics: MinBacktestMetrics


class SensitivityMetrics(_Model):
    best_sharpe: float  # annualized
    neighbour_mean: float | None  # null without neighbours
    neighbour_std: float | None
    retention: float | None
    n_neighbours: int
    radius: int


class Axis(_Model):
    name: str
    values: list[Param]


class Cell(_Model):
    x: int
    y: int  # 0 for a one-axis heatmap


class Heatmap(_Model):
    """Annualized Sharpe over one or two axes, other parameters fixed at the best trial."""

    x: Axis
    y: Axis | None
    sharpe: list[list[float]]  # [y][x]
    trials: list[list[int]]  # [y][x]
    best: Cell
    neighbours: list[Cell]  # neighbourhood cells that lie in this slice


class SensitivityDetails(_Model):
    heatmap: Heatmap | None  # null when no ordered axis has more than one value


class SensitivityCheck(Check):
    metrics: SensitivityMetrics
    details: SensitivityDetails


class Checks(_Model):
    holdout: HoldoutCheck
    walk_forward: WalkForwardCheck
    purged_cv: PurgedCVCheck
    pbo: PBOCheck
    deflated_sharpe: DeflatedSharpeCheck
    track_record: TrackRecordCheck
    min_backtest_length: MinBacktestCheck
    sensitivity: SensitivityCheck


class Curve(_Model):
    equity: list[float]  # wealth from 1 before the first date, at each week's last date
    drawdown: list[float]  # deepest daily drawdown within each week


class Series(_Model):
    frequency: Literal["weekly"]
    dates: list[date]  # last trading date of each week
    selected: Curve
    benchmark: Curve


class Report(_Model):
    schema_version: Literal["1.0", "1.1"]  # 1.0: the frozen demo reports (D032)
    strategy: StrategyInfo
    sample: Sample
    costs: CostInfo
    selected: Selected
    benchmark: Benchmark
    overall: Overall
    checks: Checks
    series: Series


def json_schema() -> str:
    return json.dumps(Report.model_json_schema(), indent=2) + "\n"


if __name__ == "__main__":
    print(json_schema(), end="")
