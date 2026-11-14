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

The registered summary sentences round percentages to whole numbers, so the moving-average deflated Sharpe ratio of 0.945 reads 95% and both probabilistic Sharpe ratios, just under 1, read 100%. Reports built since D042 do not round a figure onto or across a verdict threshold.

The random-signal grid varies `seed`, a number, so the grid search treats it as an ordered axis (D023) and the sensitivity check compares adjacent seeds. Neighbouring seeds are unrelated, so that verdict carries no information about the control. A grid can now declare such an axis categorical (D019); the registered configuration is kept as it was run.

**Rerun with re-fetched prices.** On 2026-11-08 the three searches were run again into a separate directory, with the registered configuration and dates, the code at commit a8bbfc3, and prices fetched from Yahoo that day. The overall and per-check verdicts, the selected settings, every summary sentence and the PBO values were identical to the registered files. The other numbers were not: of the 21,246 non-integer values in the three files, 98% differed by less than 0.00001 and all by less than 0.001, because Yahoo had revised its adjusted prices slightly, so the files are not byte-identical. The registered result is the frozen files in `results/demo/` (D032).

## Tests against buy and hold

On the US market from 1926 to 1993, no setting of either grid is shown to beat buy and hold in Sharpe ratio or in mean return after correcting for the grids and for the 4 families (smallest Holm-adjusted p 1.0). On the eight ETFs, no setting of either grid is shown to beat buy and hold in Sharpe ratio or in mean return after correcting for the grids and for the 32 families (smallest Holm-adjusted p 0.928).

Registered in D043 before any strategy was run on these samples, with the corrections of D046 made before the run; the formulas are in METHODS.md Section 8. The results come from `python -m backtest_lab.validation.relative` at commit 8bf4b45: `results/relative/french.json` for (ii), the US market, and `results/relative/etfs.json` for (iii), the eight ETFs. (i), SPY, is post hoc and is in `results/posthoc/relative_spy.json`. The files are not regenerated, and CI checks them against their `SHA256SUMS` (D032). These tests are not checks of a credibility report and change no verdict above.

- Grids: D021's, 128 moving-average and 34 momentum settings, on each sample's own instrument. A grid's aligned days start once all its settings have a signal, so the two grids of a sample use different days.
- (ii): the value-weighted US market, `Mkt-RF` plus `RF` from the daily Fama/French 3 factors file, 17,863 rows from 1926-07-01 to 1993-01-28, the last day before SPY's first bar in D021. 1,158 rows are Saturdays, from 1926-07-10 to 1952-05-24 (D043). The file has no opens, so a target decided at close t fills at close t+1 (D044). Costs are 84 bps per side (Jones, 2002). As a data check, where the file and SPY overlap, from 1993-02-01 to 2026-09-30 (8,474 days), their daily returns correlate 0.9786 and SPY's mean return is 0.10 percentage points a year lower.
- (iii): QQQ, IWM, EFA, EEM, TLT, IEF, SHY and GLD from their first bar to 2026-10-30, D021's last day, with fills at the next open (D013) and 6 bps per side (D014). They share their dates with SPY, and QQQ and IWM are US equity funds, so (iii) is not independent of (i).
- Benchmark: buy and hold of the same instrument with the same fills and costs. Cash earns nothing and Sharpe ratios are on nominal returns (D015), which works against settings that are often out of the market.
- Criteria: the difference in daily Sharpe ratio between a setting and buy and hold, and the mean of the daily difference in their returns. The tables annualize them by √252 and by 252; annualized figures decide nothing.
- Decision: a family is one sample, one grid and one criterion. Its p-value is Hansen's SPA consistent p-value on one stationary bootstrap of whole days, with a mean block length L of 10 days, 10,000 resamples and seed 0. Holm adjusts the p-values within (ii), 4 families, and within (iii), 32; a finding is a family whose adjusted p-value is at most 0.05. StepM runs in every family at 0.05/4 in (ii) and 0.05/32 in (iii).
- StepM named no setting, and no setting was left out of the studentized tests, in any family of the three files.
- Every SPA p-value of 1.0 in the grid tables below comes from a family in which no setting's difference is above zero, that is, no setting is ahead of buy and hold on that criterion over the sample; D046 sets the SPA p-values to 1 there. Holm-adjusted values are capped at 1.

