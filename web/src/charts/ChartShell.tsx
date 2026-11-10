import { useId, type KeyboardEvent, type ReactNode, type Ref } from 'react'

interface Props {
  shellRef: Ref<HTMLDivElement>
  className?: string
  /** The accessible name, ending with what the arrow keys do. */
  label: string
  /** The selected point in words; empty when nothing is selected. */
  readout: string
  /** An arrow, Home or End key was pressed; true when it moved the selection. */
  onMove: (key: string, shift: boolean) => boolean
  onClear: () => void
  clearOnPointerLeave?: boolean
  /** The tooltip of the selected point. */
  tooltip: ReactNode
  /** Shown below the chart, such as its data table. */
  after?: ReactNode
  children: ReactNode
}

/** What every chart shares (D030): one focus stop whose arrow keys move a selection
 * and whose Escape clears it, and a spoken readout of the selected point. */
export function ChartShell({
  shellRef,
  className,
  label,
  readout,
  onMove,
  onClear,
  clearOnPointerLeave,
  tooltip,
  after,
  children,
}: Props) {
  const id = useId()

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') {
      // The first Escape clears the readout; the next may close a dialog.
      if (readout) event.preventDefault()
      onClear()
    } else if (onMove(event.key, event.shiftKey)) {
      event.preventDefault()
    }
  }

  return (
    <div className={className ? `chart ${className}` : 'chart'} ref={shellRef}>
      <div
        className="chart-hit"
        tabIndex={0}
        role="group"
        aria-label={label}
        aria-describedby={`${id}-readout`}
        onKeyDown={onKeyDown}
        onBlur={onClear}
        onPointerLeave={clearOnPointerLeave ? onClear : undefined}
      >
        {children}
      </div>
      {tooltip}
      <p id={`${id}-readout`} className="visually-hidden" aria-live="polite">
        {readout}
      </p>
      {after}
    </div>
  )
}

/** Where an arrow, Home or End key moves the selection in a row of `count` points, or
 * undefined for another key. From no selection the right arrow gives the first point
 * and the left arrow the last. */
export function stepIndex(
  key: string,
  from: number | null,
  count: number,
  stride = 1,
): number | undefined {
  const moves: Record<string, number> = {
    ArrowRight: stride,
    ArrowLeft: -stride,
    Home: -Infinity,
    End: Infinity,
  }
  const move = moves[key]
  if (move === undefined) return undefined
  const last = count - 1
  return Math.min(
    Math.max((from ?? (move > 0 ? -1 : last + 1)) + move, 0),
    last,
  )
}
