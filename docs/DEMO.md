# Demo Results

SPY data from 1993-01-29 to 2026-10-30; each report's sample starts once every setting in its grid has a signal. Default costs (1 bp fees and 5 bps slippage per side). Sharpe ratios are annualized and net of costs. Buy and hold is a reference only and takes no part in any verdict.

## Pre-registered results

The configuration (D021) and the verdict thresholds (D022) were fixed before any strategy was run on real data. The reports in `results/demo/` come from a single run of `python -m backtest_lab.validation.demo` and are not regenerated (D032); to run the searches again, pass `--out` with another directory.

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
| PBO | green (0.05) | yellow (0.12) | yellow (0.299) |
| Deflated Sharpe ratio | yellow (0.945) | green (0.988) | red (0.15) |
| Probabilistic Sharpe ratio | green | green | yellow |
| Minimum backtest length | green | green | red |
| Parameter sensitivity | green | green | red |

The random-signal PBO of 0.299 sits just below the red line of 0.30; about one search in ten with no skill scores 0.30 or less (D022).

The random-signal grid varies `seed`, a number, so the grid search treats it as an ordered axis (D023) and the sensitivity check compares adjacent seeds. Neighbouring seeds are unrelated, so that verdict carries no information about the control. A grid can now declare such an axis categorical (D019); the registered configuration is kept as it was run.

**Rerun with re-fetched prices.** On 2026-11-08 the three searches were run again into a separate directory, with the registered configuration and dates, the code at commit a8bbfc3, and prices fetched from Yahoo that day. The overall and per-check verdicts, the selected settings, every summary sentence and the PBO values were identical to the registered files. The other numbers were not: of the 21,246 non-integer values in the three files, 98% differed by less than 0.00001 and all by less than 0.001, because Yahoo had revised its adjusted prices slightly, so the files are not byte-identical. The registered result is the frozen files in `results/demo/` (D032).

## Post hoc analysis

Not pre-registered. These questions were chosen after seeing the results above, to explain them. Restricting a grid to the half that won is a choice made knowing the outcome, so the numbers below are exploratory and carry no confirmatory weight; they are kept out of the credibility reports (D029). They come from `python -m backtest_lab.validation.posthoc`, which wrote `results/posthoc/long_only.json`; that file is fixed like the registered results, so a new run should pass `--out` with another directory.

**Long-only against long/short.** Each grid has an `allow_short` axis.

| | Moving average | Momentum |
|---|---|---|
| Sharpe range, long-only settings | 0.49 to 0.80 | 0.54 to 0.79 |
| Sharpe range, long/short settings | 0.02 to 0.51 | 0.01 to 0.53 |
| CSCV splits whose in-sample winner is long-only | 12,870 of 12,870 | 12,869 of 12,870 |
| PBO, whole grid (registered) | 0.05 | 0.12 |
| PBO, long-only half | 0.42 (64 settings) | 0.72 (17 settings) |

An in-sample winner that is always long-only ranks in the top half out of sample because the long/short half is worse, so the whole-grid PBO is low. Within the long-only half, which setting wins is no better than chance. The best long-only setting still has a significant deflated Sharpe ratio within that half (about 1.00 for both, with 10.5 and 3.8 effectively independent settings).

Counting every setting of the grid, as METHODS.md Section 5 requires, the deflated Sharpe ratios of the same two settings are the registered 0.945 and 0.988; the values near 1.00 hold only when the long/short half is left out.

**Independent trials.** The registered reports estimate the independent trials from the average correlation. The eigenvalue estimate (METHODS.md Section 5) and the rule that DSR and MinBTL use the larger of the two were adopted afterwards (D041). `results/posthoc/effective_trials.json` holds both for a rerun of the three searches on prices fetched on 2026-11-10; it is fixed like the other post hoc file.

| | Moving average | Momentum | Random signal |
|---|---|---|---|
| Settings tried | 128 | 34 | 100 |
| Independent, average correlation (registered) | 47.9 | 14.0 | 100.0 |
| Independent, eigenvalues | 72.6 | 20.2 | 99.7 |
| DSR with each | 0.945 / 0.919 | 0.988 / 0.979 | 0.147 / 0.147 |
| MinBTL in years with each | 8.0 / 9.1 | 4.8 / 5.8 | 123.4 / 123.3 |

With the larger estimate every DSR and MinBTL verdict is the registered one, and no search falls under the floor of 10 independent trials below which PBO and DSR get no verdict. The long-only halves above are smaller: by the average correlation they have 10.5 and 3.8 independent settings, so under that floor the momentum half would get no PBO or DSR verdict, and its 0.72 is a description of 17 similar settings, not a test.

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

**Stale opens.** This analysis is not in `results/posthoc/`; it uses SPY prices fetched on 2026-11-08 with the registered configuration and dates. Of the 8,497 bars from 1993-01-29 to 2026-10-30, 159 have an open equal to the previous close. Most fall in 1993 to 1995 (69), when SPY was quoted in fractions of a dollar down to 1/64 and such ties are expected, and in 2016 to 2017 (23). In the later group 21.7% of these opens also equal the day's high or low, against 0.4% of the other days of those two years, which points to stale data. A stale open turns a fill at the next open into a fill at the close that formed the signal.

Replacing the 159 opens with draws from each year's overnight volatility, clipped to the day's range (30 seeds), or with the day's low or high, leaves every moving-average and momentum verdict unchanged: the moving-average deflated Sharpe ratio stays between 0.944 and 0.946 and the momentum PBO between 0.119 and 0.129. The random-signal PBO, 8 splits below the red line, turns red in 12 of the 30 draws and with the highs, so 7 of 8 checks fail instead of 6; with the lows its holdout check turns green instead and 5 fail. Its overall verdict is red in every variant.