**Deciding run, (ii) the US market.** Best setting is the setting with the largest difference; mean-return differences are in percentage points a year.

| Grid | Criterion | Days | Best setting | Best difference, annualized | Reality Check | SPA lower | SPA consistent | SPA upper | Holm-adjusted |
|---|---|---|---|---|---|---|---|---|---|
| Moving average | Sharpe ratio | 17,613 | fast 5, slow 250, long only | 0.07 | 0.7779 | 0.4491 | 0.6826 | 0.742 | 1.0 |
| Moving average | Mean return | 17,613 | fast 5, slow 250, long only | -2.24% | 0.9941 | 1.0 | 1.0 | 1.0 | 1.0 |
| Momentum | Sharpe ratio | 17,484 | lookback 273, long only | -0.04 | 0.9714 | 1.0 | 1.0 | 1.0 | 1.0 |
| Momentum | Mean return | 17,484 | lookback 273, long only | -3.50% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

**Deciding run, (iii) the eight ETFs.**

| Instrument | Grid | Criterion | Days | Best setting | Best difference, annualized | Reality Check | SPA lower | SPA consistent | SPA upper | Holm-adjusted |
|---|---|---|---|---|---|---|---|---|---|---|
| QQQ | Moving average | Sharpe ratio | 6,705 | fast 50, slow 200, long only | 0.21 | 0.4955 | 0.2934 | 0.3299 | 0.3299 | 1.0 |
| QQQ | Moving average | Mean return | 6,705 | fast 50, slow 200, long/short | 0.61% | 0.7517 | 0.5646 | 0.7348 | 0.7348 | 1.0 |
| QQQ | Momentum | Sharpe ratio | 6,576 | lookback 126, long only | 0.25 | 0.4204 | 0.2474 | 0.2751 | 0.2751 | 1.0 |
| QQQ | Momentum | Mean return | 6,576 | lookback 147, long only | -0.51% | 0.8201 | 1.0 | 1.0 | 1.0 | 1.0 |
| IWM | Moving average | Sharpe ratio | 6,397 | fast 15, slow 80, long only | 0.01 | 0.913 | 0.7369 | 0.9112 | 0.9122 | 1.0 |
| IWM | Moving average | Mean return | 6,397 | fast 15, slow 80, long only | -3.67% | 0.9883 | 1.0 | 1.0 | 1.0 | 1.0 |
| IWM | Momentum | Sharpe ratio | 6,268 | lookback 252, long only | -0.01 | 0.9072 | 1.0 | 1.0 | 1.0 | 1.0 |
| IWM | Momentum | Mean return | 6,268 | lookback 252, long only | -3.87% | 0.9868 | 1.0 | 1.0 | 1.0 | 1.0 |
| EFA | Moving average | Sharpe ratio | 6,082 | fast 10, slow 180, long only | 0.20 | 0.5477 | 0.3984 | 0.442 | 0.442 | 1.0 |
| EFA | Moving average | Mean return | 6,082 | fast 10, slow 180, long only | -1.06% | 0.8909 | 1.0 | 1.0 | 1.0 | 1.0 |
| EFA | Momentum | Sharpe ratio | 5,953 | lookback 147, long only | 0.17 | 0.5936 | 0.372 | 0.4951 | 0.4951 | 1.0 |
| EFA | Momentum | Mean return | 5,953 | lookback 147, long only | -1.85% | 0.9332 | 1.0 | 1.0 | 1.0 | 1.0 |
| EEM | Moving average | Sharpe ratio | 5,676 | fast 20, slow 60, long only | 0.13 | 0.6661 | 0.5226 | 0.6082 | 0.6082 | 1.0 |
| EEM | Moving average | Mean return | 5,676 | fast 20, slow 60, long only | -1.94% | 0.9265 | 1.0 | 1.0 | 1.0 | 1.0 |
| EEM | Momentum | Sharpe ratio | 5,547 | lookback 210, long only | 0.12 | 0.6674 | 0.4759 | 0.6006 | 0.6006 | 1.0 |
| EEM | Momentum | Mean return | 5,547 | lookback 210, long only | -1.82% | 0.9149 | 1.0 | 1.0 | 1.0 | 1.0 |
| TLT | Moving average | Sharpe ratio | 5,854 | fast 40, slow 60, long only | 0.15 | 0.6213 | 0.4188 | 0.4928 | 0.4928 | 1.0 |
| TLT | Moving average | Mean return | 5,854 | fast 40, slow 60, long/short | 1.25% | 0.7087 | 0.57 | 0.7087 | 0.7087 | 1.0 |
| TLT | Momentum | Sharpe ratio | 5,725 | lookback 42, long only | 0.04 | 0.8489 | 0.6586 | 0.84 | 0.8404 | 1.0 |
| TLT | Momentum | Mean return | 5,725 | lookback 42, long only | -0.56% | 0.92 | 1.0 | 1.0 | 1.0 | 1.0 |
| IEF | Moving average | Sharpe ratio | 5,854 | fast 10, slow 100, long only | 0.07 | 0.8016 | 0.607 | 0.7692 | 0.7697 | 1.0 |
| IEF | Moving average | Mean return | 5,854 | fast 10, slow 100, long only | -0.43% | 0.9504 | 1.0 | 1.0 | 1.0 | 1.0 |
| IEF | Momentum | Sharpe ratio | 5,725 | lookback 294, long only | 0.04 | 0.8243 | 0.6542 | 0.7857 | 0.7873 | 1.0 |
| IEF | Momentum | Mean return | 5,725 | lookback 357, long only | -0.26% | 0.9117 | 1.0 | 1.0 | 1.0 | 1.0 |
| SHY | Moving average | Sharpe ratio | 5,854 | fast 40, slow 250, long only | 0.17 | 0.5703 | 0.1275 | 0.1867 | 0.2081 | 1.0 |
| SHY | Moving average | Mean return | 5,854 | fast 40, slow 250, long/short | 0.07% | 0.805 | 0.4943 | 0.7189 | 0.7858 | 1.0 |
| SHY | Momentum | Sharpe ratio | 5,725 | lookback 378, long only | 0.26 | 0.3743 | 0.0237 | 0.029 | 0.0407 | 0.928 |
| SHY | Momentum | Mean return | 5,725 | lookback 378, long/short | 0.20% | 0.6445 | 0.2971 | 0.4462 | 0.6032 | 1.0 |
| GLD | Moving average | Sharpe ratio | 5,272 | fast 40, slow 120, long only | 0.11 | 0.7324 | 0.5501 | 0.6693 | 0.6702 | 1.0 |
| GLD | Moving average | Mean return | 5,272 | fast 25, slow 150, long only | -0.79% | 0.9198 | 1.0 | 1.0 | 1.0 | 1.0 |
| GLD | Momentum | Sharpe ratio | 5,143 | lookback 315, long only | 0.01 | 0.9016 | 0.7303 | 0.8919 | 0.8919 | 1.0 |
| GLD | Momentum | Mean return | 5,143 | lookback 315, long only | -0.77% | 0.942 | 1.0 | 1.0 | 1.0 | 1.0 |

