# Demo Results

Results of three parameter searches on SPY, registered before any strategy was run on real data, of registered tests against buy and hold on samples the grids never saw, and of post hoc analyses. SPY data run from 1993-01-29 to 2026-10-30, and each report's sample starts once every setting in its grid has a signal. Costs are 1 bp in fees and 5 bps in slippage per side, and Sharpe ratios are annualized and net of costs.

- The moving-average and momentum searches are borderline (yellow): one check of eight, the deflated Sharpe ratio (0.945) and PBO (0.12) respectively, falls short of a pass. The random-signal control is red and fails 6 of 8 checks.
- No setting of either grid is shown to beat buy and hold in Sharpe ratio or mean return, after correcting for the grids and for the families: on the US market from 1926 to 1993 the smallest Holm-adjusted p is 1.0 (4 families), on eight ETFs 0.928 (32 families).
- The checks of a credibility report do not compare a result with buy and hold, which takes no part in any verdict, and in a market that rose a long-only setting with no timing ability can pass them. The tests against buy and hold have low power: for orientation, a finding needs an annualized Sharpe difference of about 0.25 to 0.28 on the US market and 0.45 to 0.55 on an ETF (Limits).

## Registered results

### Three searches on SPY

The configuration (D021) and the verdict thresholds (D022) were fixed before the run. The reports in `results/demo/` come from one run and are not regenerated (D032).

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

The random-signal PBO of 0.299 sits just below the red line of 0.30; about one search in ten with no skill scores 0.30 or less (D022). The registered summary sentences round percentages to whole numbers, so the moving-average deflated Sharpe ratio of 0.945 reads 95% and both probabilistic Sharpe ratios, just under 1, read 100%. Reports built since D042 do not round a figure onto or across a verdict threshold.

### Tests against buy and hold

Registered in D043 before any strategy was run on these samples, with the corrections of D046 made before the run; the formulas are in METHODS.md Section 8. They are not checks of a credibility report and change no verdict above. A family is one sample, one grid and one criterion, and a finding is a family whose Holm-adjusted p-value is at most 0.05. There are no findings, StepM named no setting in any family, and no setting was left out of the studentized tests.

- **Samples.** (ii) the value-weighted US market, `Mkt-RF` plus `RF` from the daily Fama/French 3 factors file: 17,863 rows from 1926-07-01 to 1993-01-28, the last day before SPY's first bar. 1,158 rows are Saturdays, to 1952-05-24 (D043). The file has no opens, so a target decided at close t fills at close t+1 (D044), and costs are 84 bps per side (Jones, 2002). Over their overlap, 8,474 days from 1993-02-01 to 2026-09-30, the file's daily returns correlate 0.9786 with SPY's, and SPY's mean return is 0.10 percentage points a year lower. (iii) QQQ, IWM, EFA, EEM, TLT, IEF, SHY and GLD from their first bar to 2026-10-30, with fills at the next open (D013) and 6 bps per side (D014). (i), SPY, is post hoc and appears below.
- **Grids.** D021's 128 moving-average and 34 momentum settings on each sample's own instrument. A grid's aligned days start once all its settings have a signal, so the two grids of a sample use different days.
- **Benchmark.** Buy and hold of the same instrument with the same fills and costs. Cash earns nothing and Sharpe ratios are on nominal returns (D015).
- **Criteria.** The difference in daily Sharpe ratio between a setting and buy and hold, and the mean of the daily difference in their returns, annualized by √252 and by 252 in the tables; annualized figures decide nothing.
- **Decision.** Hansen's SPA consistent p-value on one stationary bootstrap of whole days, with a mean block length L of 10 days, 10,000 resamples and seed 0. Holm adjusts the p-values within (ii), 4 families, and within (iii), 32. StepM runs at 0.05/4 in (ii) and 0.05/32 in (iii). An SPA p-value of 1.0 means no setting's difference is above zero, so no setting is ahead of buy and hold on that criterion over the sample (D046); Holm-adjusted values are capped at 1.

All 36 families, from `results/relative/french.json` (the US market) and `results/relative/etfs.json` (the ETFs), produced by `python -m backtest_lab.validation.relative` at commit 8bf4b45. The best difference is in Sharpe ratio, or in percentage points a year for mean return, and the best settings are in the files. L = 10 decides; the other block lengths are reported beside it. In every family but one, the Reality Check and the SPA lower, consistent and upper p-values exceed 0.05; the exception is SHY momentum on the Sharpe ratio (0.0237, 0.029 and 0.0407).

