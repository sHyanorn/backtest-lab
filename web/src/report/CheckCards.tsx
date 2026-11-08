import { InfoTip } from '../InfoTip.tsx'
import type { Report } from '../report.gen.ts'
import { checkViews } from './checks.ts'
import { Verdict } from './Verdict.tsx'

export function CheckCards({ report }: { report: Report }) {
  const heatmap = report.checks.sensitivity.details.heatmap
  const seedAxis = heatmap?.x.name === 'seed' || heatmap?.y?.name === 'seed'
  return (
    <section aria-labelledby="cards-title">
      <h2 className="section-title" id="cards-title">
        Checks
      </h2>
      <ol className="cards">
        {checkViews(report.checks).map((c) => (
          <li key={c.key} className="card" id={`check-${c.key}`} tabIndex={-1}>
            <div className="card-head">
              <Verdict verdict={c.verdict} />
              <InfoTip label={`How ${c.title} is judged`} align="end">
                {c.rule}
                {c.key === 'sensitivity' && seedAxis && (
                  <>
                    {' '}
                    Neighbouring seeds are unrelated, so this verdict carries no
                    information about the control.
                  </>
                )}
              </InfoTip>
            </div>
            <h3 className="card-title">{c.title}</h3>
            <p className="figure">
              <span className="figure-value">{c.value}</span>
              <span className="figure-measure">{c.measure}</span>
            </p>
            <p className="figure-context">{c.context}</p>
            <p className="card-summary">{c.summary}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
