# Tasks

## M0 Setup
- [ ] Initialize a Python 3.12 project with uv; configure ruff, mypy strict mode and pytest
- [ ] Package structure `src/backtest_lab/{data,engine,strategies,validation,api}`
- [ ] CI: lint, type checking, tests
- [ ] `.env.example` (FRED_API_KEY)

## M1 Data layer
- [ ] Price data fetching (yfinance or Stooq) with retries and caching
- [ ] FRED macro data fetching
- [ ] Parquet storage and DuckDB query wrapper
- [ ] Data quality checks with a report
- [ ] Weekly update via GitHub Actions

## M2 Backtest engine
- [ ] Vectorized engine: signals fill with a one-day delay
- [ ] Transaction costs and slippage
- [ ] Performance metrics, cross-checked against existing libraries
- [ ] Look-ahead bias detection test
- [ ] Four example strategies

## M3 Anti-overfitting methods
- [ ] Complete METHODS.md for Aaron's review
- [ ] Parameter grid search (multiprocess), recording all trials
- [ ] In-sample/out-of-sample split and walk-forward analysis
- [ ] Purged and embargoed K-fold
- [ ] Combinatorial purged cross-validation and PBO
- [ ] Deflated Sharpe ratio, probabilistic Sharpe ratio, minimum backtest length
- [ ] Parameter sensitivity analysis
- [ ] Control test with a random-signal strategy
- [ ] Credibility report generation (JSON)

## M4 API
- [ ] FastAPI endpoints
- [ ] Background jobs for parameter search, with progress queries
- [ ] API tests

## M5 Dashboard
- [ ] Vite + React + TypeScript setup
- [ ] Strategy selection and parameter settings
- [ ] Equity and drawdown charts, heatmap, credibility report cards
- [ ] Static mode: read precomputed JSON
- [ ] Deploy to GitHub Pages

## M6 Presentation
- [ ] Demo notebook tells the core story
- [ ] English README and screenshots
- [ ] Tidy up DECISIONS.md