| Sample | Grid | Criterion | Days | Best difference | SPA, L = 10 | L = 5 | L = 20 | L = 50 | Holm |
|---|---|---|---|---|---|---|---|---|---|
| US market | Moving average | Sharpe ratio | 17,613 | 0.07 | 0.6826 | 0.6692 | 0.6914 | 0.6925 | 1.0 |
| US market | Moving average | Mean return | 17,613 | -2.24% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| US market | Momentum | Sharpe ratio | 17,484 | -0.04 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| US market | Momentum | Mean return | 17,484 | -3.50% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| QQQ | Moving average | Sharpe ratio | 6,705 | 0.21 | 0.3299 | 0.3405 | 0.3421 | 0.3378 | 1.0 |
| QQQ | Moving average | Mean return | 6,705 | 0.61% | 0.7348 | 0.7415 | 0.7376 | 0.7322 | 1.0 |
| QQQ | Momentum | Sharpe ratio | 6,576 | 0.25 | 0.2751 | 0.2822 | 0.2574 | 0.2454 | 1.0 |
| QQQ | Momentum | Mean return | 6,576 | -0.51% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| IWM | Moving average | Sharpe ratio | 6,397 | 0.01 | 0.9112 | 0.9042 | 0.9256 | 0.9372 | 1.0 |
| IWM | Moving average | Mean return | 6,397 | -3.67% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| IWM | Momentum | Sharpe ratio | 6,268 | -0.01 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| IWM | Momentum | Mean return | 6,268 | -3.87% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| EFA | Moving average | Sharpe ratio | 6,082 | 0.20 | 0.442 | 0.4516 | 0.4172 | 0.3978 | 1.0 |
| EFA | Moving average | Mean return | 6,082 | -1.06% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| EFA | Momentum | Sharpe ratio | 5,953 | 0.17 | 0.4951 | 0.5132 | 0.4702 | 0.4503 | 1.0 |
| EFA | Momentum | Mean return | 5,953 | -1.85% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| EEM | Moving average | Sharpe ratio | 5,676 | 0.13 | 0.6082 | 0.6294 | 0.5801 | 0.5656 | 1.0 |
| EEM | Moving average | Mean return | 5,676 | -1.94% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| EEM | Momentum | Sharpe ratio | 5,547 | 0.12 | 0.6006 | 0.6065 | 0.6001 | 0.5797 | 1.0 |
| EEM | Momentum | Mean return | 5,547 | -1.82% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| TLT | Moving average | Sharpe ratio | 5,854 | 0.15 | 0.4928 | 0.5066 | 0.4732 | 0.4284 | 1.0 |
| TLT | Moving average | Mean return | 5,854 | 1.25% | 0.7087 | 0.7206 | 0.704 | 0.6957 | 1.0 |
| TLT | Momentum | Sharpe ratio | 5,725 | 0.04 | 0.84 | 0.8425 | 0.8308 | 0.8228 | 1.0 |
| TLT | Momentum | Mean return | 5,725 | -0.56% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| IEF | Moving average | Sharpe ratio | 5,854 | 0.07 | 0.7692 | 0.7775 | 0.7623 | 0.7455 | 1.0 |
| IEF | Moving average | Mean return | 5,854 | -0.43% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| IEF | Momentum | Sharpe ratio | 5,725 | 0.04 | 0.7857 | 0.7957 | 0.7795 | 0.7805 | 1.0 |
| IEF | Momentum | Mean return | 5,725 | -0.26% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| SHY | Moving average | Sharpe ratio | 5,854 | 0.17 | 0.1867 | 0.1676 | 0.2112 | 0.2718 | 1.0 |
| SHY | Moving average | Mean return | 5,854 | 0.07% | 0.7189 | 0.7311 | 0.6953 | 0.6797 | 1.0 |
| SHY | Momentum | Sharpe ratio | 5,725 | 0.26 | 0.029 | 0.0233 | 0.0484 | 0.0918 | 0.928 |
| SHY | Momentum | Mean return | 5,725 | 0.20% | 0.4462 | 0.4421 | 0.4522 | 0.4331 | 1.0 |
| GLD | Moving average | Sharpe ratio | 5,272 | 0.11 | 0.6693 | 0.6575 | 0.6664 | 0.6417 | 1.0 |
| GLD | Moving average | Mean return | 5,272 | -0.79% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| GLD | Momentum | Sharpe ratio | 5,143 | 0.01 | 0.8919 | 0.8804 | 0.8941 | 0.9 | 1.0 |
| GLD | Momentum | Mean return | 5,143 | -0.77% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

Variants of (ii), with SPA consistent p-values at L = 10 and the best setting's annualized difference in parentheses. In the cash variant, capital not held in a position earns `RF`, short proceeds earn nothing, and Sharpe ratios are on returns in excess of `RF` (D046). The split at 1960-01-04, the first row of 1960, divides the deciding run's aligned days; signals carry across it.

