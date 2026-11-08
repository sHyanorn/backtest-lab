import { EquityChart, Legend, type Line } from './charts/EquityChart.tsx'
import { loadDemo, type DemoKey, type Report } from './data.ts'
import { settingText } from './format.ts'
import { useAsync } from './useAsync.ts'

export function DemoView({ demo }: { demo: DemoKey }) {
  const report = useAsync(demo, () => loadDemo(demo))
  if (report.status === 'error' && !report.value) {
    return (
      <p className="error" role="alert">
        Could not load the results: {report.error.message}
      </p>
    )
  }
  if (!report.value) return <div className="view" aria-busy="true" />
  return (
    <div className="view" aria-busy={report.status === 'loading'}>
      <ReportView report={report.value} />
    </div>
  )
}

export function ReportView({ report }: { report: Report }) {
  const lines: Line[] = [
    {
      label: settingText(report.selected.params, report.strategy.grid),
      color: 'var(--series-1)',
      wash: 'var(--series-1-wash)',
      ...report.series.selected,
    },
    {
      label: report.benchmark.name,
      color: 'var(--series-ref)',
      wash: 'var(--series-ref-wash)',
      ...report.series.benchmark,
    },
  ]
  return (
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
  )
}
