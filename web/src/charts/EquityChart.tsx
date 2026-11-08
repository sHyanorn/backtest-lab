import { bisector } from 'd3-array'
import { scaleLinear, scaleLog, scaleUtc } from 'd3-scale'
import { area, line } from 'd3-shape'
import {
  useId,
  useMemo,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from 'react'
import { date as formatDate, minus, num, pct } from '../format.ts'
import { useWidth } from './useWidth.ts'

export interface Line {
  label: string
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
  const id = useId()
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

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    const step = event.shiftKey ? 52 : 1
    const moves: Record<string, number> = {
      ArrowRight: step,
      ArrowLeft: -step,
      Home: -Infinity,
      End: Infinity,
    }
    if (event.key === 'Escape') {
      setIndex(null)
      return
    }
    const move = moves[event.key]
    if (move === undefined) return
    event.preventDefault()
    const from = index ?? (move > 0 ? -1 : last + 1)
    setIndex(Math.min(Math.max(from + move, 0), last))
  }

  const at = index === null ? null : index
  const crossX = at === null ? 0 : scales.x(times[at] ?? 0)
  const readout =
    at === null
      ? ''
      : `${formatDate(dates[at] ?? '')}: ` +
        lines
          .map(
            (l) =>
              `${l.label} ${money(l.equity[at] ?? 0)}, drawdown ${minus(pct(l.drawdown[at]))}`,
          )
          .join('; ')

  return (
    <div className="chart" ref={ref}>
      <div
        className="chart-hit"
        tabIndex={0}
        role="group"
        aria-label={`${label}. Arrow keys step through the weeks.`}
        aria-describedby={`${id}-readout`}
        onKeyDown={onKey}
        onBlur={() => setIndex(null)}
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
                  {minus(pct(t, 0))}
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
          {at !== null && (
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
                    cy={M.top + scales.equity(l.equity[at] ?? 1)}
                    r={4}
                    fill={l.color}
                    stroke="var(--surface)"
                    strokeWidth={2}
                  />
                  <circle
                    cx={crossX}
                    cy={drawdownTop + scales.drawdown(l.drawdown[at] ?? 0)}
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
      </div>
      {at !== null && (
        <div
          className="tooltip"
          style={
            crossX > innerWidth / 2
              ? { right: width - M.left - crossX + 12 }
              : { left: M.left + crossX + 12 }
          }
        >
          <div className="tooltip-date">{formatDate(dates[at] ?? '')}</div>
          {lines.map((l) => (
            <div className="tooltip-row" key={l.label}>
              <span className="key-line" style={{ background: l.color }} />
              <span className="muted">{l.label}</span>
              <strong>{money(l.equity[at] ?? 0)}</strong>
              <span>{minus(pct(l.drawdown[at]))}</span>
            </div>
          ))}
        </div>
      )}
      <p id={`${id}-readout`} className="visually-hidden" aria-live="polite">
        {readout}
      </p>
      <YearTable dates={dates} lines={lines} />
    </div>
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
    <details className="table-toggle">
      <summary>Table by year</summary>
      <div className="table-wrap">
        <table>
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
                  <td key={k}>{minus(pct(v))}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