**Mean block length.** SPA consistent p-values of the deciding families at mean block lengths of 5, 10, 20 and 50 days; 10 decides.

| Sample | Grid | Criterion | L = 5 | L = 10 | L = 20 | L = 50 |
|---|---|---|---|---|---|---|
| US market | Moving average | Sharpe ratio | 0.6692 | 0.6826 | 0.6914 | 0.6925 |
| US market | Moving average | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| US market | Momentum | Sharpe ratio | 1.0 | 1.0 | 1.0 | 1.0 |
| US market | Momentum | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| QQQ | Moving average | Sharpe ratio | 0.3405 | 0.3299 | 0.3421 | 0.3378 |
| QQQ | Moving average | Mean return | 0.7415 | 0.7348 | 0.7376 | 0.7322 |
| QQQ | Momentum | Sharpe ratio | 0.2822 | 0.2751 | 0.2574 | 0.2454 |
| QQQ | Momentum | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| IWM | Moving average | Sharpe ratio | 0.9042 | 0.9112 | 0.9256 | 0.9372 |
| IWM | Moving average | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| IWM | Momentum | Sharpe ratio | 1.0 | 1.0 | 1.0 | 1.0 |
| IWM | Momentum | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| EFA | Moving average | Sharpe ratio | 0.4516 | 0.442 | 0.4172 | 0.3978 |
| EFA | Moving average | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| EFA | Momentum | Sharpe ratio | 0.5132 | 0.4951 | 0.4702 | 0.4503 |
| EFA | Momentum | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| EEM | Moving average | Sharpe ratio | 0.6294 | 0.6082 | 0.5801 | 0.5656 |
| EEM | Moving average | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| EEM | Momentum | Sharpe ratio | 0.6065 | 0.6006 | 0.6001 | 0.5797 |
| EEM | Momentum | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| TLT | Moving average | Sharpe ratio | 0.5066 | 0.4928 | 0.4732 | 0.4284 |
| TLT | Moving average | Mean return | 0.7206 | 0.7087 | 0.704 | 0.6957 |
| TLT | Momentum | Sharpe ratio | 0.8425 | 0.84 | 0.8308 | 0.8228 |
| TLT | Momentum | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| IEF | Moving average | Sharpe ratio | 0.7775 | 0.7692 | 0.7623 | 0.7455 |
| IEF | Moving average | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| IEF | Momentum | Sharpe ratio | 0.7957 | 0.7857 | 0.7795 | 0.7805 |
| IEF | Momentum | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| SHY | Moving average | Sharpe ratio | 0.1676 | 0.1867 | 0.2112 | 0.2718 |
| SHY | Moving average | Mean return | 0.7311 | 0.7189 | 0.6953 | 0.6797 |
| SHY | Momentum | Sharpe ratio | 0.0233 | 0.029 | 0.0484 | 0.0918 |
| SHY | Momentum | Mean return | 0.4421 | 0.4462 | 0.4522 | 0.4331 |
| GLD | Moving average | Sharpe ratio | 0.6575 | 0.6693 | 0.6664 | 0.6417 |
| GLD | Moving average | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |
| GLD | Momentum | Sharpe ratio | 0.8804 | 0.8919 | 0.8941 | 0.9 |
| GLD | Momentum | Mean return | 1.0 | 1.0 | 1.0 | 1.0 |

