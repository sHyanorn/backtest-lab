import { EquityChart, Legend, type Line } from '../charts/EquityChart.tsx'
import { settingText } from '../format.ts'
import type { Report } from '../report.gen.ts'
import { CheckCards } from './CheckCards.tsx'
import { Overview } from './Overview.tsx'
import { Sensitivity } from './Sensitivity.tsx'

export function ReportView({
  report,
  title,
  kind,
}: {
  report: Report
  title: string
  kind: string
}) {
  const lines: Line[] = [
    {
      label: settingText(report.selected.params, report.strategy.grid),
      short: 'Selected',
      color: 'var(--series-1)',
      wash: 'var(--series-1-wash)',
      ...report.series.selected,
    },
    {
      label: report.benchmark.name,
      short: report.benchmark.name.replace(/ buy and hold$/, ''),
      color: 'var(--series-ref)',
      wash: 'var(--series-ref-wash)',
      ...report.series.benchmark,
    },
  ]
  return (
    <>
      <Overview report={report} title={title} kind={kind} />
      <section className="panel" aria-labelledby="equity-title">
        <div className="panel-head">
          <h2 className="panel-title" id="equity-title">
            Equity and drawdown
          </h2>
          <Legend lines={lines} />
        </div>
        <EquityChart
          dates={report.series.dates}
          lines={lines}
          label="Weekly equity on a log scale and drawdown of the selected setting and buy and hold"
        />
      </section>
      <CheckCards report={report} />
      <Sensitivity report={report} />
    </>
  )
}