| Variant | Days | Moving average, Sharpe | Moving average, mean return | Momentum, Sharpe | Momentum, mean return |
|---|---|---|---|---|---|
| 84 bps per side (deciding run) | 17,613 / 17,484 | 0.6826 (0.07) | 1.0 (-2.24%) | 1.0 (-0.04) | 1.0 (-3.50%) |
| 0 bps | 17,613 / 17,484 | 0.0591 (0.28) | 1.0 (-0.51%) | 0.0442 (0.30) | 1.0 (-0.60%) |
| 6 bps | 17,613 / 17,484 | 0.0895 (0.26) | 1.0 (-0.64%) | 0.1361 (0.22) | 1.0 (-1.00%) |
| 25 bps | 17,613 / 17,484 | 0.2807 (0.19) | 1.0 (-1.03%) | 0.6048 (0.10) | 1.0 (-1.90%) |
| 50 bps | 17,613 / 17,484 | 0.455 (0.13) | 1.0 (-1.54%) | 0.789 (0.04) | 1.0 (-2.58%) |
| Cash earns `RF`, Sharpe ratios on excess returns | 17,613 / 17,484 | 0.6934 (0.07) | 1.0 (-1.29%) | 1.0 (-0.06) | 1.0 (-2.65%) |
| Before 1960-01-04 | 9,291 / 9,162 | 0.5834 (0.15) | 1.0 (-1.17%) | 0.6172 (0.12) | 1.0 (-1.55%) |
| From 1960-01-04 | 8,322 / 8,322 | 1.0 (-0.04) | 1.0 (-2.73%) | 1.0 (-0.20) | 1.0 (-4.46%) |

D021's selected settings, fast 10, slow 200, long only and lookback 273, long only, each tested alone against buy and hold by the SPA consistent p-value, which for one setting is a one-sided studentized bootstrap test:

| Sample | Moving average, Sharpe ratio | Moving average, mean return | Momentum, Sharpe ratio | Momentum, mean return |
|---|---|---|---|---|
| US market | 0.4858 | 1.0 | 1.0 | 1.0 |
| QQQ | 0.3035 | 1.0 | 0.206 | 1.0 |
| IWM | 1.0 | 1.0 | 1.0 | 1.0 |
| EFA | 0.1465 | 1.0 | 1.0 | 1.0 |
| EEM | 1.0 | 1.0 | 0.4625 | 1.0 |
| TLT | 1.0 | 1.0 | 1.0 | 1.0 |
| IEF | 1.0 | 1.0 | 1.0 | 1.0 |
| SHY | 0.4292 | 1.0 | 0.3959 | 1.0 |
| GLD | 1.0 | 1.0 | 1.0 | 1.0 |

Reading of these results:

- On (ii) the Sharpe p-values rise with costs, from 0.0591 (moving average) and 0.0442 (momentum) at 0 bps to 0.6826 and 1.0 at 84 bps. The momentum value at 0 bps is the only one among (ii)'s variants at or below 0.05, before any correction for the 4 families; a run without costs is not tradable and decides nothing.
- Every setting of both grids has a lower mean return than buy and hold over (ii)'s days at each cost tested, and from 1960 every setting is behind buy and hold in both Sharpe ratio and mean return. Before 1960 the best Sharpe differences are 0.15 and 0.12.
- The smallest p-value of (iii) before Holm, 0.029 (SHY, momentum, Sharpe ratio), is the only one at or below 0.05 among its 32 families; Holm multiplies it by 32, to 0.928. It is 0.0233 at L = 5, 0.0484 at L = 20 and 0.0918 at L = 50. In 12 of the 16 mean-return families of (iii), no setting is ahead of buy and hold.
- D021's selected settings have no SPA consistent p-value below 0.1465 (EFA, moving average, Sharpe ratio), and every one of their mean-return p-values is 1.0.

## Post hoc analysis

These questions were chosen after seeing the registered results. Restricting a grid to the half that won is a choice made knowing the outcome, so the numbers below are exploratory and carry no confirmatory weight, and they are kept out of the credibility reports (D029). `results/posthoc/` holds them, fixed like the registered results.

### SPY against buy and hold

D021's results on SPY were known before D043, so this is not a registered test. It reruns D043's code over D021's sample at 6 bps per side, with StepM at 0.05/4, in `results/posthoc/relative_spy.json`. D021's selected settings, tested alone, have SPA consistent p-values of 0.1065 (moving average) and 0.1158 (momentum) on the Sharpe ratio and 1.0 for both on the mean return.