**Variants of (ii).** SPA consistent p-values at L = 10. In the cash variant, capital not held in a position earns `RF`, short proceeds earn nothing, and Sharpe ratios are on returns in excess of `RF` (D046). The split at 1960-01-04, the first row of 1960, divides the deciding run's aligned days; signals carry across it.

| Variant | Days, moving average / momentum | Moving average, Sharpe ratio | Moving average, mean return | Momentum, Sharpe ratio | Momentum, mean return |
|---|---|---|---|---|---|
| 84 bps per side (deciding run) | 17,613 / 17,484 | 0.6826 | 1.0 | 1.0 | 1.0 |
| 0 bps | 17,613 / 17,484 | 0.0591 | 1.0 | 0.0442 | 1.0 |
| 6 bps | 17,613 / 17,484 | 0.0895 | 1.0 | 0.1361 | 1.0 |
| 25 bps | 17,613 / 17,484 | 0.2807 | 1.0 | 0.6048 | 1.0 |
| 50 bps | 17,613 / 17,484 | 0.455 | 1.0 | 0.789 | 1.0 |
| Cash earns `RF`, Sharpe ratios on excess returns | 17,613 / 17,484 | 0.6934 | 1.0 | 1.0 | 1.0 |
| Before 1960-01-04 | 9,291 / 9,162 | 0.5834 | 1.0 | 0.6172 | 1.0 |
| From 1960-01-04 | 8,322 / 8,322 | 1.0 | 1.0 | 1.0 | 1.0 |

