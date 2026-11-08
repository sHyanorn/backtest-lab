import numpy as np
import pandas as pd
import pytest

from backtest_lab.engine.backtest import INFORMATION_SPAN
from backtest_lab.validation.purged_kfold import (
    default_embargo,
    information_intervals,
    kfold_splits,
    purged_cv,
)


def test_hand_example() -> None:
    t0 = np.arange(10)
    splits = kfold_splits(t0, t0 + 1, k=5, embargo=1)
    train, test = splits[2]
    assert test.tolist() == [4, 5]
    # 3 and 6 overlap [4, 6] and are purged; 7 is embargoed
    assert train.tolist() == [0, 1, 2, 8, 9]


def test_reduces_to_ordinary_kfold() -> None:
    t = np.arange(10)
    for train, test in kfold_splits(t, t, k=3, embargo=0):
        assert sorted([*train, *test]) == list(range(10))


@pytest.mark.parametrize("seed", range(5))
def test_invariants_on_random_intervals(seed: int) -> None:
    rng = np.random.default_rng(seed)
    n, k, h = 200, 7, 5
    t0 = np.sort(rng.integers(0, 300, n))
    t1 = t0 + rng.integers(0, 15, n)
    splits = kfold_splits(t0, t1, k, h)
    tests = np.concatenate([test for _, test in splits])
    assert tests.tolist() == list(range(n))  # test folds partition the index, in order
    for train, test in splits:
        lo, hi = t0[test].min(), t1[test].max()
        assert not np.intersect1d(train, test).size
        assert not ((t0[train] <= hi) & (t1[train] >= lo)).any()  # no overlap
        assert not ((t0[train] > hi) & (t0[train] <= hi + h)).any()  # embargo


def test_intervals_follow_the_engine() -> None:
    t0, t1 = information_intervals(5)
    assert INFORMATION_SPAN == 1  # decided at close t, marked to close t + 1 (D013)
    assert (t1 - t0 == INFORMATION_SPAN).all()
    assert t1.tolist() == [0, 1, 2, 3, 4]


def test_daily_returns_purge_rows_sharing_a_close_with_the_test_fold() -> None:
    train, test = kfold_splits(*information_intervals(100), k=4, embargo=2)[1]
    assert test.tolist() == list(range(25, 50))
    # Row 24 ends at close 24, where row 25's signal forms, and row 50's signal forms at
    # close 49, the last test close: both are purged. Rows 51 and 52 are embargoed.
    assert train.tolist() == [*range(24), *range(53, 100)]


def test_default_embargo_rounds_up() -> None:
    assert default_embargo(100) == 1
    assert default_embargo(101) == 2
    assert default_embargo(300) == 3


def _matrix(t: int, n: int, seed: int) -> pd.DataFrame:
    x = 0.01 * np.random.default_rng(seed).standard_normal((t, n))
    return pd.DataFrame(x, index=pd.bdate_range("2000-01-03", periods=t))


def test_cv_selection_ignores_purged_and_embargoed_rows() -> None:
    # Identical trials, except that a row where the common return is 0 pays one trial a
    # gain; the larger the gain, the higher that trial's Sharpe on any rows that include it.
    t, h = 1000, 10
    base = 0.0005 + 0.01 * np.random.default_rng(0).standard_normal(t)
    rigged = {1: (199, 0.08), 2: (410, 0.07), 3: (411, 0.05)}
    base[[row for row, _ in rigged.values()]] = 0.0
    x = np.tile(base[:, None], (1, 4))
    for trial, (row, gain) in rigged.items():
        x[row, trial] = gain
    frame = pd.DataFrame(x, index=pd.bdate_range("2000-01-03", periods=t))
    fold = purged_cv(frame, k=5, embargo=h).folds[1]  # test rows 200-399
    # Row 199 is purged, rows 400 (purged) to 410 (embargoed) are dropped, 411 is kept.
    assert fold.n_train == t - 200 - 1 - (1 + h)
    assert fold.trial == 3


def test_cv_selects_a_planted_edge_in_every_fold() -> None:
    x = _matrix(2000, 20, seed=0)
    x[11] += 0.002
    cv = purged_cv(x, k=5)
    assert cv.embargo == 20
    assert [f.trial for f in cv.folds] == [11] * 5
    assert cv.score > 0
    assert cv.retention is not None and cv.retention > 0.5
    assert [f.test_start for f in cv.folds] == [x.index[i] for i in range(0, 2000, 400)]


def test_cv_of_noise_scores_near_zero() -> None:
    scores = [purged_cv(_matrix(1000, 50, seed), k=5).score for seed in range(20)]
    # each fold has 200 days; the mean of 5 folds has SE about sqrt(252 / 1000)
    assert abs(np.mean(scores)) < 2 * np.sqrt(252 / 1000) / np.sqrt(20)
