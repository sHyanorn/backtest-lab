import { useId, useState, type KeyboardEvent } from 'react'
import type { Heatmap } from '../report.gen.ts'
import { colourScale, DIV_HALF, SEQ_STEPS } from './colour.ts'
import { useWidth } from './useWidth.ts'

interface Props {
  heatmap: Heatmap
  label: string
  format: (value: number) => string
  /** Tooltip line for a cell, e.g. its setting. */
  describe: (x: number, y: number) => string
}

const M = { top: 22, right: 8, bottom: 36, left: 52 }
export function HeatGrid({ heatmap, label, format, describe }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [active, setActive] = useState<{ x: number; y: number } | null>(null)
  const id = useId()
  const nx = heatmap.x.values.length
  const ny = heatmap.sharpe.length
  const values = heatmap.sharpe.flat().filter((v): v is number => v !== null)
  const colour = colourScale(values)
  const cell = Math.max(Math.min(56, (width - M.left - M.right) / nx), 14)
  const gridWidth = cell * nx
  const gridHeight = cell * ny
  // Rows run upwards so the y axis increases like a chart's.
  const top = (row: number) => (ny - 1 - row) * cell

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    const moves: Record<string, [number, number]> = {
      ArrowRight: [1, 0],
      ArrowLeft: [-1, 0],
      ArrowUp: [0, 1],
      ArrowDown: [0, -1],
    }
    if (event.key === 'Escape') {
      if (active !== null) event.preventDefault()
      return setActive(null)
    }
    const move = moves[event.key]
    if (!move) return
    event.preventDefault()
    setActive((a) => {
      const from = a ?? heatmap.best
      return {
        x: Math.min(Math.max(from.x + (a ? move[0] : 0), 0), nx - 1),
        y: Math.min(Math.max(from.y + (a ? move[1] : 0), 0), ny - 1),
      }
    })
  }

  const value = active ? heatmap.sharpe[active.y]?.[active.x] : undefined
  const valueText = value == null ? 'n/a' : format(value)
  const readout = active
    ? `${describe(active.x, active.y)}: Sharpe ${valueText}`
    : ''
  const tipLeft = active ? M.left + (active.x + 1) * cell + 8 : 0

  return (
    <div className="chart heat" ref={ref}>
      <div
        className="chart-hit"
        tabIndex={0}
        role="group"
        aria-label={`${label}. Arrow keys move between settings.`}
        aria-describedby={`${id}-readout`}
        onKeyDown={onKey}
        onBlur={() => setActive(null)}
        onPointerLeave={() => setActive(null)}
      >
        <svg
          width={M.left + gridWidth + M.right}
          height={M.top + gridHeight + M.bottom}
          aria-hidden="true"
        >
          <g transform={`translate(${M.left},${M.top})`}>
            {heatmap.y && (
              <text className="axis-label" x={-8} y={-8} textAnchor="end">
                {heatmap.y.name.replace(/_/g, ' ')}
              </text>
            )}
            {heatmap.sharpe.map((row, y) =>
              row.map((v, x) => (
                <rect
                  key={`${x}-${y}`}
                  className="cell"
                  x={x * cell + 1}
                  y={top(y) + 1}
                  width={cell - 2}
                  height={cell - 2}
                  rx={3}
                  fill={v === null ? 'var(--surface-2)' : colour.fill(v)}
                  onPointerEnter={() => setActive({ x, y })}
                  onPointerDown={() => setActive({ x, y })}
                />
              )),
            )}
            {heatmap.neighbours.map((n) => (
              <circle
                key={`n${n.x}-${n.y}`}
                className="mark-dot"
                cx={n.x * cell + cell / 2}
                cy={top(n.y) + cell / 2}
                r={Math.max(Math.min(cell / 10, 4), 2.5)}
              />
            ))}
            <rect
              className="cell-best"
              x={heatmap.best.x * cell}
              y={top(heatmap.best.y)}
              width={cell}
              height={cell}
              rx={4}
            />
            <rect
              className="cell-best-gap"
              x={heatmap.best.x * cell + 2.5}
              y={top(heatmap.best.y) + 2.5}
              width={cell - 5}
              height={cell - 5}
              rx={2}
            />
            {active && (
              <rect
                className="cell-active"
                x={active.x * cell + 0.5}
                y={top(active.y) + 0.5}
                width={cell - 1}
                height={cell - 1}
                rx={3.5}
              />
            )}
            {heatmap.y?.values.map((v, y) => (
              <text
                key={y}
                className="tick-label"
                x={-8}
                y={top(y) + cell / 2}
                dy="0.32em"
                textAnchor="end"
              >
                {String(v)}
              </text>
            ))}
            {heatmap.x.values.map((v, x) => (
              <text
                key={x}
                className="tick-label"
                x={x * cell + cell / 2}
                y={gridHeight + 14}
                textAnchor="middle"
              >
                {String(v)}
              </text>
            ))}
            <text
              className="axis-label"
              x={gridWidth / 2}
              y={gridHeight + 32}
              textAnchor="middle"
            >
              {heatmap.x.name.replace(/_/g, ' ')}
            </text>
          </g>
        </svg>
      </div>
      {active && (
        <div
          className="tooltip"
          style={{
            ...(tipLeft + 180 > width
              ? { right: width - M.left - active.x * cell + 8 }
              : { left: tipLeft }),
            top: M.top + top(active.y),
          }}
        >
          <div className="tooltip-date">{describe(active.x, active.y)}</div>
          <strong className="tooltip-value">Sharpe {valueText}</strong>
        </div>
      )}
      <p id={`${id}-readout`} className="visually-hidden" aria-live="polite">
        {readout}
      </p>
    </div>
  )
}

/** Discrete colour key for a heat grid, from its lowest to its highest value. */
export function HeatLegend({
  values,
  format,
}: {
  values: number[]
  format: (v: number) => string
}) {
  const colour = colourScale(values)
  // A diverging ramp is symmetric around zero.
  const reach = Math.max(-colour.low, colour.high)
  const steps = colour.diverging
    ? Array.from({ length: DIV_HALF * 2 + 1 }, (_, i) => `var(--div-${i})`)
    : Array.from({ length: SEQ_STEPS }, (_, i) => `var(--seq-${i})`)
  return (
    <div className="heat-legend">
      <span>{format(colour.diverging ? -reach : colour.low)}</span>
      <span className="heat-ramp" aria-hidden="true">
        {steps.map((s) => (
          <span key={s} style={{ background: s }} />
        ))}
      </span>
      <span>{format(colour.diverging ? reach : colour.high)}</span>
      <span className="heat-item">
        <span className="heat-key best" aria-hidden="true" />
        Selected
      </span>
      <span className="heat-item">
        <span className="heat-key neighbour" aria-hidden="true" />
        Neighbours
      </span>
    </div>
  )
}