The best setting's annualized difference in each variant, in Sharpe ratio or in percentage points a year:

| Variant | Days, moving average / momentum | Moving average, Sharpe ratio | Moving average, mean return | Momentum, Sharpe ratio | Momentum, mean return |
|---|---|---|---|---|---|
| 84 bps per side (deciding run) | 17,613 / 17,484 | 0.07 | -2.24% | -0.04 | -3.50% |
| 0 bps | 17,613 / 17,484 | 0.28 | -0.51% | 0.30 | -0.60% |
| 6 bps | 17,613 / 17,484 | 0.26 | -0.64% | 0.22 | -1.00% |
| 25 bps | 17,613 / 17,484 | 0.19 | -1.03% | 0.10 | -1.90% |
| 50 bps | 17,613 / 17,484 | 0.13 | -1.54% | 0.04 | -2.58% |
| Cash earns `RF`, Sharpe ratios on excess returns | 17,613 / 17,484 | 0.07 | -1.29% | -0.06 | -2.65% |
| Before 1960-01-04 | 9,291 / 9,162 | 0.15 | -1.17% | 0.12 | -1.55% |
| From 1960-01-04 | 8,322 / 8,322 | -0.04 | -2.73% | -0.20 | -4.46% |

**D021's selected settings.** Fast 10, slow 200, long only and lookback 273, long only, each tested alone against buy and hold by the SPA consistent p-value, which for one setting is a one-sided studentized bootstrap test.

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

**Post hoc: (i) SPY.** D021's results on SPY were known before D043, so this is not a registered test. It was rerun with D043's code over D021's sample, at 6 bps per side, with StepM at 0.05/4. D021's selected settings, tested alone, have SPA consistent p-values of 0.1065 (moving average) and 0.1158 (momentum) on the Sharpe ratio and 1.0 for both on the mean return.

| Grid | Criterion | Days | Best setting | Best difference, annualized | Reality Check | SPA lower | SPA consistent | SPA upper | Consistent, L = 5 | L = 20 | L = 50 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Moving average | Sharpe ratio | 8,247 | fast 10, slow 200, long only | 0.16 | 0.5705 | 0.3684 | 0.4495 | 0.4552 | 0.4533 | 0.4288 | 0.42 |
| Moving average | Mean return | 8,247 | fast 50, slow 250, long only | -1.17% | 0.9343 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| Momentum | Sharpe ratio | 8,118 | lookback 273, long only | 0.14 | 0.5784 | 0.3034 | 0.3934 | 0.4023 | 0.4 | 0.386 | 0.3943 |
| Momentum | Mean return | 8,118 | lookback 273, long only | -1.13% | 0.9291 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |

**Limits.**

- D043's rough critical difference, for orientation only: for a long-only setting whose daily returns correlate about 0.8 with buy and hold, with independent returns, a finding needs an annualized Sharpe difference of about 0.25 to 0.28 on (ii) and 0.45 to 0.55 on an ETF, so smaller true differences are unlikely to be found. Long/short settings have standard errors about 1.5 times larger.
- Before 1952, with about 280 to 300 rows a year, annualizing by 252 rows understates the figures of (ii): by up to about 9% for Sharpe differences, annualized by √252 (D043), and by up to about 19% for mean differences, annualized by 252.
- The cost of (ii) is a constant, the average one-way cost of trading NYSE stocks over 1925 to 2000 in Jones (2002); his text puts the cost below 0.50% in 1926 to 1928 and from 1991, and at 1.00% or more from 1953 to 1975.
- The grids hold conventional values, such as a 200-day average and a 12-month lookback, whose popularity owes something to long US histories that include 1926 to 1993; (ii) is unseen by these grids but not by the practice that chose such values.
- The tests assume stationary, weakly dependent returns, and for the Sharpe difference the studentization of the SPA and StepM rests on the delta method. Not being shown to beat buy and hold does not show that no setting does.

**Interpretation.** These comments decide nothing and do not qualify the sentences above.

