import type { ReactNode } from 'react'

/** A collapsed data table: the accessible alternative to a chart. */
export function TableToggle({
  summary = 'Table',
  label,
  children,
}: {
  summary?: string
  label: string
  children: ReactNode
}) {
  return (
    <details className="table-toggle">
      <summary>
        {summary}
        <span className="visually-hidden">: {label}</span>
      </summary>
      {/* Focusable so the scrolled table can be read from the keyboard. */}
      <div className="table-wrap" tabIndex={0} role="region" aria-label={label}>
        <table>{children}</table>
      </div>
    </details>
  )
}
