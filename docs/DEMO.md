# Demo Results

SPY, 1993-01-29 to 2026-10-30, default costs (1 bp fees and 5 bps slippage per side). Sharpe ratios are annualized and net of costs.

## Pre-registered results

The configuration (D021) and the verdict thresholds (D022) were fixed before any strategy was run on real data. `python -m backtest_lab.validation.demo` writes one credibility report per search to `results/demo/`.

| Search | Trials | Selected setting | Sharpe, selected / buy and hold | Overall |
|---|---|---|---|---|
| Moving-average crossover | 128 | fast 10, slow 200, long only | 0.80 / 0.64 | yellow |
| Time-series momentum | 34 | lookback 273, long only | 0.79 / 0.65 | yellow |
| Random-signal control | 100 | seed 55 | 0.23 / 0.64 | red |

| Check | Moving average | Momentum | Random signal |
|---|---|---|---|
| Holdout split | green | green | red |
| Walk-forward analysis | green | green | red |
| Purged cross-validation | green | green | red |
| PBO | green (0.05) | yellow (0.12) | yellow (0.30) |
| Deflated Sharpe ratio | yellow (0.945) | green (0.988) | red (0.15) |
| Probabilistic Sharpe ratio | green | green | yellow |
| Minimum backtest length | green | green | red |
| Parameter sensitivity | green | green | red |

The random-signal PBO of 0.299 sits just below the red line of 0.30; about one search in ten with no skill lands there (D022).

The random-signal grid varies `seed`, a number, so the grid search treats it as an ordered axis (D023) and the sensitivity check compares adjacent seeds. Neighbouring seeds are unrelated, so that verdict carries no information about the control. A grid can now declare such an axis categorical (D019); the registered configuration is kept as it was run.

## Post hoc analysis

Not pre-registered. These questions were chosen after seeing the results above, to explain them. Restricting a grid to the half that won is a choice made knowing the outcome, so the numbers below are exploratory and carry no confirmatory weight; they are kept out of the credibility reports (D029). `python -m backtest_lab.validation.posthoc` writes them to `results/posthoc/long_only.json`.

**Long-only against long/short.** Each grid has an `allow_short` axis.

| | Moving average | Momentum |
|---|---|---|
| Sharpe range, long-only settings | 0.49 to 0.80 | 0.54 to 0.79 |
| Sharpe range, long/short settings | 0.02 to 0.51 | 0.01 to 0.53 |
| CSCV splits whose in-sample winner is long-only | 12,870 of 12,870 | 12,869 of 12,870 |
| PBO, whole grid (registered) | 0.05 | 0.12 |
| PBO, long-only half | 0.42 (64 settings) | 0.72 (17 settings) |

An in-sample winner that is always long-only ranks in the top half out of sample because the long/short half is worse, so the whole-grid PBO is low. Within the long-only half, which setting wins is close to chance. The best long-only setting still has a significant deflated Sharpe ratio within that half (about 1.00 for both, with 10.5 and 3.8 effectively independent settings).

**Selected setting against buy and hold.**

| | Moving average | Momentum | Buy and hold |
|---|---|---|---|
| Annual mean return | 10.0% | 11.1% | 12.0% |
| Annual volatility | 12.5% | 14.0% | 18.7% |
| CAGR | 9.7% | 10.6% | 10.8% |
| Maximum drawdown | -20.6% | -26.7% | -55.2% |
| Days in the market | 77% | 82% | 100% |

The buy-and-hold figures are for the moving-average sample, which starts in January 1994; over the momentum sample, which starts in August 1994, they differ by less than 0.3 percentage points.

Returns over the three deepest buy-and-hold drawdowns:

| Peak to trough | Buy and hold | Moving average | Momentum |
|---|---|---|---|
| 2007-10-09 to 2009-03-09 | -55.2% | -9.8% | -15.2% |
| 2000-03-24 to 2002-10-09 | -47.5% | -10.0% | -13.5% |
| 2020-02-19 to 2020-03-23 | -33.7% | -15.9% | -21.1% |

Both selected settings earn less than buy and hold on average and owe their higher Sharpe ratio to lower volatility. In the two long bear markets they lost 10% to 15% while buy and hold lost 48% to 55%.
