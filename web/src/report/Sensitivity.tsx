import { Columns, type Column } from '../charts/Columns.tsx'
import { HeatGrid, HeatLegend } from '../charts/HeatGrid.tsx'
import { num, paramText, pct } from '../format.ts'
import type { Report } from '../report.gen.ts'
import { Verdict } from './Verdict.tsx'

const sharpe = (v: number) => num(v)

export function Sensitivity({ report }: { report: Report }) {
  const check = report.checks.sensitivity
  const heatmap = check.details.heatmap
  const params = report.selected.params
  const axes = heatmap ? [heatmap.x.name, heatmap.y?.name] : []
  const held = Object.keys(report.strategy.grid)
    .filter((name) => !axes.includes(name))
    .map((name) => paramText(name, params[name] ?? ''))

  return (
    <section
      className="panel"
      id="sensitivity"
      tabIndex={-1}
      aria-labelledby="sensitivity-title"
    >
      <div className="panel-head">
        <h2 className="panel-title" id="sensitivity-title">
          Sharpe ratio across settings
        </h2>
        <Verdict verdict={check.verdict} />
        {held.length > 0 && <span className="tag">{held.join(' · ')}</span>}
      </div>
      <dl className="facts stats">
        <div>
          <dt>Best Sharpe ratio</dt>
          <dd>{num(check.metrics.best_sharpe)}</dd>
        </div>
        <div>
          <dt>Neighbour mean</dt>
          <dd>{num(check.metrics.neighbour_mean)}</dd>
        </div>
        <div>
          <dt>Neighbour spread</dt>
          <dd>{num(check.metrics.neighbour_std)}</dd>
        </div>
        <div>
          <dt>Kept by neighbours</dt>
          <dd>{pct(check.metrics.retention, 0)}</dd>
        </div>
      </dl>
      {heatmap === null ? (
        <p className="note">No ordered axis with more than one value.</p>
      ) : heatmap.y ? (
        <>
          <HeatLegend
            values={heatmap.sharpe
              .flat()
              .filter((v): v is number => v !== null)}
            format={sharpe}
          />
          <HeatGrid
            heatmap={heatmap}
            format={sharpe}
            label={`Annualized Sharpe ratio by ${heatmap.x.name} and ${heatmap.y.name}`}
            describe={(x, y) =>
              `${paramText(heatmap.x.name, heatmap.x.values[x] ?? '')} · ${paramText(heatmap.y?.name ?? '', heatmap.y?.values[y] ?? '')}`
            }
          />
        </>
      ) : (
        <>
          <ul className="legend start">
            <li>
              <span className="key-box accent" />
              Selected
            </li>
            <li>
              <span className="key-box soft" />
              Neighbours
            </li>
            <li>
              <span className="key-box ref" />
              Other settings
            </li>
          </ul>
          <Columns
            label={`Annualized Sharpe ratio by ${heatmap.x.name}`}
            format={sharpe}
            columns={heatmap.x.values.map((v, i): Column => ({
              label: String(v),
              value: heatmap.sharpe[0]?.[i] ?? null,
              detail: paramText(heatmap.x.name, v),
              tone:
                i === heatmap.best.x
                  ? 'accent'
                  : heatmap.neighbours.some((n) => n.x === i)
                    ? 'soft'
                    : 'ref',
            }))}
          />
          <p className="axis-caption">{heatmap.x.name.replace(/_/g, ' ')}</p>
        </>
      )}
      {heatmap && <SharpeTable heatmap={heatmap} />}
    </section>
  )
}

function SharpeTable({
  heatmap,
}: {
  heatmap: NonNullable<Report['checks']['sensitivity']['details']['heatmap']>
}) {
  const rows = heatmap.y
    ? heatmap.y.values.map((v, y) => ({
        name: String(v),
        cells: heatmap.sharpe[y] ?? [],
      }))
    : heatmap.x.values.map((v, x) => ({
        name: String(v),
        cells: [heatmap.sharpe[0]?.[x] ?? null],
      }))
  const columns = heatmap.y ? heatmap.x.values.map(String) : ['Sharpe']
  return (
    <details className="table-toggle">
      <summary>Table</summary>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">
                {heatmap.y
                  ? `${heatmap.y.name} \\ ${heatmap.x.name}`
                  : heatmap.x.name}
              </th>
              {columns.map((c) => (
                <th scope="col" key={c}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(heatmap.y ? [...rows].reverse() : rows).map((r) => (
              <tr key={r.name}>
                <th scope="row">{r.name}</th>
                {r.cells.map((v, i) => (
                  <td key={i}>{num(v)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
