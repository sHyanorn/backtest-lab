import { Columns, type Column } from '../charts/Columns.tsx'
import { HeatGrid, HeatLegend } from '../charts/HeatGrid.tsx'
import { num, paramText, pct } from '../format.ts'
import type { Report } from '../report.gen.ts'
import { Verdict } from './Verdict.tsx'
import { TableToggle } from '../TableToggle.tsx'

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
      {heatmap?.y ? (
        <div className="heat-layout">
          <div className="heat-col">
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
          </div>
          <NeighbourFacts className="facts side" metrics={check.metrics} />
        </div>
      ) : (
        <>
          <NeighbourFacts className="facts stats" metrics={check.metrics} />
          {heatmap === null ? (
            <p className="note">No ordered axis with more than one value.</p>
          ) : (
            <>
              <ul className="legend start">
                <li>
                  <span className="key-box accent" />
                  Selected
                </li>
                <li>
                  <span className="key-dot" />
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
                columns={heatmap.x.values.map((v, i): Column => {
                  const best = i === heatmap.best.x
                  const near = heatmap.neighbours.some((n) => n.x === i)
                  return {
                    label: String(v),
                    value: heatmap.sharpe[0]?.[i] ?? null,
                    detail: paramText(heatmap.x.name, v),
                    tone: best ? 'accent' : near ? 'soft' : 'ref',
                    mark: best ? 'value' : near ? 'dot' : undefined,
                  }
                })}
              />
              <p className="axis-caption">
                {heatmap.x.name.replace(/_/g, ' ')}
              </p>
            </>
          )}
        </>
      )}
      {heatmap && <SharpeTable heatmap={heatmap} />}
    </section>
  )
}

function NeighbourFacts({
  className,
  metrics,
}: {
  className: string
  metrics: Report['checks']['sensitivity']['metrics']
}) {
  return (
    <dl className={className}>
      <div>
        <dt>Best Sharpe ratio</dt>
        <dd>{num(metrics.best_sharpe)}</dd>
      </div>
      <div>
        <dt>Neighbour mean</dt>
        <dd>{num(metrics.neighbour_mean)}</dd>
      </div>
      <div>
        <dt>Neighbour spread</dt>
        <dd>{num(metrics.neighbour_std)}</dd>
      </div>
      <div>
        <dt>Kept by neighbours</dt>
        <dd>{pct(metrics.retention, 0)}</dd>
      </div>
    </dl>
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
    <TableToggle label="Sharpe ratio of each setting">
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
    </TableToggle>
  )
}
