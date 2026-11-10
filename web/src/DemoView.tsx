import { DEMOS, loadDemo, loadPostHoc, type DemoKey } from './data.ts'
import { strategyTitle } from './format.ts'
import { PostHoc } from './report/PostHoc.tsx'
import { ReportView } from './report/ReportView.tsx'
import { useAsync } from './useAsync.ts'

export function DemoView({ demo }: { demo: DemoKey }) {
  const report = useAsync(demo, () => loadDemo(demo))
  if (report.status === 'error') {
    return (
      <div className="view">
        <div className="error" role="alert">
          Could not load the results: {report.error?.message}{' '}
          <button type="button" className="text-button" onClick={report.retry}>
            Retry
          </button>
        </div>
      </div>
    )
  }
  if (!report.value) return <div className="view" aria-busy="true" />
  // While the next search loads, the previous one stays on screen, dimmed.
  const shown = report.value
  const ticker = String(shown.strategy.fixed.ticker ?? '')
  const shownKey = DEMOS.find((d) => d.key === report.valueKey)?.key
  return (
    <div className="view" aria-busy={report.valueKey !== demo}>
      <ReportView
        report={shown}
        title={`${strategyTitle(shown.strategy.name)} on ${ticker}`}
        kind="Pre-registered"
      />
      {shownKey && <PostHocFor demo={shownKey} benchmark={ticker} />}
    </div>
  )
}

function PostHocFor({ demo, benchmark }: { demo: DemoKey; benchmark: string }) {
  const postHoc = useAsync('posthoc', loadPostHoc)
  const search = postHoc.value?.searches[demo]
  return search ? <PostHoc search={search} benchmark={benchmark} /> : null
}
