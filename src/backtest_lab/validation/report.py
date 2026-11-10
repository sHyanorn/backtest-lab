"""Credibility report: every check on one set of trials, with a verdict and a
plain-language summary (docs/REPORT.md; thresholds in D022)."""

import math
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import pandas as pd

from backtest_lab.engine.backtest import Costs, run
from backtest_lab.engine.metrics import ANNUALIZATION, drawdown_curve, sharpe, summarize
from backtest_lab.strategies import MarketData
from backtest_lab.validation import report_schema as rs
from backtest_lab.validation.pbo import cscv, n_combinations
from backtest_lab.validation.purged_kfold import purged_cv
from backtest_lab.validation.search import Trials
from backtest_lab.validation.selection import annualize, best_trial, ranking_daily_sharpe
from backtest_lab.validation.sensitivity import heatmap, sensitivity
from backtest_lab.validation.sharpe_stats import (
    SharpeMoments,
    average_correlation,
    deflated_sharpe_ratio,
    dsr_inputs,
    effective_trials,
    expected_max_sharpe,
    mean_squared_correlation,
    min_backtest_length,
    min_backtest_length_bound,
    min_track_record_length,
    probabilistic_sharpe_ratio,
    varying,
)
from backtest_lab.validation.walk_forward import holdout, walk_forward

# Verdict thresholds, fixed before any real-data run (D022)
RETENTION_GREEN = 0.5
PBO_GREEN = 0.10
PBO_RED = 0.30
PROBABILITY_GREEN = 0.95
PROBABILITY_YELLOW = 0.5
SENSITIVITY_GREEN = 0.75
SENSITIVITY_YELLOW = 0.5
# Fewer independent trials than this and a green or yellow PBO or DSR is not a verdict (D041)
MIN_EFFECTIVE_TRIALS = 10

_SEVERITY: dict[rs.CheckVerdict, int] = {"green": 0, "yellow": 1, "not_assessable": 1, "red": 2}
_OVERALL: tuple[rs.Verdict, ...] = ("green", "yellow", "red")
_LOGIT_BINS = 20


@dataclass(frozen=True)
class Settings:
    holdout_fraction: float = 0.7
    is_days: int = 1260
    oos_days: int = 252
    anchored: bool = False
    folds: int = 10
    embargo: int | None = None  # default ceil(0.01 T)
    blocks: int = 16
    radius: int = 1
    heatmap_axes: tuple[str, ...] | None = None  # default: the first two ordered axes
    alpha: float = 0.05

    @property
    def min_days(self) -> int:
        """Aligned days needed for one walk-forward window, two rows per CSCV block and
        one row per fold."""
        return max(self.is_days + self.oos_days, 2 * self.blocks, self.folds)


def retention_verdict(oos: float, ratio: float | None) -> rs.Verdict:
    if not oos > 0 or ratio is None:
        return "red"
    return "green" if ratio >= RETENTION_GREEN else "yellow"


def pbo_verdict(pbo: float) -> rs.Verdict:
    if pbo <= PBO_GREEN:
        return "green"
    return "yellow" if pbo <= PBO_RED else "red"


def probability_verdict(p: float | None) -> rs.Verdict:
    if p is None or not p >= PROBABILITY_YELLOW:
        return "red"
    return "green" if p >= PROBABILITY_GREEN else "yellow"


def min_backtest_verdict(min_years: float | None, years: float) -> rs.Verdict:
    return "green" if min_years is not None and years >= min_years else "red"


def sensitivity_verdict(best: float, retention: float | None, assessable: bool) -> rs.Verdict:
    if not assessable:
        return "yellow"  # no neighbours to compare
    if not best > 0 or retention is None or retention < SENSITIVITY_YELLOW:
        return "red"
    return "green" if retention >= SENSITIVITY_GREEN else "yellow"


def logit_histogram(
    logits: npt.NDArray[np.float64], n_trials: int, bins: int = _LOGIT_BINS
) -> tuple[npt.NDArray[np.intp], npt.NDArray[np.float64]]:
    """Counts and edges of equal bins on [-ln N, ln N], the range of the logits.

    The extreme logits are +-ln N in exact arithmetic but can round one ulp outside
    it, where np.histogram would drop them, so they are clipped first.
    """
    limit = math.log(n_trials)
    edges = np.linspace(-limit, limit, bins + 1)
    counts, _ = np.histogram(np.clip(logits, -limit, limit), edges)
    return counts, edges


