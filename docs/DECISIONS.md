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
- See also D032: the workflow never regenerates the registered demo results

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

## D016 API scope and data
- Date: 2026-11-08
- The API is for local use. It has no authentication, so it is started with `--host 127.0.0.1` and must not be exposed to the internet; the public demo is the static dashboard (D002)
- At startup it loads every ticker and macro series in the local cache (a few MB). A request uses only the tickers it trades, plus the benchmark for a sweep, on the dates where at least one of them has a price, as if only those had been loaded; a date range then slices them. Macro series stay whole because strategies read them by publication date (D010). Without a cache, data endpoints return 503 and name the update command
- Requests reject unknown fields. Parameters are checked against the strategy's dataclass fields before any work: a value must have the field's type (an integer is accepted for a float), numbers must lie within +/-1,000,000, the strategy's own range checks apply, and each string parameter must name a ticker or a macro series in the cache, as its field declares. Failures return 422. Responses and reports state every parameter, defaults included. Costs default to D014 and must be non-negative
- Dependencies: fastapi and uvicorn at run time, httpx2 for the test client, which Starlette now requires in place of httpx
- See also D039

## D017 Parameter sweeps through the API
- Date: 2026-11-08
- A sweep is checked completely before it is queued: parameters as in D016, the grid (D023), at most 500 trials, a benchmark ticker (by default the strategy's first ticker parameter when it is not an axis), and the sample length. The report settings are fixed at their defaults (D022, D024); a request cannot shorten the windows, so every report is judged on the same terms
- Length check: the number of dates in the range on which every traded ticker has a price, less one and less the longest warm-up in the grid, must reach `Settings.min_days` (1,512), or the request gets 422 with the estimate. The benchmark does not count, since buy and hold is flat before it lists. The estimate is an upper bound: publication lags can shorten the aligned sample further, and such a sweep fails when the report is built, with the same explanation
- One sweep runs at a time on a background thread. Its grid search uses a process pool, by default `min(CPUs available, 4)` workers (`BACKTEST_LAB_PROCESSES` overrides it), with the platform's start method: spawn on Windows and under `uvicorn --reload`, forkserver otherwise on Linux. At most 10 sweeps wait; further requests get 429
- Stopping the server, including a `--reload` restart or Ctrl+C, cancels the running sweep: its workers are terminated rather than left to finish, workers ignore Ctrl+C so the server decides, and unfinished sweeps are marked failed
- Memory: CSCV holds several 12,870 x N matrices; with T = 8,000 and S = 16 its peak was 73 MB for N = 100, 346 MB for 500, 687 MB for 1,000 and 1,370 MB for 2,000, about 0.7 MB per trial. Each worker holds its own copy of the data and engine buffers, about 140 MB. A 500-trial sweep with four workers peaked at 607 MB for the server process (224 MB idle) on SPY since 1993 and 706 MB on JNJ since 1962, plus the workers while trials run. The largest pre-registered grid has 128 trials
- Errors in a sweep: an expected limit (a `ValueError`, such as too few aligned days) is returned as its message; any other error is returned as its type only, with the traceback in the server log, so responses carry no local paths

## D018 Sweep state in SQLite
- Date: 2026-11-08
- Each sweep is a row in `data/jobs/jobs.sqlite3` (status, progress, timestamps, selected trial and verdict), and its results are files in `data/jobs/<id>/`: the trial matrix (D023) and `report.json`, which the report endpoint returns byte for byte. Ids are random UUIDs generated by the server; any other id is 404 before it is looked up or reaches a path
- Rationale: `uvicorn --reload` restarts the process on every code change, which would lose finished results kept in memory. SQLite is in the standard library and handles the single writer
- After a stop or restart, finished sweeps can still be read; sweeps that were queued or running are marked failed and are not rerun. One server per data directory: a second server, or `--workers` above 1, would mark the other's running sweeps failed when it starts
- Nothing is deleted automatically. A 500-trial sweep stores about 41 MB for 34 years of SPY and 76 MB for 64 years. To clean up, stop the server and delete `data/jobs/`, or one `data/jobs/<id>/` directory together with its row

## D019 Categorical numeric grid axes
- Date: 2026-11-08
- A grid can list numeric axes as categorical, such as a random seed. Their values need not be ordered, and sensitivity compares a trial only with neighbours along ordered axes, so a categorical axis never supplies neighbours
- `trials.json` writes the list only when it is not empty, so files saved before this change load unchanged. The pre-registered demo (D021) keeps its configuration, in which `seed` is an ordered axis
- Rationale: adjacent seeds are unrelated, so treating them as neighbours gives a sensitivity verdict with no meaning

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
- See also D037

## D023 Grid search and stored trials
- Date: 2026-11-08
- A grid is rectangular: every combination of its axis values, enumerated with the last axis fastest, and the trial number is the position in that order. Numeric axes must be strictly increasing so that sensitivity neighbours are adjacent values; bool and string axes are categorical. A grid with any invalid combination is rejected before work starts
- Trials run in a process pool. Each trial is a deterministic backtest of its parameters, and results are collected in grid order, so the output is identical for any number of processes. Market data and costs reach each worker once through the pool initializer, which works under the spawn start method used on Windows
- Storage is one directory per search: `returns.parquet` (T x N net daily returns from the first date all trials are live, one column per trial) and `trials.json` (strategy, grid, costs, sample dates and each trial's parameters and first live date). The API can keep one directory per job; the dashboard reads the report instead of the matrix
- Strategies are looked up by name in a registry, so stored trials and worker jobs carry a name, not a class

## D024 Holdout and walk-forward defaults
- Date: 2026-11-08
- Holdout: the first 70% of the aligned rows are IS. Walk-forward: rolling windows of 1260 IS days (five years) and 252 OOS days (one year), which gives about 27 OOS windows on the demo sample
- The selected trials' target weights are stitched by OOS day, each taken from the close before that day, and run through the engine once. The first OOS window enters from cash, so it pays the entry cost; later windows pay only for parameter switches
- Rationale: no published default exists. Five years spans more than one market regime and yearly re-optimization is a common schedule; both were fixed before any real-data run (D021)

## D025 Purged K-fold settings
- Date: 2026-11-08
- K = 10 contiguous folds and embargo h = ceil(0.01 T), computed in integer arithmetic so that floating-point error cannot add a day
- Each row of the trial matrix is one daily return with information interval [t - 1, t]: the target is decided at close t - 1 and the return is marked to close t (D013). The span is a constant of the engine, `INFORMATION_SPAN`, which purged K-fold reads. With closed intervals each test fold loses one training row before it, and training resumes h + 1 rows after it
- In each fold the best trial is selected by Sharpe on the training rows taken together, which are not contiguous when the test fold is inside the sample. The CV score is the mean annualized test-fold Sharpe; a fold where the selected trial is flat counts as 0
- Rationale: ten folds of the demo sample are over three years each, long enough for a test-fold Sharpe ratio to mean something
- See also D036

## D026 Normal distribution from the standard library
- Date: 2026-11-08
- PSR, DSR, MinTRL and MinBTL need only the standard normal CDF and its inverse, taken from `statistics.NormalDist` (the inverse is Wichura's AS241 algorithm, accurate to double precision). Skewness and raw kurtosis are population moments computed with numpy, the definitions `scipy.stats.skew` and `scipy.stats.kurtosis(fisher=False)` use (METHODS.md, Conventions); a test checks them against pandas' bias-corrected estimates after converting those back
- Rationale: scipy would be a large dependency for two functions. The paper examples reproduce to the stated precision without it
- The average pairwise correlation skips degenerate trials and is 0 when fewer than two trials remain, so N-hat falls back to N, the conservative side

## D027 Random-signal control
- Date: 2026-11-08
- The control strategy is fully long or short one instrument, with the direction drawn at random every `hold` days from `default_rng(seed)`; a grid over seeds is a search with no skill by construction. Directions are drawn in date order, so a shorter sample gives a prefix of the same signal and there is no look-ahead
- Besides the matrix controls in METHODS.md, a test runs 50 seeds with `hold` 5 through the grid search and the engine on synthetic random-walk prices. Calibrated over 40 price paths, PBO had mean 0.487 and standard deviation 0.165, and the deflated Sharpe ratio of the best trial never exceeded 0.62. The test requires the mean PBO over 10 paths to lie in [0.33, 0.67], about three standard errors around 0.5, and every DSR to stay below 0.95
- Rationale: checks the whole pipeline, including costs and the engine's fills, against the property SPEC Section 8 states

## D028 Report format
- Date: 2026-11-08
- The report is defined by pydantic 2.14.3 models, and `docs/report.schema.json` is generated from them; a test keeps the committed schema in step. The API will use the same models as response types, and the dashboard can generate its types from the schema
- Undefined values are `null`; the models reject NaN and infinity, so a missing conversion fails loudly instead of producing invalid JSON. There is no timestamp, so the same inputs give the same bytes
- Equity and drawdown are weekly: equity at each week's last date and the deepest daily drawdown within the week, so the maximum drawdown survives downsampling. Values are rounded to 6 decimals
- Sensitivity needs an ordered axis with more than one value. A grid without one has no neighbourhood; its sensitivity check is yellow ("cannot be assessed"), the one case D022 does not cover. All pre-registered grids have such an axis (D021)
- Rationale: one source of truth for the format across the Python code, the API and the dashboard
- See also D033: the dashboard's types are generated from this schema
- See also D037

## D029 Demo conclusions follow the pre-registered results
- Date: 2026-11-08
- The demo story (SPEC.md Section 3) is told from the pre-registered results in `results/demo/`, produced with the configuration and thresholds of D021 and D022, which stay unchanged
- Analyses designed after seeing those results (the long-only half of each grid, the CSCV winners, the comparison with buy and hold in its deepest drawdowns) live in `backtest_lab.validation.posthoc` and `results/posthoc/`, and every place that shows them labels them post hoc (docs/DEMO.md)
- Rationale: choosing which subset or statistic to show after seeing the results is itself a selection, the effect this project measures. Labelling keeps confirmatory and exploratory evidence apart

## D030 Dashboard charts drawn as SVG with d3-scale and d3-shape
- Date: 2026-11-08
- The dashboard draws four chart forms: equity on a log scale with drawdown below it, columns (sensitivity over one axis, walk-forward windows, purged CV folds, the PBO logit histogram), a heat grid over two axes, and range bars. Each is a small React component on d3-scale and d3-shape; colours are CSS variables, so both themes come from one stylesheet
- Measured as the gzipped size of a minimal line chart bundled with esbuild: ECharts 6 with tree-shaken imports 176 kB, Recharts 3 71 kB, visx xychart 45 kB, uPlot 23 kB (canvas, no heat map), d3-scale with d3-shape 16 kB
- Every chart is keyboard focusable with a spoken readout and has a data table next to it. Verdicts pair a status colour with an icon and a word; the heat grid uses one blue ramp, or blue and red around zero when Sharpe ratios change sign

## D031 Static and local modes of the dashboard
- Date: 2026-11-08
- The production build, deployed to GitHub Pages, reads only the committed reports: Vite emits `results/demo/*.json` and `results/posthoc/long_only.json` as hashed assets and the page fetches them, so nothing is copied or regenerated
- The dev server (`npm run dev`) proxies `/api` to the local FastAPI service on 127.0.0.1:8000 (D016). When it answers, a Custom sweep view submits a sweep, polls its progress and renders the report with the same components. The view is loaded only when `import.meta.env.DEV` is true, so the static build contains no API code
- Costs default to D014 in the form. A report with both costs at zero is labelled a zero-cost reference in its header and verdict panel
- Rationale: the public demo stays free and needs no server (D002); custom searches remain possible for anyone who runs the project locally

## D032 The demo results stay frozen; the weekly workflow only updates data
- Date: 2026-11-08
- `results/demo` holds the reports produced once with the configuration of D021. They are not regenerated, by the weekly workflow or by hand; CI checks them against `results/demo/SHA256SUMS`, and the post hoc file the documents quote against `results/posthoc/SHA256SUMS`. The weekly `data` workflow (D012) fetches and checks data only
- Rationale: rerunning on newer data changes the sample, and so the numbers, after the conclusions were drawn from them. A pre-registered result has to stay the one that was registered; an analysis of newer data would be a new, separately labelled result
- Not done: a weekly rerun over the registered dates to detect revisions in Yahoo's history. It would need the raw data that is not committed (D003), and a difference would only say that the data changed

## D033 Dashboard types generated from the report schema
- Date: 2026-11-08
- `web/src/report.gen.ts` is generated from `docs/report.schema.json` with json-schema-to-typescript (`npm run gen:types`), and CI fails if the committed file differs. The loader accepts only `schema_version` 1.0 and checks the top-level sections before rendering
- Post hoc results have no schema (D029), so their type is written by hand and the loader requires `post_hoc: true`
- Rationale: one source of truth for the report format across the Python models, the API and the dashboard (D028)

## D034 Dashboard deployed to GitHub Pages by Actions
- Date: 2026-11-08
- The `pages` workflow builds `web/` with the base path `/<repository>/` and deploys it with `actions/upload-pages-artifact` and `actions/deploy-pages` after the `ci` workflow succeeds on a push to `main`, so a pushed commit that fails the tests, the browser checks or the frozen-results check (D032) is not deployed. A manual run deploys the branch it is started on without waiting for CI. The repository's Pages source must be set to GitHub Actions
- Views are addressed by the URL hash (`#/momentum`), so a static host needs no rewrite rules for links into the dashboard
- Rationale: GitHub Pages is free and serves the static build directly (D002); deploying from Actions keeps build output out of the repository

## D035 PBO estimator and the paper's Definition 2.2
- Date: 2026-11-08
- The code counts a combination as overfit when its logit is at most 0, the estimator ∫ f(λ) dλ over λ ≤ 0 of Bailey et al. (2017, Section 3.1). Their Definition 2.2 writes PBO with r̄ < N/2. Since ω̄ = r̄ / (N + 1), λ ≤ 0 means r̄ ≤ (N + 1) / 2, so for even N the two also differ at rank N/2 (λ = ln(N / (N + 2)) < 0): the estimator counts it and Definition 2.2 does not. Under the null that rank has probability 1/N. The statement in METHODS.md Section 4 that the two differ only at λ = 0 holds for odd N only
- A rerun of the registered searches reproduces the registered counts of 607, 1,590 and 3,853 of 12,870 combinations for the moving average, momentum and the random-signal control. Under Definition 2.2 the same trial matrices give 585, 1,393 and 3,748 (PBO 0.045, 0.108 and 0.291), with every verdict the same. The registered reports keep the estimator

## D036 Information interval of a daily return
- Date: 2026-11-08
- The return of row t spans the prices from close t - 1 to close t. Its overnight leg is earned by the position set from the target at close t - 2, its intraday leg by the target set at close t - 1 (D013). `INFORMATION_SPAN = 1` describes that price span: t0 in METHODS.md Section 3 is the first close of the return interval. The older target is a feature of the row, like a trailing indicator window, and the embargo is what covers features
- So the last in-sample and first out-of-sample returns share the target from close e - 2, which is set before the selection at close e - 1 and leaks nothing; and the span is a constant of the engine pinned by a test, not a value derived from engine settings
- On a rerun of the registered searches, a span of 2 makes the random-signal search select trial 51 instead of 55 in fold 4 and moves its CV Sharpe ratio from -0.331 to -0.326; the moving-average and momentum folds do not change. Every verdict is the same

## D037 Sensitivity without neighbours when the best Sharpe ratio is not positive
- Date: 2026-11-08
- D022 makes the sensitivity check red when the best Sharpe ratio is not positive, and D028 makes it yellow when the grid has no neighbourhood. When both hold, the check is yellow: the code tests for neighbours first
- The overall verdict is red in that case anyway: the selected trial is the best one, and MinBTL is red whenever its Sharpe ratio is not positive. All registered grids have neighbours

## D038 Stale-open warning
- Date: 2026-11-08
- A bar whose open equals the previous bar's close and also the day's high or low, each within the 1e-6 relative tolerance of D011, probably has a stale open: a fill there is a fill at the close that formed the signal (D013). The check changes no data and gives one warning per ticker with the number of such bars, the first and last of them and their count by decade
- Measured on Yahoo data on 2026-11-08 (bars to 2026-11-06): XOM 1,340, JNJ 1,255, JPM 674, AAPL 461, SHY 249, MSFT 201, SPY 24, EEM 17, IWM 13, AMZN 10, IEF 9, EFA 8, TLT 5, GLD 4, QQQ 3. Before 1990 the stocks' opens repeat the previous close wholesale (XOM and JNJ about 900 each from 1962 to 1979), a property of Yahoo's early data. SHY's 207 since 2010 are mostly genuine: its price often does not move from one day to the next
- Rationale: one warning per bar would bury the other warnings in thousands of entries. The registered demo is not rerun; how its verdicts respond to SPY's stale opens is in DEMO.md (post hoc)

## D039 Sweep dates come from the traded tickers
- Date: 2026-11-08
- A sweep runs on the dates where at least one traded ticker has a price, the dates `/api/backtests` uses for the same parameters. The benchmark is a column on those dates and adds none of its own. This replaces D016's rule that a sweep also keeps the benchmark's dates
- Rationale: with the benchmark's dates kept, a bar missing from the traded ticker became a NaN row, and each rolling indicator stayed NaN for a full window after it, so the strategy sat flat for up to `slow` or `lookback` days without an error and the sweep disagreed with `/api/backtests`. A benchmark missing a bar on a traded date now fails the sweep with the engine's message. The registered demo trades and benchmarks SPY only and is unaffected
