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
