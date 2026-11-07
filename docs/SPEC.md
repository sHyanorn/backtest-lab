# backtest-lab Specification

## 1. One-line summary

A backtesting platform that tells you "this strategy is probably overfit": beyond standard backtests, it uses walk-forward analysis, purged cross-validation, the probability of backtest overfitting and the deflated Sharpe ratio to assess whether a strategy can be trusted.

## 2. Capabilities demonstrated

| Capability | Where it shows |
|---|---|
| Algorithm development | Backtest engine, combinatorial purged cross-validation, parameter search |
| Finance and statistics | Multiple testing problem, deflated Sharpe ratio, probability of backtest overfitting |
| Data engineering | Scheduled fetching, cleaning, Parquet and DuckDB storage, data quality checks |
| Backend and frontend | FastAPI endpoints, React dashboard |

## 3. Core story (how to tell it in a demo)

1. Run a parameter grid search on a moving-average strategy and find a combination with a very high in-sample Sharpe ratio
2. The platform tests it with several methods and concludes: the probability of overfitting is high and the deflated Sharpe ratio is not significant
3. Compare with a strategy whose parameters are robust: it passes
4. Takeaway: try a few hundred parameter sets and you can always "find" a good strategy; this platform can detect that

## 4. Scope

### Required

- Data layer
  - Daily prices: US equity index ETFs and several large-cap stocks, sourced from yfinance
  - Macro data: FRED (interest rates, inflation, unemployment) via the keyless fredgraph CSV download
  - Stored as Parquet, queried with DuckDB
  - Data quality checks: missing values, abnormal jumps, price adjustment consistency
  - GitHub Actions updates the data weekly and regenerates the demo results
- Backtest engine
  - Daily frequency, multi-asset, long and short
  - Transaction costs (proportional to traded value) and slippage
  - Outputs: equity curve, drawdown, turnover, annualized return, volatility, Sharpe, Sortino, maximum drawdown, Calmar
- Example strategies: moving-average crossover, time-series momentum, mean reversion, interest-rate-conditioned asset rotation (using macro data)
- Parameter search: grid search, recording every trial result (a prerequisite for multiple testing corrections)
- Anti-overfitting tests (see Section 5)
- One-page "credibility report": the result of each test, a red/yellow/green verdict, and a plain-language explanation
- React dashboard: choose a strategy and parameter ranges, view the equity curve and drawdown, parameter sensitivity heatmap, credibility report

### Optional

- Event-driven engine (results compared against the vectorized engine)
- Custom strategy upload (sandboxed execution)
- Monte Carlo resampling of the return series

### Out of scope

- Live trading
- Minute-level data

## 5. Anti-overfitting methods (project focus)

| Method | Question it answers | Reference |
|---|---|---|
| In-sample/out-of-sample split | Does out-of-sample performance get markedly worse? | Basic method |
| Walk-forward analysis | With parameters re-optimized periodically, how does rolling out-of-sample performance look? | Pardo (2008) |
| Purged and embargoed K-fold cross-validation | Removes information leakage between the training and test sets | López de Prado (2018) |
| Combinatorial purged cross-validation and probability of backtest overfitting (PBO) | Probability that the in-sample optimal parameters rank in the bottom half out of sample | Bailey, Borwein, López de Prado, Zhu (2017) |
| Deflated Sharpe ratio (DSR) | After accounting for the number of trials, skewness and kurtosis, is the Sharpe ratio still significant? | Bailey & López de Prado (2014) |
| Parameter sensitivity | Do the optimal parameters sit on a plateau or an isolated peak? | Heatmap |
| Minimum backtest length | How much data is needed to support this Sharpe ratio? | Bailey & López de Prado (2012) |

All formulas go in `docs/METHODS.md`, written before implementation.

## 6. Architecture

```
GitHub Actions (weekly)
   │
   ▼
data/update ──▶ Parquet + DuckDB ──▶ engine ──▶ validation ──▶ precomputed results JSON
                                        ▲                          │
                                        │                          ▼
                               FastAPI (on-demand)  ◀──────  React dashboard
```

Deployment:

- Public demo: the dashboard reads precomputed JSON and is deployed to GitHub Pages, with zero server cost
- Full local version: FastAPI computes results in real time for custom parameters

## 7. API (FastAPI)

| Method | Path | Description |
|---|---|---|
| GET | `/api/strategies` | Strategy list and parameter definitions |
| POST | `/api/backtests` | Single backtest |
| POST | `/api/sweeps` | Parameter search; returns a job id |
| GET | `/api/sweeps/{id}` | Progress and results |
| GET | `/api/sweeps/{id}/report` | Credibility report |

Parameter searches run in parallel across multiple processes; job state is kept in memory or SQLite.

## 8. Testing strategy

- Engine: small hand-calculated examples; a look-ahead bias test (shuffle future data; results must not change)
- Metrics: compare against empyrical-reloaded
- Validation methods: use numerical examples from the papers; for a purely random-signal strategy, PBO should be close to or above 0.5 and DSR should not be significant
- Data: simulate missing values and jumps, and check that the quality checks flag them

## 9. Deliverables

- Public dashboard on GitHub Pages
- Demo notebook: tells the story from Section 3
- `docs/METHODS.md` methods documentation
- English README: one-line summary, dashboard screenshot, core story, methods table
