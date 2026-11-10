import { num, pct, prob, years } from '../format.ts'
import type { CheckVerdict, Checks } from '../report.gen.ts'

export type CheckKey = keyof Checks

export const VERDICT_LABEL: Record<CheckVerdict, string> = {
  green: 'Pass',
  yellow: 'Borderline',
  red: 'Fail',
  not_assessable: 'Not assessable',
}

/** Checks whose details open in a dialog; sensitivity has its own section. */
export const HAS_DETAILS: CheckKey[] = [
  'holdout',
  'walk_forward',
  'purged_cv',
  'pbo',
]

export interface CheckView {
  key: CheckKey
  title: string
  verdict: CheckVerdict
  summary: string
  value: string
  measure: string
  rule: string
}

const TOO_FEW_RULE =
  'Not assessed when fewer than 10 independent settings were tried.'

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
  // A figure that is not judged is not shown as a headline (D041).
  const judged = (key: CheckKey, value: string) =>
    c[key].verdict === 'not_assessable' ? '–' : value
  return [
    {
      ...base('holdout'),
      value: pct(c.holdout.metrics.retention, 0),
      measure: 'OOS / IS Sharpe',
      rule: RETENTION_RULE,
    },
    {
      ...base('walk_forward'),
      value: pct(c.walk_forward.metrics.efficiency, 0),
      measure: 'Walk-forward efficiency',
      rule: RETENTION_RULE,
    },
    {
      ...base('purged_cv'),
      value: pct(c.purged_cv.metrics.retention, 0),
      measure: 'Test / train Sharpe',
      rule: RETENTION_RULE,
    },
    {
      ...base('pbo'),
      value: judged('pbo', num(c.pbo.metrics.pbo, 3)),
      measure: 'PBO',
      rule: `Pass up to 0.10, borderline up to 0.30, fail above. A search with no skill lands near 0.5. ${TOO_FEW_RULE}`,
    },
    {
      ...base('deflated_sharpe'),
      value: judged('deflated_sharpe', prob(c.deflated_sharpe.metrics.dsr)),
      measure: 'DSR',
      rule: `Pass from 0.95, borderline from 0.50, fail below. Below 0.50 the selected Sharpe ratio is under the best expected from skill-less trials. ${TOO_FEW_RULE}`,
    },
    {
      ...base('track_record'),
      value: prob(c.track_record.metrics.psr),
      measure: 'PSR',
      rule: 'Pass from 0.95, borderline from 0.50, fail below. It ignores how many settings were tried.',
    },
    {
      ...base('min_backtest_length'),
      value: years(c.min_backtest_length.metrics.min_backtest_years),
      measure: 'Needed for this Sharpe ratio',
      rule: 'Pass when the sample is at least this long and the selected Sharpe ratio is positive; otherwise fail.',
    },
    {
      ...base('sensitivity'),
      value: pct(c.sensitivity.metrics.retention, 0),
      measure: 'Kept by neighbours',
      rule: 'Pass when neighbouring settings keep at least 75% of the best Sharpe ratio, borderline from 50%, fail below or when the best is not positive.',
    },
  ]
}
