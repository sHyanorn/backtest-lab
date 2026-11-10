# Credibility Report

The credibility report is one JSON document per parameter search. It runs every check in `METHODS.md` on the stored trials, gives each a verdict and a one-sentence plain-language summary, and compares the selected trial with buy and hold. The API returns it and the dashboard renders it.

- Models: `src/backtest_lab/validation/report_schema.py` (pydantic)
- JSON Schema: [`report.schema.json`](report.schema.json), generated from the models; a test fails if the two differ. Regenerate with `uv run python -m backtest_lab.validation.report_schema > docs/report.schema.json`
- Builder: `backtest_lab.validation.report.build_report(trials, data, benchmark, settings)`. It raises when the trials share fewer days than `Settings.min_days`, 1,512 with the defaults (one walk-forward window)

## Conventions

- Sharpe ratios are annualized ($\sqrt{252}$ times daily) unless a field says otherwise, and every figure is computed on returns net of costs.
- `null` means undefined (a zero denominator, or a ratio that `METHODS.md` reports only for a positive denominator). The document never contains `NaN` or `Infinity`.
- Dates are ISO `YYYY-MM-DD`. Trial numbers index the grid in enumeration order, last axis fastest (D023).
- The same inputs give byte-identical JSON; there is no timestamp.
- `schema_version` changes whenever a field is added, removed or changes meaning.

## Top level

| Field | Content |
|---|---|
| `schema_version` | `"1.1"`. The registered demo reports are `"1.0"` (D032): one estimate of the independent trials, no `not_assessable` verdict (D041) |
| `strategy` | Registry name, fixed parameters, grid axes and their values, number of trials |
| `sample` | First and last date of the aligned trial returns, number of days, years ($T / 252$) |
| `costs` | Fees and slippage in basis points per side (D014) |
| `selected` | Trial with the highest Sharpe over the whole sample, its parameters and its Section 1 metrics |
| `benchmark` | Buy and hold of one instrument over the same dates through the engine with the same costs, its metrics, and `difference` = selected minus benchmark for Sharpe, CAGR, maximum drawdown and volatility. A reference only: it takes no part in any verdict (D021) |
| `overall` | `verdict`: the worst verdict among the checks, with a check that is not assessable counted as yellow. `summary`: which checks fail, are borderline or cannot be assessed. `benchmark_summary`: the comparison with buy and hold, kept apart because passing the checks says the result is unlikely to come from the search alone, not that it beats the market |
| `checks` | The eight checks below, always in this order |
| `series` | Weekly equity and drawdown of the selected trial and of the benchmark |

## Checks

Every check has `title`, `verdict` (`green`, `yellow` or `red`), `summary` and `metrics`; some also have `details` for charts. Thresholds are fixed in D022. `pbo` and `deflated_sharpe` have the verdict `not_assessable` when fewer than 10 trials are effectively independent by the smaller of the two estimates; their metrics are still reported (D041).

| Key | Method | Verdict | `details` |
|---|---|---|---|
| `holdout` | Section 2.1, first 70% IS | Retention rule on OOS/IS Sharpe | Fraction, selected trial and parameters |
| `walk_forward` | Section 2.2, rolling 1260/252 days | Retention rule on walk-forward efficiency, OOS return positive | Each window: dates, selected trial, IS and OOS Sharpe |
| `purged_cv` | Section 3, K = 10, h = ceil(0.01 T) | Retention rule on test/train Sharpe | Each fold: dates, training size, selected trial, train and test Sharpe |
| `pbo` | Section 4, S = 16 | Green up to 0.10, yellow up to 0.30, red above | Histogram of the logits: 20 equal bins on $[-\ln N, \ln N]$ |
| `deflated_sharpe` | Section 5 | Green from 0.95, yellow from 0.5, red below | none |
| `track_record` | Section 6, PSR(0) and MinTRL at $\alpha$ = 0.05 | Green from 0.95, yellow from 0.5, red below | none |
| `min_backtest_length` | Section 6, MinBTL with $\hat N$ | Green when the sample is at least MinBTL, else red | none |
| `sensitivity` | Section 7, radius 1 | Retention green from 0.75, yellow from 0.5, red below or when the best Sharpe is not positive; yellow when no ordered axis has more than one value | Heatmap |

Retention rule: green when the ratio is at least 0.5 and OOS performance is positive, yellow when the ratio is below 0.5 with positive OOS performance, red when OOS performance is not positive or the ratio is undefined.

`deflated_sharpe.metrics` gives the trials run (`n_trials`), the two estimates of the independent trials (`n_effective_correlation`, `n_effective_eigenvalue`) and the larger of them (`n_effective`), which DSR and MinBTL use.

Units worth noting: `deflated_sharpe.metrics.sharpe_variance` is the variance of the non-annualized Sharpe ratios across trials; `kurtosis` is raw (3 for normal returns); `walk_forward.metrics.is_return` and `oos_return` are annualized arithmetic returns ($252 \times$ mean); `track_record.metrics.min_track_record_years` and the MinBTL fields are in years.

### Heatmap

`sensitivity.details.heatmap` shows the annualized Sharpe over one or two ordered axes, by default the first two with more than one value, with every other parameter fixed at its value in the selected trial. `sharpe[y][x]` and `trials[y][x]` index the values of `y` and `x`; a one-axis heatmap has `y: null` and a single row. `best` is the selected trial's cell and `neighbours` lists the cells of its neighbourhood that lie in the slice. It is `null` when no ordered axis has more than one value.

## Series

Daily curves are downsampled to one point per calendar week to keep the file small, about 1,750 points for 33 years:

- `dates`: the last trading date of each week
- `equity`: wealth at that date, starting from 1 before the first date
- `drawdown`: the deepest daily drawdown within the week, so the chart keeps the maximum drawdown that a week-end sample would miss

Values are rounded to 6 decimal places. These series are derived from strategy returns; no raw prices are included (D003).
