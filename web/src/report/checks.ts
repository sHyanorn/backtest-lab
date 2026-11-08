import { count, num, pct, years } from '../format.ts'
import type { Checks, Verdict } from '../report.gen.ts'

export type CheckKey = keyof Checks

export const VERDICT_LABEL: Record<Verdict, string> = {
  green: 'Pass',
  yellow: 'Borderline',
  red: 'Fail',
}

export interface CheckView {
  key: CheckKey
  title: string
  verdict: Verdict
  summary: string
  value: string
  measure: string
  context: string
  rule: string
}

const RETENTION_RULE =
  'Pass when out-of-sample performance is positive and keeps at least half of in-sample; borderline below half; fail when it is not positive.'

/** The headline number of each check and the rule that judges it (D022). */
export function checkViews(checks: Checks): CheckView[] {
  const c = checks
  const base = <K extends CheckKey>(key: K) => ({
    key,
    title: c[key].title,
    verdict: c[key].verdict,
    summary: c[key].summary,
  })
  return [
    {
      ...base('holdout'),
      value: pct(c.holdout.metrics.retention, 0),
      measure: 'OOS / IS Sharpe',
      context: `${num(c.holdout.metrics.is_sharpe)} → ${num(c.holdout.metrics.oos_sharpe)}`,
      rule: RETENTION_RULE,
    },
    {
      ...base('walk_forward'),
      value: pct(c.walk_forward.metrics.efficiency, 0),
      measure: 'Walk-forward efficiency',
      context: `OOS Sharpe ${num(c.walk_forward.metrics.oos_sharpe)} · ${c.walk_forward.metrics.n_windows} windows`,
      rule: RETENTION_RULE,
    },
    {
      ...base('purged_cv'),
      value: pct(c.purged_cv.metrics.retention, 0),
      measure: 'Test / train Sharpe',
      context: `${num(c.purged_cv.metrics.cv_sharpe)} vs ${num(c.purged_cv.metrics.train_sharpe)} · ${c.purged_cv.metrics.folds} folds`,
      rule: RETENTION_RULE,
    },
    {
      ...base('pbo'),
      value: num(c.pbo.metrics.pbo, 3),
      measure: 'PBO',
      context: `${count(c.pbo.metrics.n_combinations)} splits`,
      rule: 'Pass up to 0.10, borderline up to 0.30, fail above. A search with no skill lands near 0.5.',
    },
    {
      ...base('deflated_sharpe'),
      value: num(c.deflated_sharpe.metrics.dsr, 3),
      measure: 'DSR',
      context: `Sharpe ${num(c.deflated_sharpe.metrics.sharpe)} vs ${num(c.deflated_sharpe.metrics.expected_max_sharpe)} by luck`,
      rule: 'Pass from 0.95, borderline from 0.50, fail below. Below 0.50 the selected Sharpe ratio is under the best expected from skill-less trials.',
    },
    {
      ...base('track_record'),
      value: num(c.track_record.metrics.psr, 3),
      measure: 'PSR',
      context: `${years(c.track_record.metrics.min_track_record_years)} needed of ${years(c.track_record.metrics.years)}`,
      rule: 'Pass from 0.95, borderline from 0.50, fail below. It ignores how many settings were tried.',
    },
    {
      ...base('min_backtest_length'),
      value: years(c.min_backtest_length.metrics.min_backtest_years),
      measure: 'Needed for this Sharpe ratio',
      context: `${years(c.min_backtest_length.metrics.years)} available`,
      rule: 'Pass when the sample is at least this long and the selected Sharpe ratio is positive; otherwise fail.',
    },
    {
      ...base('sensitivity'),
      value: pct(c.sensitivity.metrics.retention, 0),
      measure: 'Kept by neighbours',
      context: `${c.sensitivity.metrics.n_neighbours} neighbouring settings`,
      rule: 'Pass when neighbouring settings keep at least 75% of the best Sharpe ratio, borderline from 50%, fail below or when the best is not positive.',
    },
  ]
}
