# Tasks

## M0 Setup
- [x] Initialize a Python 3.14 project with uv; configure ruff, mypy strict mode and pytest
- [x] Package structure `src/backtest_lab/{data,engine,strategies,validation,api}`
- [x] CI: lint, type checking, tests

## M1 Data layer
- [x] Price data fetching (yfinance) with retries and caching
- [x] FRED macro data fetching
- [x] Parquet storage and DuckDB query wrapper
- [x] Data quality checks with a report
- [x] Weekly update via GitHub Actions

## M2 Backtest engine
- [x] Vectorized engine: signals fill with a one-day delay
- [ ] Transaction costs and slippage
- [ ] Performance metrics, cross-checked against existing libraries
- [ ] Look-ahead bias detection test
- [ ] Four example strategies

## M3 Anti-overfitting methods
- [x] Complete METHODS.md
- [ ] Parameter grid search (multiprocess), recording all trials
- [ ] In-sample/out-of-sample split and walk-forward analysis
- [ ] Purged and embargoed K-fold
- [ ] Combinatorially symmetric cross-validation (CSCV) and PBO
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
