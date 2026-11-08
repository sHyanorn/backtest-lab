# Technical Decisions

## D001 Python for the engine, React for the dashboard
- Date: 2026-11-04
- Rationale: Python has a mature data and statistics ecosystem; the dashboard reuses front-end skills

## D002 Precomputed results for the public demo
- Date: 2026-11-04
- Rationale: GitHub Pages is free and stable, and visitors see results as soon as they open the page; avoids exposing a public server to abuse

## D003 Raw data is not committed
- Date: 2026-11-04
- Rationale: Data source terms usually prohibit redistribution; keeps the repository lightweight

## D004 Vectorized engine first
- Date: 2026-11-04
- Rationale: Parameter search needs a large number of backtests, and vectorization is much faster; an event-driven version is an optional point of comparison

## D005 Python 3.14
- Date: 2026-11-07
- Rationale: numpy, pandas, pyarrow, scipy and duckdb all ship 3.14 wheels; 3.15 is still in beta and 3.12 only receives security fixes

## D006 Prices from yfinance, adjusted and unadjusted
- Date: 2026-11-07
- Rationale: Stooq CSV downloads have required a captcha-issued key since early 2026 (pandas-datareader issue #1012), which cannot run in CI. yfinance is called with `auto_adjust=False`; `Close` is split-adjusted and `Adj Close` also adjusts for dividends. Both are stored so adjustment consistency can be checked. Yahoo terms restrict redistribution, so raw data is not committed (D003)

## D007 FRED via fredgraph CSV, no API key
- Date: 2026-11-07
- Rationale: `fredgraph.csv?id=<series>` serves full history without a key, so neither CI nor local runs need secrets. The project has no secrets, so there is no `.env.example`

## D008 empyrical-reloaded for metric cross-checks
- Date: 2026-11-07
- Rationale: Maintained, small dependency footprint, works with pandas 3 on Python 3.14. quantstats gives the same values but pulls in plotting libraries. Used as a dev dependency only

## D009 Instrument universe
- Date: 2026-11-07
- ETFs: SPY, QQQ, IWM, EFA, EEM, TLT, IEF, SHY, GLD. Stocks: AAPL, MSFT, AMZN, JPM, XOM, JNJ. Macro: DGS10, DGS3MO, DFF, CPIAUCSL, UNRATE
- Rationale: Liquid instruments with long histories across equities, bonds and gold; the stocks span several sectors
- Limitation: the stocks were picked because they exist today and have long histories, which is survivorship bias. Results on them overstate what a strategy would have earned. The demo story uses the ETFs

## D010 Macro publication lag and revisions
- Date: 2026-11-07
- FRED dates are observation periods, so each value gets an `available_date`: daily rates (DGS10, DGS3MO, DFF) the next Federal Reserve business day, after the H.15 release (the Fed is closed on some days the stock market is open, such as Veterans Day); a monthly value (CPIAUCSL, UNRATE) for month M at the end of M+1. A signal generated after the close of day t and filled at the next open may use values whose `available_date` is on or before t
- Checked against ALFRED vintages at every month-end from 1998 to 2026: each monthly value was published by the end of M+1 except UNRATE for September 2025, delayed by the government shutdown to 2025-11-20, which is hard-coded. October 2025 was never published for either series
- Limitation: fredgraph serves the latest revised values, so even with the lag a backtest sees revised numbers. Measured against ALFRED vintages at 84 quarter-ends from 2005 to 2025, the first-release value differed from today's by a mean of 0.048 pp (max 0.20 pp) for UNRATE and 0.030 pp (max 0.13 pp) for CPI year-over-year inflation. Treasury and fed funds rates are not revised. The rotation strategy conditions on rates only, so this does not affect it; using CPI or UNRATE as signals would need ALFRED vintages

## D011 Data quality thresholds
- Date: 2026-11-07
- Errors (the update fails): missing or non-positive prices; open or close outside low-high by more than 1e-6 relative; a ticker whose last bar is older than the latest bar of any ticker; adjustment factor `Adj Close / Close` changing by more than 1e-5 on a day without a dividend, or its step on an ex-dividend day differing from `1 - D / Close[t-1]` by more than 1e-5. Across the full histories of the universe the largest factor deviation is 2.5e-6, so the tolerance leaves a 4x margin. A dividend step right after a missing bar cannot be checked and is a warning
- Warnings (logged for review): a daily log return whose robust z-score (median and 1.4826 x MAD) exceeds 10; a missing bar on a date when at least half of the tickers trading at the time have one; a macro series whose last observation is more than 7 days (daily) or 75 days (monthly) older than the latest price date. Over the universe a z-score of 10 flags 105 days in total, all real market events (1987, 2008, March 2020); a lower threshold would bury them in noise. Macro staleness is a warning because releases can legitimately pause, as in late 2025
- Basis: measured on Yahoo data on 2026-11-07

## D012 Weekly data update
- Date: 2026-11-07
- The `data` workflow runs on Saturdays and on demand. It fetches into an Actions cache, runs the quality checks and uploads the report. It fails if any fetch fails or any check errors, and only a successful run saves the cache. Nothing is committed and raw data is not uploaded (D003)
- GitHub evicts caches unused for 7 days, so a weekly run may refetch everything. A full fetch is one history request per ticker for 15 tickers, 1 s apart, plus 5 FRED downloads; it takes about 25 s. Each request retries 4 times with 2 to 16 s backoff before the run fails
- The incremental update refetches a ticker in full only when the last 10 cached rows change; a correction to an older dividend is picked up by the next full fetch (a cache miss, or `--full`)
- GitHub disables scheduled workflows after 60 days without repository activity; it has to be re-enabled from the Actions tab

## D013 Fills at the next open
- Date: 2026-11-08
- Target weights are decided at the close of day t and traded at the open of t+1. The return of t+1 is `(1 + overnight)(1 + intraday) - 1`: the previous positions, drifted with prices, earn the gap from close t to open t+1; the portfolio is then rebalanced to the target and earns open to close. Trading costs (D014) are taken at the open, between the two legs
- The portfolio is rebalanced to its targets every day, so it trades a little every day as prices drift. Only a single asset held at weight +1 does not drift; a short or partial position is resized as its price moves (a constant -1 short in SPY trades about 4 times a year, roughly 24 bps a year at default costs)
- Opens are adjusted with the same day's `Adj Close / Close` factor. Back-adjustment rescales all prices before a later dividend by one constant, so signals must be scale-invariant functions of prices (returns, ratios, crossovers, z-scores) to stay free of look-ahead
- Rationale: matches the hard rule that a signal fills no earlier than t+1, and the one-day information interval assumed in METHODS.md Section 3. Filling at the next close would add a day of delay for no extra realism

## D014 Transaction costs
- Date: 2026-11-08
- Costs are proportional to traded notional, `rate = (fee_bps + slippage_bps) / 1e4`, with defaults of 1 bp fees and 5 bps slippage per side. They are on by default; a zero-cost run is only a reference
- Turnover at an open is the sum of `|target - drifted weight|`, so building a position from cash costs `rate x gross exposure` and daily rebalancing of a multi-asset portfolio pays for its drift (D013)
- Rationale: commissions on liquid US ETFs and large caps are near zero; 5 bps covers the half-spread and impact at the open with room to spare

## D015 Cash, shorting and leverage
- Date: 2026-11-08
- Uninvested capital and short proceeds earn zero, consistent with `r_f = 0` in METHODS.md. Shorts pay no borrow fee. Gross exposure is capped at 1 by default
- A day that loses 100% or more ends the backtest: its return is -1 and later returns are 0
- Limitation: ignoring interest on cash understates the returns of strategies that are often flat when rates are high

## D020 Metrics return NaN in degenerate cases
- Date: 2026-11-08
- A standard deviation or downside deviation below 1e-12 counts as zero, and a ratio with a zero denominator is NaN; CAGR is NaN when final wealth is not positive (METHODS.md, Conventions and Section 1)
- empyrical-reloaded returns `inf`, or a large value from float noise in the standard deviation, for constant or all-positive series. An infinite Sharpe would rank first in parameter search and PBO, so the project uses NaN and treats it as Sharpe 0 in rankings. Cross-checks against empyrical (D008) cover non-degenerate series only

## D021 Pre-registered demo
- Date: 2026-11-08
- Fixed before any strategy was run on real data. Instrument SPY, sample 1993-01-29 to 2026-10-30, default costs (D014)
- Moving-average crossover: `fast` in {5, 10, 15, 20, 25, 30, 40, 50}, `slow` in {60, 80, 100, 120, 150, 180, 200, 250}, `allow_short` in {false, true}: 128 trials
- Robust comparison: time-series momentum, `lookback` in {42, 63, ..., 378} (step 21, 17 values), `allow_short` in {false, true}: 34 trials
- Random-signal control: random direction on SPY, `seed` 0 to 99, `hold` 5 days: 100 trials
- Settings: holdout f = 0.7; walk-forward rolling, IS 1260 and OOS 252 days; purged K-fold K = 10, h = ceil(0.01 T); CSCV S = 16; sensitivity radius 1, heatmap over (`fast`, `slow`) and over `lookback` for momentum
- Benchmark: SPY buy and hold on the same dates, a constant weight of 1 through the engine with default costs. The report gives its Sharpe, CAGR, maximum drawdown and volatility and the selected trial's differences from them. It is a reference only: it takes no part in any verdict and changes no test in METHODS.md
- Rationale: with r_f = 0 (D015) and the equity premium, a long-biased SPY strategy can look significant by holding the market. Passing the checks says the result is unlikely to come from the parameter search alone; beating buy and hold is a separate question, and the report keeps the two apart
- Expected in advance: both strategies may pass PSR and DSR because of the equity premium, and momentum may show a high PBO because its configurations have similar skill (METHODS.md Section 4). The configuration is not changed after the results are seen

## D022 Credibility report verdicts
- Date: 2026-11-08
- Retention (holdout OOS/IS Sharpe, walk-forward efficiency, purged CV test/train Sharpe): green when the ratio is at least 0.5 and OOS performance is positive; yellow when the ratio is below 0.5 and OOS is positive; red when OOS is not positive or the ratio is undefined. Basis: 50% is the commonly cited acceptance level for walk-forward efficiency (Pardo, 2008; the book text was not checked, see METHODS.md Section 2.2)
- PBO: green up to 0.10, yellow up to 0.30, red above. Green follows the paper's remark on investors sensitive to PBO below 1/10. Red is set from the null: for X = 0.01 `default_rng(seed).standard_normal((1000, 100))`, S = 16 and seeds 0 to 199, PBO had mean 0.488, standard deviation 0.153 and 5/10/25/50% quantiles 0.236/0.296/0.372/0.476; 89.5% of seeds were above 0.30, so a search with no skill is red about nine times in ten
- DSR and PSR(0): green from 0.95, yellow from 0.5, red below. A DSR below 0.5 means the selected Sharpe is below the expected best of N̂ skill-less trials
- MinBTL: red when the sample is shorter than MinBTL or the selected Sharpe is not positive, otherwise green. It is a necessary condition only, so there is no middle band
- Sensitivity retention: green from 0.75, yellow from 0.5, red below 0.5 or when the best Sharpe is not positive. A project convention; there is no published threshold
- Overall: the worst verdict among the checks
- Rationale: fixed before any real-data run so the thresholds cannot be fitted to the demo
