import { scaleBand, scaleLinear } from 'd3-scale'
import { useId, useState, type KeyboardEvent } from 'react'
import { useWidth } from './useWidth.ts'

export interface Column {
  label: string
  value: number | null
  /** Shown in the tooltip, e.g. a setting or a date range. */
  detail?: string
  tone?: 'accent' | 'soft' | 'ref'
  /** A value label or a dot beyond the bar's end, for the columns the story is about. */
  mark?: 'value' | 'dot'
}

interface Props {
  columns: Column[]
  label: string
  format: (value: number) => string
  height?: number
  /** Draw a vertical marker before this column, e.g. a logit of zero. */
  marker?: { before: number; label: string }
}

const M = { top: 12, right: 8, bottom: 22, left: 44 }

/** Columns from a zero baseline; every column has a tooltip and keyboard focus. */
export function Columns({
  columns,
  label,
  format,
  height = 180,
  marker,
}: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<number | null>(null)
  const id = useId()
  const innerWidth = Math.max(width - M.left - M.right, 10)
  const innerHeight = height - M.top - M.bottom

  const values = columns.map((c) => c.value ?? 0)
  const y = scaleLinear()
    .domain([Math.min(0, ...values), Math.max(0, ...values)])
    .nice(4)
    .range([innerHeight, 0])
  const x = scaleBand<number>()
    .domain(columns.map((_, i) => i))
    .range([0, innerWidth])
    .paddingInner(columns.length > 40 ? 0.15 : 0.25)
  const band = x.bandwidth()
  const barWidth = Math.min(band, 24)
  const every = Math.ceil(
    columns.length / Math.max(2, Math.floor(innerWidth / 44)),
  )

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    const last = columns.length - 1
    const moves: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1 }
    if (event.key === 'Escape') {
      // The first Escape clears the readout; the next may close a dialog.
      if (active !== null) event.preventDefault()
      return setActive(null)
    }
    if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault()
      return setActive(event.key === 'Home' ? 0 : last)
    }
    const move = moves[event.key]
    if (move === undefined) return
    event.preventDefault()
    setActive((a) =>
      Math.min(Math.max((a ?? (move > 0 ? -1 : last + 1)) + move, 0), last),
    )
  }

  const current = active === null ? null : columns[active]
  const currentX = active === null ? 0 : M.left + (x(active) ?? 0) + band / 2
  // Beside the hovered column, level with its end, so taller columns stay visible.
  const currentTop =
    current?.value == null
      ? 0
      : Math.min(
          Math.max(M.top + y(Math.max(current.value, 0)) - 12, 0),
          height - 64,
        )

  return (
    <div className="chart" ref={ref}>
      <div
        className="chart-hit"
        tabIndex={0}
        role="group"
        aria-label={`${label}. Arrow keys step through the columns.`}
        aria-describedby={`${id}-readout`}
        onKeyDown={onKey}
        onBlur={() => setActive(null)}
        onPointerLeave={() => setActive(null)}
      >
        <svg width={width} height={height} aria-hidden="true">
          <g transform={`translate(${M.left},${M.top})`}>
            {y.ticks(4).map((t) => (
              <g key={t} className="tick" transform={`translate(0,${y(t)})`}>
                <line x2={innerWidth} />
                <text x={-8} dy="0.32em" textAnchor="end">
                  {format(t)}
                </text>
              </g>
            ))}
            {columns.map((c, i) => {
              const v = c.value ?? 0
              const top = y(Math.max(v, 0))
              const h = Math.abs(y(v) - y(0))
              const cx = (x(i) ?? 0) + band / 2
              return (
                <g key={i} className={`column ${c.tone ?? 'soft'}`}>
                  <rect
                    x={cx - barWidth / 2}
                    y={top}
                    width={barWidth}
                    height={Math.max(h, 0.5)}
                    rx={Math.min(3, barWidth / 3)}
                    opacity={active === null || active === i ? 1 : 0.55}
                  />
                  <rect
                    className="hit"
                    x={x(i)}
                    y={0}
                    width={x.step()}
                    height={innerHeight}
                    fill="transparent"
                    onPointerEnter={() => setActive(i)}
                    onPointerDown={() => setActive(i)}
                  />
                  {c.mark === 'value' && c.value !== null && (
                    <text
                      className="column-value"
                      x={cx}
                      y={v >= 0 ? top - 6 : top + h + 14}
                      textAnchor="middle"
                    >
                      {format(v)}
                    </text>
                  )}
                  {c.mark === 'dot' && (
                    <circle
                      className="mark-dot"
                      cx={cx}
                      cy={v >= 0 ? top - 8 : top + h + 8}
                      r={3.5}
                    />
                  )}
                  {i % every === 0 && (
                    <text
                      className="tick-label"
                      x={cx}
                      y={innerHeight + 15}
                      textAnchor="middle"
                    >
                      {c.label}
                    </text>
                  )}
                </g>
              )
            })}
            <line className="baseline" x2={innerWidth} y1={y(0)} y2={y(0)} />
            {marker && (
              <g className="marker">
                <line
                  x1={x(marker.before) ?? 0}
                  x2={x(marker.before) ?? 0}
                  y1={-4}
                  y2={innerHeight}
                />
                <text x={(x(marker.before) ?? 0) + 4} y={4}>
                  {marker.label}
                </text>
              </g>
            )}
          </g>
        </svg>
      </div>
      {current && (
        <div
          className="tooltip"
          style={{
            top: currentTop,
            ...(currentX > width / 2
              ? { right: width - currentX + 10 }
              : { left: currentX + 10 }),
          }}
        >
          <div className="tooltip-date">{current.detail ?? current.label}</div>
          <strong className="tooltip-value">
            {current.value === null ? 'n/a' : format(current.value)}
          </strong>
        </div>
      )}
      <p id={`${id}-readout`} className="visually-hidden" aria-live="polite">
        {current
          ? `${current.detail ?? current.label}: ${current.value === null ? 'n/a' : format(current.value)}`
          : ''}
      </p>
    </div>
  )
}