| Grid | Criterion | Days | Best setting | Best difference, annualized | Reality Check | SPA lower | SPA consistent | SPA upper | Consistent, L = 5 | L = 20 | L = 50 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Moving average | Sharpe ratio | 8,247 | fast 10, slow 200, long only | 0.16 | 0.5705 | 0.3684 | 0.4495 | 0.4552 | 0.4533 | 0.4288 | 0.42 |
| Moving average | Mean return | 8,247 | fast 50, slow 250, long only | -1.17% | 0.9343 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| Momentum | Sharpe ratio | 8,118 | lookback 273, long only | 0.14 | 0.5784 | 0.3034 | 0.3934 | 0.4023 | 0.4 | 0.386 | 0.3943 |
| Momentum | Mean return | 8,118 | lookback 273, long only | -1.13% | 0.9291 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

### Long-only against long/short

Each grid has an `allow_short` axis (`results/posthoc/long_only.json`).

| | Moving average | Momentum |
|---|---|---|
| Sharpe range, long-only settings | 0.49 to 0.80 | 0.54 to 0.79 |
| Sharpe range, long/short settings | 0.02 to 0.51 | 0.01 to 0.53 |
| CSCV splits whose in-sample winner is long-only | 12,870 of 12,870 | 12,869 of 12,870 |
| PBO, whole grid (registered) | 0.05 | 0.12 |
| PBO, long-only half | 0.42 (64 settings) | 0.72 (17 settings) |

The in-sample winner is long-only in nearly every split and the long/short half has lower Sharpe ratios, so the winner ranks in the top half out of sample and the whole-grid PBO is low. Within the long-only half, picking the winner is not shown to beat chance. The best long-only setting has a deflated Sharpe ratio of about 1.00 within that half, with 10.5 and 3.8 effectively independent settings by the average-correlation estimate, the only one computed for the halves. The momentum half is below the floor of 10 independent trials, so its figure would get no verdict, and the moving-average half is barely above it. Counting every setting of the grid, the registered deflated Sharpe ratios of the same two settings are 0.945 and 0.988.

### Independent trials

The registered reports estimate the independent trials from the average correlation. The eigenvalue estimate (METHODS.md Section 5) and the rule that DSR and MinBTL use the larger of the two were adopted afterwards (D041). `results/posthoc/effective_trials.json` holds both for a rerun of the three searches on prices fetched on 2026-11-10.

| | Moving average | Momentum | Random signal |
|---|---|---|---|
| Settings tried | 128 | 34 | 100 |
| Independent, average correlation (registered) | 47.9 | 14.0 | 100.0 |
| Independent, eigenvalues | 72.6 | 20.2 | 99.7 |
| DSR with each | 0.945 / 0.919 | 0.988 / 0.979 | 0.147 / 0.147 |
| MinBTL in years with each | 8.0 / 9.1 | 4.8 / 5.8 | 123.4 / 123.3 |

With the larger estimate every DSR and MinBTL verdict is the registered one, and no search falls under the floor of 10 independent trials below which PBO and DSR cannot pass.

### Selected setting against buy and hold

| | Moving average | Momentum | Buy and hold |
|---|---|---|---|
| Annual mean return | 10.0% | 11.1% | 12.0% |
| Annual volatility | 12.5% | 14.0% | 18.7% |
| CAGR | 9.7% | 10.6% | 10.8% |
| Maximum drawdown | -20.6% | -26.7% | -55.2% |
| Days in the market | 77% | 82% | 100% |

The buy-and-hold figures are for the moving-average sample, which starts in January 1994; over the momentum sample, which starts in August 1994, they differ by less than 0.3 percentage points. Returns over the three deepest buy-and-hold drawdowns:

| Peak to trough | Buy and hold | Moving average | Momentum |
|---|---|---|---|
| 2007-10-09 to 2009-03-09 | -55.2% | -9.8% | -15.2% |
| 2000-03-24 to 2002-10-09 | -47.5% | -10.0% | -13.5% |
| 2020-02-19 to 2020-03-23 | -33.7% | -15.9% | -21.1% |

Both selected settings earn less than buy and hold and owe their higher Sharpe ratio to lower volatility. In the two long bear markets they lost 10% to 15% while buy and hold lost 48% to 55%.

### Stale opens

