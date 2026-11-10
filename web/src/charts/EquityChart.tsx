import { bisector } from 'd3-array'
import { scaleLinear, scaleLog, scaleUtc } from 'd3-scale'
import { area, line } from 'd3-shape'
import { useMemo, useState, type PointerEvent } from 'react'
import { date as formatDate, num, pct } from '../format.ts'
import { ChartShell, stepIndex } from './ChartShell.tsx'
import { useWidth } from './useWidth.ts'
import { TableToggle } from '../TableToggle.tsx'

export interface Line {
  label: string
  /** A short name for the tooltip. */
  short: string
  color: string
  wash: string
  equity: number[]
  drawdown: number[]
}

interface Props {
  dates: string[]
  lines: Line[]
  label: string
}

const M = { top: 8, right: 12, bottom: 24, left: 48 }
const GAP = 28
// The tooltip is placed by its left edge, so the chart assumes this width for it.
const TIP_WIDTH = 168
const LOG_TICKS = [0.25, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]
const byTime = bisector<number, number>((t) => t)

function money(value: number): string {
  return `$${num(value, 2)}`
}

function tickMoney(value: number): string {
  return value < 1 ? `$${num(value, 2)}` : `$${num(value, 0)}`
}

export function Legend({ lines }: { lines: Pick<Line, 'label' | 'color'>[] }) {
  return (
    <ul className="legend">
      {lines.map((l) => (
        <li key={l.label}>
          <span className="key-line" style={{ background: l.color }} />
          {l.label}
        </li>
      ))}
    </ul>
  )
}