- The best settings' annualized Sharpe differences in the deciding runs, 0.07 on (ii) and at most 0.26 on an ETF (SHY, momentum), are below D043's rough critical differences.
- On (ii) the SPA consistent p-values of the Sharpe difference rise with costs: 0.0591 (moving average) and 0.0442 (momentum) at 0 bps, 0.0895 and 0.1361 at 6 bps and 0.6826 and 1.0 at 84 bps, while the best Sharpe differences fall from 0.28 and 0.30 at 0 bps to 0.07 and -0.04 at 84 bps. The momentum value at 0 bps is the only SPA consistent p-value of (ii)'s variants at or below 0.05, before any correction for the 4 families; a run without costs is not a tradable result and decides nothing.
- In the sample, every setting of both grids has a lower mean return than buy and hold over (ii)'s days at each cost tested, from 0 to 84 bps, and from 1960 every setting is behind buy and hold in both Sharpe ratio and mean return. Before 1960 the best Sharpe differences are 0.15 and 0.12, with SPA consistent p-values of 0.5834 and 0.6172.
- The smallest p-value of (iii) before Holm, 0.029 for SHY's momentum grid on the Sharpe ratio, is the only one at or below 0.05 among the 32 families; Holm's first step multiplies it by 32, to 0.928. It is 0.0233 at L = 5, 0.0484 at L = 20 and 0.0918 at L = 50. In 12 of the 16 mean-return families of (iii) no setting is ahead of buy and hold over the sample.
- D021's selected settings, tested alone, have no SPA consistent p-value below 0.1465 on (ii) and (iii) (EFA, moving average, Sharpe ratio), and every one of their mean-return p-values is 1.0.

**Rerun.** The study needs the Fama/French zip and Yahoo prices for the eight ETFs and SPY in `data/`, which are not committed (D003):

```bash
uv run python -m backtest_lab.data.update     # prices, the eight ETFs and SPY included
uv run python -m backtest_lab.data.french     # the daily Fama/French 3 factors zip
uv run python -m backtest_lab.validation.relative --out /tmp/relative --posthoc-out /tmp/relative-posthoc
```

The runner stops unless the Fama/French rows before 1993-01-29 and the eight ETFs' rows match the digests registered in D043. Yahoo revises its adjusted prices (see the rerun above), so data fetched later can fail that check. Each family is cached in `data/cache/relative/` as soon as it is done, so an interrupted run resumes.

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

An in-sample winner that is always long-only ranks in the top half out of sample because the long/short half is worse, so the whole-grid PBO is low. Within the long-only half, picking the winner is not shown to beat chance. The best long-only setting still has a significant deflated Sharpe ratio within that half (about 1.00 for both, with 10.5 and 3.8 effectively independent settings).

Counting every setting of the grid, as METHODS.md Section 5 requires, the deflated Sharpe ratios of the same two settings are the registered 0.945 and 0.988; the values near 1.00 hold only when the long/short half is left out.

**Independent trials.** The registered reports estimate the independent trials from the average correlation. The eigenvalue estimate (METHODS.md Section 5) and the rule that DSR and MinBTL use the larger of the two were adopted afterwards (D041). `results/posthoc/effective_trials.json` holds both for a rerun of the three searches on prices fetched on 2026-11-10; it is fixed like the other post hoc file.

| | Moving average | Momentum | Random signal |
|---|---|---|---|
| Settings tried | 128 | 34 | 100 |
| Independent, average correlation (registered) | 47.9 | 14.0 | 100.0 |
| Independent, eigenvalues | 72.6 | 20.2 | 99.7 |
| DSR with each | 0.945 / 0.919 | 0.988 / 0.979 | 0.147 / 0.147 |
| MinBTL in years with each | 8.0 / 9.1 | 4.8 / 5.8 | 123.4 / 123.3 |

With the larger estimate every DSR and MinBTL verdict is the registered one, and no search falls under the floor of 10 independent trials below which PBO and DSR cannot pass. The long-only halves above are smaller: by the average correlation they have 10.5 and 3.8 independent settings. Their PBO values of 0.42 and 0.72 are red, and a fail counts under the floor as well; the momentum half's deflated Sharpe ratio of about 1.00 is the figure that would get no verdict.

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
