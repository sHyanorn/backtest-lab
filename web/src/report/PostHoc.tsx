import { scaleLinear } from 'd3-scale'
import { useWidth } from '../charts/useWidth.ts'
import { InfoTip } from '../InfoTip.tsx'
import type { PostHocSearch } from '../data.ts'
import { count, date, num, pct, prob } from '../format.ts'

/** Analyses chosen after seeing the registered results (docs/DEMO.md, D029). */
export function PostHoc({
  search,
  benchmark,
}: {
  search: PostHocSearch
  benchmark: string
}) {
  const {
    annual_sharpe_range: range,
    cscv,
    pbo,
    long_only_half_dsr: dsr,
  } = search
  const winners = Math.round(cscv.long_only_winner_share * cscv.combinations)
  return (
    <section className="posthoc" aria-labelledby="posthoc-title">
      <div className="posthoc-head">
        <h2 className="section-title" id="posthoc-title">
          Post hoc
        </h2>
        <span className="tag">Not pre-registered</span>
        <InfoTip label="Why this analysis is post hoc">
          These questions were chosen after seeing the pre-registered results,
          to explain them. Restricting a grid to the half that won is a choice
          made knowing the outcome, so these numbers are exploratory and carry
          no confirmatory weight.
        </InfoTip>
      </div>
      <div className="posthoc-grid">
        <section className="panel" aria-labelledby="posthoc-sides">
          <h3 className="panel-title" id="posthoc-sides">
            Long only against long/short
          </h3>
          <RangeBars
            rows={[
              { label: 'Long only', range: range.long_only, tone: 'accent' },
              { label: 'Long/short', range: range.long_short, tone: 'ref' },
            ]}
          />
          <p className="note">
            The in-sample winner is long only in {count(winners)} of{' '}
            {count(cscv.combinations)} splits.
          </p>
        </section>
        <section className="panel" aria-labelledby="posthoc-pbo">
          <h3 className="panel-title" id="posthoc-pbo">
            PBO within the long-only half
          </h3>
          <dl className="pair">
            <div>
              <dt>Whole grid, registered</dt>
              <dd>{num(pbo.full_grid, 2)}</dd>
            </div>
            <div>
              <dt>Long-only half</dt>
              <dd>{num(pbo.long_only_half, 2)}</dd>
            </div>
          </dl>
          <p className="note">
            Deflated Sharpe ratio of the best long-only setting {prob(dsr.dsr)},
            with about {num(dsr.n_effective, 1)} independent settings of{' '}
            {dsr.n_trials}.
          </p>
        </section>
        <section className="panel" aria-labelledby="posthoc-drawdowns">
          <h3 className="panel-title" id="posthoc-drawdowns">
            Deepest {benchmark} drawdowns
          </h3>
          <table className="compare">
            <thead>
              <tr>
                <th scope="col">Peak to trough</th>
                <th scope="col">Buy and hold</th>
                <th scope="col">Selected</th>
              </tr>
            </thead>
            <tbody>
              {search.benchmark_drawdowns.map((d) => (
                <tr key={d.peak}>
                  <th scope="row">
                    {date(d.peak).replace(/ \d+,/, '')} to{' '}
                    {date(d.trough).replace(/ \d+,/, '')}
                  </th>
                  <td>{pct(d.benchmark_return)}</td>
                  <td>{pct(d.selected_return)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="note">
            In the market {pct(search.selected_profile.time_in_market, 0)} of
            days; mean return {pct(search.selected_profile.annual_mean_return)}{' '}
            against {pct(search.benchmark_profile.annual_mean_return)}.
          </p>
        </section>
      </div>
    </section>
  )
}

interface RangeRow {
  label: string
  range: [number, number]
  tone: 'accent' | 'ref'
}

/** Each row's Sharpe range across its settings on one shared axis. */
function RangeBars({ rows }: { rows: RangeRow[] }) {
  const [ref, width] = useWidth<HTMLDivElement>(320)
  const left = 96
  const right = 12
  const rowHeight = 40
  const high = Math.max(...rows.map((r) => r.range[1]))
  const x = scaleLinear()
    .domain([Math.min(0, ...rows.map((r) => r.range[0])), high])
    .nice(4)
    .range([left, Math.max(width - right, left + 10)])
  const height = rows.length * rowHeight + 38
  return (
    <div className="chart" ref={ref}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={rows
          .map(
            (r) =>
              `${r.label}: Sharpe ${num(r.range[0])} to ${num(r.range[1])}`,
          )
          .join('; ')}
      >
        {x.ticks(4).map((t) => (
          <g key={t} className="tick" transform={`translate(${x(t)},0)`}>
            <line y1={4} y2={rows.length * rowHeight} />
            <text y={rows.length * rowHeight + 16} textAnchor="middle">
              {num(t, 1)}
            </text>
          </g>
        ))}
        <text
          className="axis-label"
          x={(left + Math.max(width - right, left + 10)) / 2}
          y={rows.length * rowHeight + 34}
          textAnchor="middle"
        >
          Annualized Sharpe ratio
        </text>
        {rows.map((r, i) => {
          const cy = i * rowHeight + rowHeight / 2 + 2
          return (
            <g key={r.label}>
              <text className="range-label" x={0} y={cy - 7}>
                {r.label}
              </text>
              <text className="range-values" x={0} y={cy + 9}>
                {num(r.range[0])} to {num(r.range[1])}
              </text>
              <rect
                className={`range ${r.tone}`}
                x={x(r.range[0])}
                y={cy - 5}
                width={Math.max(x(r.range[1]) - x(r.range[0]), 2)}
                height={10}
                rx={5}
              />
            </g>
          )
        })}
      </svg>
    </div>
  )
}