Of the 8,497 SPY bars from 1993-01-29 to 2026-10-30, 159 have an open equal to the previous close. Most fall in 1993 to 1995 (69) and in 2016 to 2017 (23). In 2016 to 2017, 21.7% of these opens also equal the day's high or low against 0.4% of the other days of those two years, which points to stale data. A stale open turns a fill at the next open into a fill at the close that formed the signal. Replacing the 159 opens with draws from each year's overnight volatility, clipped to the day's range (30 seeds), or with the day's low or high, leaves every moving-average and momentum verdict unchanged: the moving-average deflated Sharpe ratio stays between 0.944 and 0.946 and the momentum PBO between 0.119 and 0.129. The random-signal PBO, 8 splits below the red line, turns red in 12 of the 30 draws and with the highs, so 7 of 8 checks fail instead of 6; with the lows its holdout check turns green and 5 fail. Its overall verdict is red in every variant. This analysis used SPY prices fetched on 2026-11-08; the script and its output were not kept (Limits).

## Limits

- **Power.** D043's rough critical difference, for orientation only: for a long-only setting whose daily returns correlate about 0.8 with buy and hold, with independent returns, a finding needs an annualized Sharpe difference of about 0.25 to 0.28 on (ii) and 0.45 to 0.55 on an ETF, so smaller true differences are unlikely to be found. Long/short settings have standard errors about 1.5 times larger. Not being shown to beat buy and hold does not show that no setting does.
- **Assumptions.** The tests assume stationary, weakly dependent returns, which a sample dominated by one episode such as 1929 to 1932 strains (METHODS.md Section 8), and for the Sharpe difference the studentization of the SPA and StepM rests on the delta method.
- **Annualization before 1952.** With about 280 to 300 rows a year, annualizing by 252 rows understates the figures of (ii) by up to about 9% for Sharpe differences, annualized by √252 (D043).
- **Costs of (ii).** A constant, the average one-way cost of trading NYSE stocks over 1925 to 2000 in Jones (2002), half the quoted spread on Dow Jones stocks plus the average commission. His text puts the cost below 0.50% in 1926 to 1928 and from 1991, and at 1.00% or more from 1953 to 1975, and gives no average for 1926 to 1993 alone.
- **Grids.** They hold conventional values, such as a 200-day average and a 12-month lookback, whose popularity owes something to long US histories that include 1926 to 1993; (ii) is unseen by these grids but not by the practice that chose such values.
- **Choices made knowing earlier checks.** Post hoc checks on SPY with code that is not in the repository were known before D043, and the choice of the SPA consistent p-value to decide and of L = 10 was made knowing them (D043).
- **Overlap of samples.** The ETFs share their dates with SPY, and QQQ and IWM are US equity funds, so (iii) is not independent of (i). Cash earns nothing in the benchmark, which works against settings that are often out of the market.
- **Random-signal sensitivity.** The grid varies `seed`, so the grid search treats it as an ordered axis (D023) and the sensitivity check compares adjacent seeds. Neighbouring seeds are unrelated, so that verdict carries no information about the control. A grid can now declare such an axis categorical (D019); the registered configuration is kept as it was run.
- **Stale opens in the ETFs.** The stale-opens analysis above covers SPY only. On Yahoo data of 2026-11-08, D038 counts opens that equal the previous close and the day's high or low at 249 bars for SHY, 17 for EEM and 13 for IWM, and fewer for the other ETFs; it judges most of SHY's since 2010 genuine. A stale open turns a fill into a fill at the signal's close.
- **Not kept in the repository.** The rerun of 2026-11-08 and the stale-opens analysis. In the rerun, with the registered configuration and dates, the code at commit a8bbfc3 and prices fetched from Yahoo that day, the overall and per-check verdicts, the selected settings, every summary sentence and the PBO values were identical to the registered files; of the 21,246 non-integer values in the three files, 98% differed by less than 0.00001 and all by less than 0.001, which fits slight revisions of Yahoo's adjusted prices.

## Reproduce

The registered files in `results/demo/`, `results/relative/` and `results/posthoc/` are fixed, and CI checks them against their `SHA256SUMS` (D032). Run the commands with another output directory to repeat a study:

```bash
uv run python -m backtest_lab.data.update     # prices, the eight ETFs and SPY included
uv run python -m backtest_lab.data.french     # the daily Fama/French 3 factors zip
uv run python -m backtest_lab.validation.demo --out /tmp/demo
uv run python -m backtest_lab.validation.relative --out /tmp/relative --posthoc-out /tmp/relative-posthoc
uv run python -m backtest_lab.validation.posthoc --out /tmp/posthoc
```

The prices and the Fama/French zip are not committed (D003). The relative study stops unless the Fama/French rows before 1993-01-29 and the eight ETFs' rows match the digests registered in D043, and Yahoo's revisions of adjusted prices (see Limits) can make later data fail that check. Each family is cached in `data/cache/relative/` when done, so an interrupted run resumes.
