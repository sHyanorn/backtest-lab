import { InfoTip } from '../InfoTip.tsx'
import {
  costText,
  count,
  date,
  num,
  pct,
  settingText,
  signed,
} from '../format.ts'
import type { Report } from '../report.gen.ts'
import { checkViews, VERDICT_LABEL } from './checks.ts'
import { Verdict, VerdictIcon } from './Verdict.tsx'

export function Overview({
  report,
  title,
  kind,
}: {
  report: Report
  title: string
  kind: string
}) {
  const { strategy, sample, costs, selected, overall } = report
  const zeroCost = costs.fee_bps === 0 && costs.slippage_bps === 0
  return (
    <>
      <header className="overview">
        <h1>{title}</h1>
        <p className="meta">
          <span className="tag">{kind}</span>
          <span>{count(strategy.n_trials)} settings</span>
          <span>
            {date(sample.start)} to {date(sample.end)}
          </span>
          <span className={zeroCost ? 'cost zero' : 'cost'}>
            {zeroCost ? 'Zero-cost reference' : `Net of ${costText(costs)}`}
          </span>
        </p>
      </header>
      <div className="verdicts">
        <section className="panel verdict-panel" aria-labelledby="checks-title">
          <div className="panel-head">
            <h2 className="panel-title" id="checks-title">
              Overfitting checks
            </h2>
          </div>
          <p className="overall">
            <Verdict verdict={overall.verdict} size={22} />
          </p>
          {zeroCost && (
            <p className="zero-note cost zero">
              Costs are off: read this as a reference only.
            </p>
          )}
          <p className="overall-summary">{overall.summary}</p>
          <ul className="strip" aria-label="Verdict of each check">
            {checkViews(report.checks).map((c) => (
              <li key={c.key}>
                <a
                  href={`#check-${c.key}`}
                  title={`${c.title}: ${VERDICT_LABEL[c.verdict]}`}
                  onClick={(e) => {
                    e.preventDefault()
                    document
                      .getElementById(`check-${c.key}`)
                      ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                    document
                      .getElementById(`check-${c.key}`)
                      ?.focus({ preventScroll: true })
                  }}
                >
                  <VerdictIcon verdict={c.verdict} size={18} />
                  <span className="visually-hidden">
                    {c.title}: {VERDICT_LABEL[c.verdict]}
                  </span>
                </a>
              </li>
            ))}
          </ul>
          <p className="selected">
            <span className="muted">Selected</span>{' '}
            {settingText(selected.params, strategy.grid)}
            <span className="muted"> · trial {selected.trial}</span>
          </p>
        </section>
        <Benchmark report={report} />
      </div>
    </>
  )
}

function Benchmark({ report }: { report: Report }) {
  const s = report.selected.metrics
  const b = report.benchmark.metrics
  const d = report.benchmark.difference
  const pp = (v: number | null) =>
    v === null ? 'n/a' : `${signed(num(v * 100, 1))} pp`
  const rows = [
    ['Sharpe ratio', num(s.sharpe), num(b.sharpe), signed(num(d.sharpe))],
    ['CAGR', pct(s.cagr), pct(b.cagr), pp(d.cagr)],
    [
      'Max drawdown',
      pct(s.max_drawdown),
      pct(b.max_drawdown),
      pp(d.max_drawdown),
    ],
    [
      'Volatility',
      pct(s.annual_volatility),
      pct(b.annual_volatility),
      pp(d.annual_volatility),
    ],
  ]
  return (
    <section className="panel" aria-labelledby="benchmark-title">
      <div className="panel-head">
        <h2 className="panel-title" id="benchmark-title">
          Against {report.benchmark.name}
        </h2>
        <span className="tag">Not part of the verdict</span>
        <InfoTip label="Why the benchmark is separate" align="end">
          {report.overall.benchmark_summary}
        </InfoTip>
      </div>
      <table className="compare diff">
        <thead>
          <tr>
            <th scope="col">
              <span className="visually-hidden">Metric</span>
            </th>
            <th scope="col">Selected</th>
            <th scope="col">Buy and hold</th>
            <th scope="col">Difference</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([name, ...values]) => (
            <tr key={name}>
              <th scope="row">{name}</th>
              {values.map((v, i) => (
                <td key={i}>{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
