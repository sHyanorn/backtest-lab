import numpy as np

from backtest_lab.validation.selection import best_trial, ranking_daily_sharpe


def test_degenerate_trials_rank_as_zero() -> None:
    # D020: a flat or constant-return trial has no Sharpe ratio and ranks as 0, so it is
    # never selected over a trial with a positive Sharpe ratio.
    noisy = 0.002 + 0.01 * np.random.default_rng(0).standard_normal(250)
    x = np.column_stack([np.zeros(250), np.full(250, 0.001), noisy])
    assert ranking_daily_sharpe(x)[:2].tolist() == [0.0, 0.0]
    assert best_trial(x) == 2
