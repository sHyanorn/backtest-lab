import itertools
import math

import numpy as np
import pytest

from backtest_lab.validation.pbo import cscv, n_combinations, selection_logits
from backtest_lab.validation.selection import sharpe_ratios


def _noise(seed: int) -> np.ndarray:
    return 0.01 * np.random.default_rng(seed).standard_normal((1000, 100))


def test_ranking_example_from_the_paper() -> None:
    # Section 2.1: R = (0.5, 1.1, 0.7) ranks (1, 3, 2); R-bar = (0.6, 0.7, 1.3) ranks (1, 2, 3)
    logits = selection_logits(np.array([[0.5, 1.1, 0.7]]), np.array([[0.6, 0.7, 1.3]]))
    assert logits.tolist() == [0.0]  # n* = 2, omega = 2/4


def test_ties_take_the_first_winner_and_average_ranks() -> None:
    # winner is column 0; OOS ranks of (1, 1, 0) are (2.5, 2.5, 1)
    logits = selection_logits(np.array([[1.0, 1.0, 0.0]]), np.array([[1.0, 1.0, 0.0]]))
    assert logits[0] == pytest.approx(math.log(2.5 / 1.5))


@pytest.mark.parametrize(("s", "c"), [(12, 924), (16, 12_870), (24, 2_704_156)])
def test_number_of_combinations(s: int, c: int) -> None:
    assert n_combinations(s) == c


def _two_blocks(first: tuple[float, ...], second: tuple[float, ...]) -> np.ndarray:
    # each column n in a block is (a_n, a_n + 0.02), so all columns share one std
    rows = [first, tuple(a + 0.02 for a in first), second, tuple(a + 0.02 for a in second)]
    return np.array(rows)


def test_persistent_extreme() -> None:
    result = cscv(_two_blocks((0.01, 0.02, 0.03), (0.01, 0.02, 0.03)), blocks=2)
    np.testing.assert_allclose(result.logits, [math.log(3)] * 2)
    assert result.pbo == 0.0


def test_reversed_extreme() -> None:
    result = cscv(_two_blocks((0.01, 0.02, 0.03), (0.03, 0.02, 0.01)), blocks=2)
    np.testing.assert_allclose(result.logits, [-math.log(3)] * 2)
    assert result.pbo == 1.0
    assert result.prob_oos_loss == 0.0


def test_a_winner_at_the_oos_median_counts_as_overfit() -> None:
    # Odd N: each IS winner ranks 2 of 3 OOS, so lambda = 0, which counts (METHODS Section 4)
    result = cscv(_two_blocks((0.01, 0.02, 0.03), (0.01, 0.03, 0.02)), blocks=2)
    assert result.logits.tolist() == [0.0, 0.0]
    assert result.pbo == 1.0


def test_union_sharpe_matches_direct_computation() -> None:
    x = np.random.default_rng(0).normal(0.0005, 0.01, (103, 5))  # 103 = 6 x 17 + 1
    result = cscv(x, blocks=6)
    blocks = x[1:].reshape(6, 17, 5)
    for c, chosen in enumerate(itertools.combinations(range(6), 3)):
        rest = [b for b in range(6) if b not in chosen]
        is_sr = sharpe_ratios(np.concatenate(blocks[list(chosen)]))
        oos_sr = sharpe_ratios(np.concatenate(blocks[rest]))
        winner = int(np.argmax(is_sr))
        assert result.winners[c] == winner
        assert result.is_sharpe[c] == pytest.approx(is_sr[winner], rel=1e-12)
        assert result.oos_sharpe[c] == pytest.approx(oos_sr[winner], rel=1e-12)


def test_degenerate_columns_rank_as_zero_without_warnings() -> None:
    x = np.random.default_rng(1).normal(0.0, 0.01, (64, 4))
    x[:, 0] = 0.0
    x[:, 1] = 0.01  # constant: zero variance, not a huge Sharpe from rounding
    with np.errstate(all="raise"):
        result = cscv(x, blocks=4)
    assert np.isfinite(result.logits).all()
    assert (np.abs(result.is_sharpe) < 10).all()


def test_random_control() -> None:
    # Expected PBO is 0.5 for even N; one seed is noisy, so average seeds 0-99.
    mean = np.mean([cscv(_noise(seed)).pbo for seed in range(100)])
    assert 0.42 <= mean <= 0.58


@pytest.mark.parametrize("seed", range(10))
def test_planted_edge(seed: int) -> None:
    result = cscv(_noise(seed) + np.linspace(0, 0.002, 100))
    assert result.pbo < 0.1


def test_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="even"):
        cscv(_noise(0), blocks=15)
    with pytest.raises(ValueError, match="two rows"):
        cscv(_noise(0)[:20], blocks=16)
