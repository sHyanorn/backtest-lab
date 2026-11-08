import { useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react'

const EDGE = 12

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
  const [hover, setHover] = useState(false)
  const [focus, setFocus] = useState(false)
  const [shift, setShift] = useState(0)
  const tip = useRef<HTMLSpanElement>(null)
  const open = hover || focus

  // Keep the tip inside the viewport on narrow screens.
  useLayoutEffect(() => {
    if (!open || tip.current === null) return setShift(0)
    const box = tip.current.getBoundingClientRect()
    const width = document.documentElement.clientWidth
    if (box.right > width - EDGE) setShift(width - EDGE - box.right)
    else if (box.left < EDGE) setShift(EDGE - box.left)
  }, [open])

  return (
    <span
      className={`info ${align}`}
      onPointerEnter={(e) => e.pointerType === 'mouse' && setHover(true)}
      onPointerLeave={() => setHover(false)}
    >
      <button
        type="button"
        className="info-button"
        aria-label={label}
        aria-describedby={id}
        onFocus={() => setFocus(true)}
        onBlur={() => setFocus(false)}
        onKeyDown={(e) => {
          if (e.key === 'Escape') {
            setFocus(false)
            setHover(false)
          }
        }}
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
      <span
        ref={tip}
        role="tooltip"
        id={id}
        className="info-tip"
        data-open={open || undefined}
        style={shift ? { translate: `${shift}px 0` } : undefined}
      >
        {children}
      </span>
    </span>
  )
}
