import { useId, type ReactNode } from 'react'

/** A small "i" button whose text shows on hover, focus or tap. */
export function InfoTip({
  label,
  children,
  align = 'start',
}: {
  label: string
  children: ReactNode
  align?: 'start' | 'end'
}) {
  const id = useId()
  return (
    <span className={`info ${align}`}>
      <button
        type="button"
        className="info-button"
        aria-label={label}
        aria-describedby={id}
        onKeyDown={(e) => e.key === 'Escape' && e.currentTarget.blur()}
      >
        <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
          <circle
            cx="8"
            cy="8"
            r="7.25"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          />
          <path
            d="M8 7v4.5M8 4.6v.1"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
          />
        </svg>
      </button>
      <span role="tooltip" id={id} className="info-tip">
        {children}
      </span>
    </span>
  )
}
