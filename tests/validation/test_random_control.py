"""SPEC Section 8: a grid of random-signal strategies run through the engine has no skill,
so PBO should be near 0.5 and the best trial's DSR should not be significant."""

import numpy as np

from backtest_lab.validation.pbo import cscv
from backtest_lab.validation.search import Grid, run_grid
from backtest_lab.validation.selection import sharpe_ratios
from backtest_lab.validation.sharpe_stats import (
    average_correlation,
    deflated_sharpe_ratio,
    effective_trials,
    sharpe_moments,
)
from tests.factories import synthetic_market

GRID = Grid.of({"seed": list(range(50))}, {"ticker": "SPY", "hold": 5})


def test_random_signals_look_overfit_and_insignificant() -> None:
    # Calibration over price paths 1000-1039: PBO mean 0.487 (sd 0.165); DSR at most 0.62.
    pbos, dsrs = [], []
    for path in range(1000, 1010):
        x = run_grid(
            "random_signal", GRID, synthetic_market(n=1500, seed=path), processes=1
        ).returns
        pbos.append(cscv(x).pbo)
        sr = np.nan_to_num(sharpe_ratios(x), nan=0.0)
        best = sharpe_moments(x[int(np.argmax(sr))])
        n_eff = effective_trials(average_correlation(x), x.shape[1])
        dsrs.append(
            deflated_sharpe_ratio(
                best.sharpe, float(np.var(sr, ddof=1)), n_eff, best.n, best.skewness, best.kurtosis
            )
        )
    assert 0.33 <= np.mean(pbos) <= 0.67
    assert max(dsrs) < 0.95
