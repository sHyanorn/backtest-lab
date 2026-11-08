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
- FRED dates are observation periods, so each value gets an `available_date`: daily rates (DGS10, DGS3MO, DFF) the next Federal Reserve business day, after the H.15 release (the Fed is closed on some days the stock market is open, such as Veterans Day); a monthly value (CPIAUCSL, UNRATE) for month M at the end of M+1. Strategies may only read values whose `available_date` has passed
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

## D020 Metrics return NaN in degenerate cases
- Date: 2026-11-08
- A standard deviation or downside deviation below 1e-12 counts as zero, and a ratio with a zero denominator is NaN; CAGR is NaN when final wealth is not positive (METHODS.md, Conventions and Section 1)
- empyrical-reloaded returns `inf`, or a large value from float noise in the standard deviation, for constant or all-positive series. An infinite Sharpe would rank first in parameter search and PBO, so the project uses NaN and treats it as Sharpe 0 in rankings. Cross-checks against empyrical (D008) cover non-degenerate series only

## D013 Fills at the next open
- Date: 2026-11-08
- Target weights are decided at the close of day t and traded at the open of t+1. The return of t+1 is `(1 + overnight)(1 + intraday) - 1`: the previous positions, drifted with prices, earn the gap from close t to open t+1; the portfolio is then rebalanced to the target and earns open to close. Trading costs (D014) are taken at the open, between the two legs
- The portfolio is rebalanced to its targets every day, so a multi-asset portfolio trades a little every day as prices drift. A single fully invested asset does not drift and trades only when its target changes
- Opens are adjusted with the same day's `Adj Close / Close` factor. Back-adjustment rescales all prices before a later dividend by one constant, so signals must be scale-invariant functions of prices (returns, ratios, crossovers, z-scores) to stay free of look-ahead
- Rationale: matches the hard rule that a signal fills no earlier than t+1, and the one-day information interval assumed in METHODS.md Section 3. Filling at the next close would add a day of delay for no extra realism

## D015 Cash, shorting and leverage
- Date: 2026-11-08
- Uninvested capital and short proceeds earn zero, consistent with `r_f = 0` in METHODS.md. Shorts pay no borrow fee. Gross exposure is capped at 1 by default
- A day that loses 100% or more ends the backtest: its return is -1 and later returns are 0
- Limitation: ignoring interest on cash understates the returns of strategies that are often flat when rates are high