export function EquityChart({ dates, lines, label }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [index, setIndex] = useState<number | null>(null)
  const times = useMemo(
    () => dates.map((d) => Date.parse(`${d}T00:00:00Z`)),
    [dates],
  )

  const compact = width < 520
  const equityHeight = compact ? 200 : 260
  const drawdownHeight = compact ? 96 : 120
  const innerWidth = Math.max(width - M.left - M.right, 10)
  const drawdownTop = M.top + equityHeight + GAP
  const height = drawdownTop + drawdownHeight + M.bottom

  const scales = useMemo(() => {
    const first = times[0] ?? 0
    const last = times[times.length - 1] ?? 1
    const x = scaleUtc().domain([first, last]).range([0, innerWidth])
    const equities = lines.flatMap((l) => l.equity)
    const low = Math.min(...equities)
    const high = Math.max(...equities)
    const equity = scaleLog()
      .domain([low * 0.95, high * 1.05])
      .range([equityHeight, 0])
    const deepest = Math.min(...lines.flatMap((l) => l.drawdown), -0.01)
    const drawdown = scaleLinear()
      .domain([deepest, 0])
      .nice(4)
      .range([drawdownHeight, 0])
    return { x, equity, drawdown, low, high }
  }, [times, lines, innerWidth, equityHeight, drawdownHeight])

  const paths = useMemo(() => {
    const x = (i: number) => scales.x(times[i] ?? 0)
    return lines.map((l) => ({
      equity:
        line<number>()
          .x((_, i) => x(i))
          .y((v) => scales.equity(v))(l.equity) ?? '',
      drawdown:
        area<number>()
          .x((_, i) => x(i))
          .y0(0)
          .y1((v) => scales.drawdown(v))(l.drawdown) ?? '',
      drawdownLine:
        line<number>()
          .x((_, i) => x(i))
          .y((v) => scales.drawdown(v))(l.drawdown) ?? '',
    }))
  }, [lines, scales, times])

  const equityTicks = LOG_TICKS.filter(
    (t) => t >= scales.low * 0.95 && t <= scales.high * 1.05,
  )
  const drawdownTicks = scales.drawdown.ticks(compact ? 2 : 3)
  const timeTicks = scales.x.ticks(Math.max(2, Math.floor(innerWidth / 70)))

  const last = times.length - 1
  function pointAt(clientX: number, rect: DOMRect) {
    const t = scales.x.invert(clientX - rect.left - M.left).getTime()
    const i = Math.min(byTime.center(times, t), last)
    setIndex(Math.max(i, 0))
  }

  function onPointer(event: PointerEvent<SVGRectElement>) {
    const svg = event.currentTarget.ownerSVGElement
    if (svg) pointAt(event.clientX, svg.getBoundingClientRect())
  }

  // Shift moves a year of weeks at a time.
  function onMove(key: string, shift: boolean) {
    const next = stepIndex(key, index, times.length, shift ? 52 : 1)
    if (next !== undefined) setIndex(next)
    return next !== undefined
  }

  const crossX = index === null ? 0 : scales.x(times[index] ?? 0)
  const readout =
    index === null
      ? ''
      : `${formatDate(dates[index] ?? '')}: ` +
        lines
          .map(
            (l) =>
              `${l.label} ${money(l.equity[index] ?? 0)}, drawdown ${pct(l.drawdown[index])}`,
          )
          .join('; ')

  return (
    <ChartShell
      shellRef={ref}
      label={`${label}. Arrow keys step through the weeks.`}
      readout={readout}
      onMove={onMove}
      onClear={() => setIndex(null)}
      tooltip={
        index !== null && (
          <div
            className="tooltip"
            style={{
              // Beside the crosshair, on the side with room, and inside the chart.
              left:
                crossX > innerWidth / 2
                  ? Math.max(M.left + crossX - TIP_WIDTH - 12, 0)
                  : Math.min(M.left + crossX + 12, width - TIP_WIDTH),
            }}
          >
            <div className="tooltip-date">{formatDate(dates[index] ?? '')}</div>
            {lines.map((l) => (
              <div className="tooltip-row" key={l.label}>
                <span className="key-line" style={{ background: l.color }} />
                <span className="muted">{l.short}</span>
                <strong>{money(l.equity[index] ?? 0)}</strong>
                <span>{pct(l.drawdown[index])}</span>
              </div>
            ))}
          </div>
        )
      }
      after={<YearTable dates={dates} lines={lines} />}
    >
      <svg width={width} height={height} aria-hidden="true">
        <g transform={`translate(${M.left},${M.top})`}>
          {equityTicks.map((t) => (
            <g
              key={t}
              className="tick"
              transform={`translate(0,${scales.equity(t)})`}
            >
              <line x2={innerWidth} />
              <text x={-8} dy="0.32em" textAnchor="end">
                {tickMoney(t)}
              </text>
            </g>
          ))}
          <text className="axis-label" x={4} y={10}>
            Growth of $1 · log scale
          </text>
          {paths.map((p, i) => (
            <path
              key={i}
              d={p.equity}
              fill="none"
              stroke={lines[i]?.color}
              strokeWidth={i === 0 ? 2 : 1.5}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))}
        </g>
        <g transform={`translate(${M.left},${drawdownTop})`}>
          {drawdownTicks.map((t) => (
            <g
              key={t}
              className="tick"
              transform={`translate(0,${scales.drawdown(t)})`}
            >
              <line x2={innerWidth} />
              <text x={-8} dy="0.32em" textAnchor="end">
                {pct(t, 0)}
              </text>
            </g>
          ))}
          <text className="axis-label" x={4} y={drawdownHeight - 6}>
            Drawdown
          </text>
          {[...paths].reverse().map((p, j) => {
            const l = lines[lines.length - 1 - j]
            return (
              <g key={j}>
                <path d={p.drawdown} fill={l?.wash} />
                <path
                  d={p.drawdownLine}
                  fill="none"
                  stroke={l?.color}
                  strokeWidth={1}
                />
              </g>
            )
          })}
          <line className="baseline" x2={innerWidth} />
          {timeTicks.map((t) => (
            <g
              key={t.getTime()}
              className="tick"
              transform={`translate(${scales.x(t)},${drawdownHeight})`}
            >
              <text y={16} textAnchor="middle">
                {t.getUTCFullYear()}
              </text>
            </g>
          ))}
        </g>
        {index !== null && (
          <g transform={`translate(${M.left},0)`}>
            <line
              className="crosshair"
              x1={crossX}
              x2={crossX}
              y1={M.top}
              y2={drawdownTop + drawdownHeight}
            />
            {lines.map((l, i) => (
              <g key={i}>
                <circle
                  cx={crossX}
                  cy={M.top + scales.equity(l.equity[index] ?? 1)}
                  r={4}
                  fill={l.color}
                  stroke="var(--surface)"
                  strokeWidth={2}
                />
                <circle
                  cx={crossX}
                  cy={drawdownTop + scales.drawdown(l.drawdown[index] ?? 0)}
                  r={3.5}
                  fill={l.color}
                  stroke="var(--surface)"
                  strokeWidth={2}
                />
              </g>
            ))}
          </g>
        )}
        <rect
          x={M.left}
          y={0}
          width={innerWidth}
          height={drawdownTop + drawdownHeight}
          fill="transparent"
          onPointerMove={onPointer}
          onPointerDown={onPointer}
          onPointerLeave={() => setIndex(null)}
        />
      </svg>
    </ChartShell>
  )
}

/** Year-end equity and the deepest drawdown within each year. */
function YearTable({ dates, lines }: { dates: string[]; lines: Line[] }) {
  const rows = useMemo(() => {
    const out: { year: string; equity: number[]; drawdown: number[] }[] = []
    dates.forEach((d, i) => {
      const year = d.slice(0, 4)
      let row = out[out.length - 1]
      if (row?.year !== year) {
        row = { year, equity: [], drawdown: lines.map(() => 0) }
        out.push(row)
      }
      row.equity = lines.map((l) => l.equity[i] ?? 0)
      row.drawdown = row.drawdown.map((v, k) =>
        Math.min(v, lines[k]?.drawdown[i] ?? 0),
      )
    })
    return out
  }, [dates, lines])

  return (
    <TableToggle summary="Table by year" label="Equity and drawdown by year">
      <thead>
        <tr>
          <th scope="col">Year end</th>
          {lines.map((l) => (
            <th scope="col" key={l.label}>
              {l.label}
            </th>
          ))}
          {lines.map((l) => (
            <th scope="col" key={l.label}>
              Deepest drawdown, {l.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.year}>
            <th scope="row">{r.year}</th>
            {r.equity.map((v, k) => (
              <td key={k}>{money(v)}</td>
            ))}
            {r.drawdown.map((v, k) => (
              <td key={k}>{pct(v)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </TableToggle>
  )
}
