import { EquityChart, Legend, type Line } from './charts/EquityChart.tsx'
import {
  DEMOS,
  loadDemo,
  loadPostHoc,
  type DemoKey,
  type Report,
} from './data.ts'
import { settingText, strategyTitle } from './format.ts'
import { CheckCards } from './report/CheckCards.tsx'
import { Overview } from './report/Overview.tsx'
import { PostHoc } from './report/PostHoc.tsx'
import { Sensitivity } from './report/Sensitivity.tsx'
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
  // While the next search loads, the previous one stays on screen, dimmed.
  const shown = report.value
  const meta = DEMOS.find((d) => d.key === shown.strategy.name)
  const ticker = String(shown.strategy.fixed.ticker ?? '')
  return (
    <div className="view" aria-busy={report.status === 'loading'}>
      <ReportView
        report={shown}
        title={`${strategyTitle(shown.strategy.name)} on ${ticker}`}
      />
      {meta && <PostHocFor demo={meta.key} benchmark={ticker} />}
    </div>
  )
}

function PostHocFor({ demo, benchmark }: { demo: DemoKey; benchmark: string }) {
  const postHoc = useAsync('posthoc', loadPostHoc)
  const search = postHoc.value?.searches[demo]
  return search ? <PostHoc search={search} benchmark={benchmark} /> : null
}

export function ReportView({
  report,
  title,
}: {
  report: Report
  title: string
}) {
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
    <>
      <Overview report={report} title={title} />
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