def enough_trials(*estimates: float) -> bool:
    """Whether the smallest estimate of the independent trials lets PBO or DSR pass."""
    return min(estimates) >= MIN_EFFECTIVE_TRIALS


def worst(verdicts: list[rs.CheckVerdict]) -> rs.Verdict:
    """The overall verdict; a check that cannot be assessed counts as yellow."""
    return _OVERALL[max(_SEVERITY[v] for v in verdicts)]


def _num(x: float | None) -> float | None:
    return float(x) if x is not None and math.isfinite(x) else None


def metrics_model(returns: npt.NDArray[np.float64]) -> rs.Metrics:
    m = {k: _num(v) for k, v in summarize(returns).items()}
    return rs.Metrics(
        cagr=m["cagr"],
        annual_volatility=m["annual_volatility"],
        sharpe=m["sharpe"],
        sortino=m["sortino"],
        max_drawdown=m["max_drawdown"],
        calmar=m["calmar"],
    )


def _diff(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a - b


def _fmt(x: float | None, spec: str = ".2f") -> str:
    return "undefined" if x is None else format(x, spec)


def buy_and_hold(ticker: str, data: MarketData, costs: Costs) -> pd.Series:
    """Net returns of a constant weight of 1 in `ticker`, flat before it lists."""
    close = data.prices.close[ticker]
    weights = pd.Series(1.0, index=close.index).where(close.notna()).to_frame(ticker)
    return run(weights, data.prices, costs).returns


def weekly_curve(
    dates: pd.DatetimeIndex, returns: npt.NDArray[np.float64]
) -> tuple[list[str], rs.Curve]:
    equity, drawdown = drawdown_curve(returns)
    frame = pd.DataFrame({"date": dates, "equity": equity, "drawdown": drawdown})
    weeks = frame.groupby(dates.to_period("W"))
    last = weeks.last()
    curve = rs.Curve(
        equity=[round(float(v), 6) for v in last["equity"]],
        drawdown=[round(float(v), 6) for v in weeks["drawdown"].min()],
    )
    return [d.strftime("%Y-%m-%d") for d in last["date"]], curve


def build_report(
    trials: Trials,
    data: MarketData,
    benchmark: str,
    settings: Settings = Settings(),  # noqa: B008
) -> rs.Report:
    """Run every check on `trials` and compare the selected trial with buy and hold of
    `benchmark` over the same dates (D021)."""
    frame = trials.returns
    x = frame.to_numpy(dtype=np.float64)
    n_days, n_trials = x.shape
    if n_trials < 2:
        raise ValueError("a report needs at least two trials")
    if n_days < settings.min_days:
        raise ValueError(
            f"the trials share {n_days} days; these settings need at least {settings.min_days}"
        )
    dates = pd.DatetimeIndex(frame.index)
    years = n_days / ANNUALIZATION
    params = trials.params
    best = best_trial(x)
    chosen = x[:, best]
    bench = buy_and_hold(benchmark, data, trials.costs).loc[dates].to_numpy(dtype=np.float64)

    moments, daily_sharpe_variance = dsr_inputs(x)
    rho, rho_squared = average_correlation(x), mean_squared_correlation(x)
    # A trial that never trades adds no independent trial to the floor's count.
    live = varying(x).shape[1]
    counts = _TrialCounts(
        n_trials,
        by_correlation=effective_trials(rho, n_trials),
        by_eigenvalue=effective_trials(rho_squared, n_trials),
        fewest=min(effective_trials(rho, live), effective_trials(rho_squared, live)),
    )

    checks = rs.Checks(
        holdout=_holdout_check(trials, settings),
        walk_forward=_walk_forward_check(trials, data, settings),
        purged_cv=_purged_cv_check(trials, settings),
        pbo=_pbo_check(x, settings, counts),
        deflated_sharpe=_dsr_check(moments, daily_sharpe_variance, counts, rho),
        track_record=_track_record_check(moments, years, settings.alpha),
        min_backtest_length=_min_backtest_check(
            counts.used, annualize(moments.daily_sharpe), years
        ),
        sensitivity=_sensitivity_check(trials, annualize(ranking_daily_sharpe(x)), best, settings),
    )
    selected = metrics_model(chosen)
    bench_metrics = metrics_model(bench)
    week_dates, selected_curve = weekly_curve(dates, chosen)
    _, bench_curve = weekly_curve(dates, bench)
    name = f"{benchmark} buy and hold"
    return rs.Report(
        schema_version=rs.SCHEMA_VERSION,
        strategy=rs.StrategyInfo(
            name=trials.strategy,
            fixed=dict(trials.grid.fixed),
            grid={k: list(v) for k, v in trials.grid.axes},
            n_trials=n_trials,
        ),
        sample=rs.Sample(start=dates[0].date(), end=dates[-1].date(), n_days=n_days, years=years),
        costs=rs.CostInfo(fee_bps=trials.costs.fee_bps, slippage_bps=trials.costs.slippage_bps),
        selected=rs.Selected(trial=best, params=params[best], metrics=selected),
        benchmark=rs.Benchmark(
            name=name,
            metrics=bench_metrics,
            difference=rs.Difference(
                sharpe=_diff(selected.sharpe, bench_metrics.sharpe),
                cagr=_diff(selected.cagr, bench_metrics.cagr),
                max_drawdown=_diff(selected.max_drawdown, bench_metrics.max_drawdown),
                annual_volatility=_diff(
                    selected.annual_volatility, bench_metrics.annual_volatility
                ),
            ),
        ),
        overall=_overall(checks, selected, bench_metrics, name),
        checks=checks,
        series=rs.Series(
            frequency="weekly",
            dates=[pd.Timestamp(d).date() for d in week_dates],
            selected=selected_curve,
            benchmark=bench_curve,
        ),
    )


def _holdout_check(trials: Trials, s: Settings) -> rs.HoldoutCheck:
    h = holdout(trials.returns, s.holdout_fraction)
    oos_years = int((trials.returns.index >= h.split).sum()) / ANNUALIZATION
    retention = _num(h.retention)
    summary = (
        f"Picked on the first {s.holdout_fraction:.0%} of the history, the best setting's "
        f"Sharpe ratio went from {_fmt(_num(h.is_sharpe))} to {_fmt(_num(h.oos_sharpe))} "
        f"over the remaining {oos_years:.1f} years."
    )
    return rs.HoldoutCheck(
        title="Holdout split",
        verdict=retention_verdict(h.oos_sharpe, retention),
        summary=summary,
        metrics=rs.HoldoutMetrics(
            split_date=h.split.date(),
            is_sharpe=_num(h.is_sharpe),
            oos_sharpe=_num(h.oos_sharpe),
            retention=retention,
        ),
        details=rs.HoldoutDetails(
            fraction=s.holdout_fraction, trial=h.trial, params=trials.params[h.trial]
        ),
    )


def _walk_forward_check(trials: Trials, data: MarketData, s: Settings) -> rs.WalkForwardCheck:
    wf = walk_forward(trials, data, s.is_days, s.oos_days, anchored=s.anchored)
    efficiency = _num(wf.efficiency)
    oos_sharpe = _num(sharpe(wf.returns))
    window = "an expanding window" if s.anchored else f"the previous {s.is_days} days"
    if efficiency is None:
        kept = "the in-sample return was not positive, so efficiency is undefined"
    else:
        kept = f"it kept {efficiency:.0%} of the in-sample return rate"
    summary = (
        f"Re-picking the best setting every {s.oos_days} days on {window} and trading it on "
        f"the next period, {kept}; the out-of-sample Sharpe ratio was {_fmt(oos_sharpe)}."
    )
    return rs.WalkForwardCheck(
        title="Walk-forward analysis",
        verdict=retention_verdict(wf.oos_return, efficiency),
        summary=summary,
        metrics=rs.WalkForwardMetrics(
            n_windows=len(wf.windows),
            is_return=wf.is_return,
            oos_return=wf.oos_return,
            efficiency=efficiency,
            oos_sharpe=oos_sharpe,
        ),
        details=rs.WalkForwardDetails(
            is_days=s.is_days,
            oos_days=s.oos_days,
            anchored=s.anchored,
            windows=[
                rs.WalkForwardWindow(
                    is_start=w.is_start.date(),
                    oos_start=w.oos_start.date(),
                    oos_end=w.oos_end.date(),
                    trial=w.trial,
                    is_sharpe=_num(w.is_sharpe),
                    oos_sharpe=_num(w.oos_sharpe),
                )
                for w in wf.windows
            ],
        ),
    )


def _purged_cv_check(trials: Trials, s: Settings) -> rs.PurgedCVCheck:
    cv = purged_cv(trials.returns, s.folds, s.embargo)
    retention = _num(cv.retention)
    summary = (
        f"Picking the best setting on {s.folds - 1} of {s.folds} folds, with overlapping and "
        f"embargoed days removed, gave an average Sharpe ratio of {cv.score:.2f} on the "
        f"held-out fold, against {cv.train_score:.2f} on the folds it was picked on."
    )
    return rs.PurgedCVCheck(
        title="Purged cross-validation",
        verdict=retention_verdict(cv.score, retention),
        summary=summary,
        metrics=rs.PurgedCVMetrics(
            folds=s.folds,
            embargo_days=cv.embargo,
            cv_sharpe=cv.score,
            train_sharpe=cv.train_score,
            retention=retention,
        ),
        details=rs.PurgedCVDetails(
            folds=[
                rs.PurgedCVFold(
                    test_start=f.test_start.date(),
                    test_end=f.test_end.date(),
                    n_train=f.n_train,
                    trial=f.trial,
                    train_sharpe=_num(f.train_sharpe),
                    test_sharpe=_num(f.test_sharpe),
                )
                for f in cv.folds
            ]
        ),
    )


@dataclass(frozen=True)
class _TrialCounts:
    """The trials run and the two estimates of how many are independent (METHODS.md
    Section 5)."""

    n_trials: int
    by_correlation: float
    by_eigenvalue: float
    fewest: float  # the smaller estimate over the trials whose returns vary

    @property
    def used(self) -> float:
        """The larger estimate: the higher DSR threshold and the longer MinBTL."""
        return max(self.by_correlation, self.by_eigenvalue)

    def judge(self, verdict: rs.Verdict, summary: str) -> tuple[rs.CheckVerdict, str]:
        """A check's verdict and summary. With too few trials the check is lenient, so a
        pass is withheld; a fail still counts."""
        if verdict == "red" or enough_trials(self.fewest):
            return verdict, summary
        shown = math.floor(10 * self.fewest) / 10  # 9.97 must not read as the 10 required
        return "not_assessable", (
            f"Only about {shown:.1f} of the {self.n_trials} settings tried are independent; "
            f"this check needs at least {MIN_EFFECTIVE_TRIALS}."
        )


def _pbo_check(x: npt.NDArray[np.float64], s: Settings, trials: _TrialCounts) -> rs.PBOCheck:
    result = cscv(x, s.blocks)
    counts, edges = logit_histogram(result.logits, result.n_trials)
    combos = n_combinations(s.blocks)
    summary = (
        f"In {result.pbo:.0%} of {combos:,} ways to split the history into two halves, the "
        f"best of {result.n_trials} settings on one half ranked in the bottom half on the other."
    )
    verdict, summary = trials.judge(pbo_verdict(result.pbo), summary)
    return rs.PBOCheck(
        title="Probability of backtest overfitting",
        verdict=verdict,
        summary=summary,
        metrics=rs.PBOMetrics(
            pbo=result.pbo,
            n_combinations=combos,
            n_blocks=s.blocks,
            degradation_slope=_num(result.degradation_slope),
            prob_oos_loss=result.prob_oos_loss,
        ),
        details=rs.PBODetails(
            logits=rs.Histogram(edges=[float(e) for e in edges], counts=[int(c) for c in counts])
        ),
    )


def _dsr_check(
    m: SharpeMoments, daily_sharpe_variance: float, trials: _TrialCounts, rho: float
) -> rs.DeflatedSharpeCheck:
    n_eff = trials.used
    low, high = sorted((trials.by_correlation, trials.by_eigenvalue))
    dsr = _num(
        deflated_sharpe_ratio(
            m.daily_sharpe, daily_sharpe_variance, n_eff, m.n, m.skewness, m.kurtosis
        )
    )
    sr0 = annualize(expected_max_sharpe(n_eff, daily_sharpe_variance))
    summary = (
        f"With {trials.n_trials} settings tried ({low:.0f} to {high:.0f} independent by two "
        f"estimates; the larger is used), the chance that the best one's true Sharpe ratio "
        f"beats the {sr0:.2f} expected from the luckiest of them by chance is {_fmt(dsr, '.0%')}."
    )
    verdict, summary = trials.judge(probability_verdict(dsr), summary)
    return rs.DeflatedSharpeCheck(
        title="Deflated Sharpe ratio",
        verdict=verdict,
        summary=summary,
        metrics=rs.DeflatedSharpeMetrics(
            dsr=dsr,
            sharpe=_num(annualize(m.daily_sharpe)),
            expected_max_sharpe=sr0,
            n_trials=trials.n_trials,
            n_effective=n_eff,
            n_effective_correlation=trials.by_correlation,
            n_effective_eigenvalue=trials.by_eigenvalue,
            average_correlation=rho,
            sharpe_variance=daily_sharpe_variance,
            skewness=_num(m.skewness),
            kurtosis=_num(m.kurtosis),
        ),
    )


def _track_record_check(m: SharpeMoments, years: float, alpha: float) -> rs.TrackRecordCheck:
    psr = _num(probabilistic_sharpe_ratio(m.daily_sharpe, 0.0, m.n, m.skewness, m.kurtosis))
    trl = _num(min_track_record_length(m.daily_sharpe, 0.0, m.skewness, m.kurtosis, alpha))
    trl_years = None if trl is None else trl / ANNUALIZATION
    if trl_years is None:
        need = "its Sharpe ratio is not positive, so no amount of data would establish skill"
    else:
        need = f"{trl_years:.1f} years would be enough for {1 - alpha:.0%} confidence"
    summary = (
        f"Ignoring how many settings were tried, the chance that the selected setting's true "
        f"Sharpe ratio is above zero is {_fmt(psr, '.0%')}; {need}."
    )
    return rs.TrackRecordCheck(
        title="Probabilistic Sharpe ratio",
        verdict=probability_verdict(psr),
        summary=summary,
        metrics=rs.TrackRecordMetrics(
            psr=psr,
            sharpe=_num(annualize(m.daily_sharpe)),
            min_track_record_years=trl_years,
            years=years,
            alpha=alpha,
        ),
    )


def _min_backtest_check(n_eff: float, target: float, years: float) -> rs.MinBacktestCheck:
    min_years = _num(min_backtest_length(n_eff, target))
    bound = _num(min_backtest_length_bound(n_eff, target)) if target > 0 else None
    if min_years is None:
        summary = (
            "The selected setting's Sharpe ratio is not positive, so no length of data supports it."
        )
    else:
        summary = (
            f"With about {n_eff:.0f} independent settings tried, luck alone produces a best "
            f"Sharpe ratio of {target:.2f} in samples shorter than {min_years:.1f} years; "
            f"this backtest covers {years:.1f}."
        )
    return rs.MinBacktestCheck(
        title="Minimum backtest length",
        verdict=min_backtest_verdict(min_years, years),
        summary=summary,
        metrics=rs.MinBacktestMetrics(
            min_backtest_years=min_years,
            upper_bound_years=bound,
            years=years,
            target_sharpe=_num(target),
            n_effective=n_eff,
        ),
    )


def _sensitivity_check(
    trials: Trials, annual_sharpe: npt.NDArray[np.float64], best: int, s: Settings
) -> rs.SensitivityCheck:
    grid = trials.grid
    result = sensitivity(annual_sharpe, grid, best, s.radius)
    # ordered axes with more than one value, the only ones along which neighbours exist
    varied = [
        name
        for name, ordered, size in zip(grid.names, grid.ordered, grid.shape, strict=True)
        if ordered and size > 1
    ]
    axes = s.heatmap_axes if s.heatmap_axes is not None else tuple(varied[:2])
    retention = _num(result.retention)
    assessable = bool(result.neighbours)
    if not assessable:
        summary = (
            "No ordered parameter takes more than one value, so there are no neighbouring "
            "settings to compare."
        )
    elif result.best_sharpe <= 0:
        summary = "The best setting's Sharpe ratio is not positive."
    else:
        summary = (
            f"Settings next to the best one keep {_fmt(retention, '.0%')} of its Sharpe ratio "
            f"of {result.best_sharpe:.2f} on average."
        )
    return rs.SensitivityCheck(
        title="Parameter sensitivity",
        verdict=sensitivity_verdict(result.best_sharpe, retention, assessable),
        summary=summary,
        metrics=rs.SensitivityMetrics(
            best_sharpe=result.best_sharpe,
            neighbour_mean=_num(result.mean),
            neighbour_std=_num(result.std),
            retention=retention,
            n_neighbours=len(result.neighbours),
            radius=s.radius,
        ),
        details=rs.SensitivityDetails(
            heatmap=_heatmap(annual_sharpe, trials, best, result.neighbours, axes) if axes else None
        ),
    )


def _heatmap(
    annual_sharpe: npt.NDArray[np.float64],
    trials: Trials,
    best: int,
    near: tuple[int, ...],
    axes: tuple[str, ...],
) -> rs.Heatmap:
    hm = heatmap(annual_sharpe, trials.grid, best, axes)
    cells = {int(t): rs.Cell(x=c, y=r) for (r, c), t in np.ndenumerate(hm.trials)}
    return rs.Heatmap(
        x=rs.Axis(name=axes[0], values=list(hm.axis_values[0])),
        y=rs.Axis(name=axes[1], values=list(hm.axis_values[1])) if len(axes) == 2 else None,
        sharpe=[[float(v) for v in row] for row in hm.sharpe],
        trials=[[int(t) for t in row] for row in hm.trials],
        best=cells[best],
        neighbours=[cells[t] for t in near if t in cells],
    )


def overall_summary(checks: rs.Checks) -> tuple[rs.Verdict, str]:
    """The overall verdict and the sentence naming the checks behind it."""
    items: list[rs.Check] = [getattr(checks, field) for field in rs.Checks.model_fields]
    verdict = worst([c.verdict for c in items])

    def titled(v: rs.CheckVerdict) -> tuple[int, str]:
        titles = [c.title for c in items if c.verdict == v]
        return len(titles), ", ".join(titles)

    if verdict == "green":
        summary = (
            "Every check passes: the selected setting's performance is unlikely to be an "
            "artefact of the parameter search."
        )
    elif verdict == "yellow":
        (b, borderline), (u, unassessed) = titled("yellow"), titled("not_assessable")
        parts = [f"{b} of {len(items)} are borderline ({borderline})"] if b else []
        if u:
            of_all = "" if b else f"of {len(items)} "
            parts.append(f"{u} {of_all}cannot be assessed ({unassessed})")
        summary = (
            f"No check fails, but {' and '.join(parts)}: treat the selected setting's "
            "performance with caution."
        )
    else:
        n, failed = titled("red")
        summary = (
            f"{n} of {len(items)} checks fail ({failed}): the selected "
            "setting's performance may well be an artefact of the parameter search."
        )
    return verdict, summary


def _overall(checks: rs.Checks, selected: rs.Metrics, bench: rs.Metrics, name: str) -> rs.Overall:
    verdict, summary = overall_summary(checks)
    benchmark_summary = (
        "The checks ask whether the result could come from the search alone, not whether it "
        f"beats the market: over the same dates the selected setting's Sharpe ratio was "
        f"{_fmt(selected.sharpe)} against {_fmt(bench.sharpe)} for {name}, and its annual "
        f"return {_fmt(selected.cagr, '.1%')} against {_fmt(bench.cagr, '.1%')}."
    )
    return rs.Overall(verdict=verdict, summary=summary, benchmark_summary=benchmark_summary)
