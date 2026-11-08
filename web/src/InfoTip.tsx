import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'

const EDGE = 12

/** A small "i" button whose text shows on hover or focus, and toggles on tap. */
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
  const [pinned, setPinned] = useState(false)
  // Escape hides the tip until the pointer or focus leaves and comes back.
  const [dismissed, setDismissed] = useState(false)
  const [shift, setShift] = useState(0)
  const root = useRef<HTMLSpanElement>(null)
  const tip = useRef<HTMLSpanElement>(null)
  const pointer = useRef('')
  const open = (hover || focus || pinned) && !dismissed

  useEffect(() => {
    if (!open) return
    function onKey(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      // Inside a dialog, the first Escape closes the tip, not the dialog.
      event.preventDefault()
      setPinned(false)
      setDismissed(true)
    }
    function onPointer(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setPinned(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onPointer)
    }
  }, [open])

  // Keep the tip inside the viewport on narrow screens.
  useLayoutEffect(() => {
    if (!open || tip.current === null) {
      setShift(0)
      return
    }
    const box = tip.current.getBoundingClientRect()
    const width = document.documentElement.clientWidth
    if (box.right > width - EDGE) setShift(width - EDGE - box.right)
    else if (box.left < EDGE) setShift(EDGE - box.left)
  }, [open])

  return (
    <span
      ref={root}
      className={`info ${align}`}
      onPointerEnter={(e) => e.pointerType === 'mouse' && setHover(true)}
      onPointerLeave={() => {
        setHover(false)
        if (!focus) setDismissed(false)
      }}
    >
      <button
        type="button"
        className="info-button"
        aria-label={label}
        aria-describedby={id}
        aria-expanded={open}
        onPointerDown={(e) => (pointer.current = e.pointerType)}
        onClick={() => {
          // A mouse already opened it on hover; a tap or a key toggles it.
          if (pointer.current === 'mouse') return
          if (open) {
            setPinned(false)
            setDismissed(true)
          } else {
            setDismissed(false)
            setPinned(true)
          }
        }}
        onKeyDown={() => (pointer.current = '')}
        // Focus from a pointer is handled by hover or by the tap itself.
        onFocus={() => pointer.current === '' && setFocus(true)}
        onBlur={() => {
          pointer.current = ''
          setFocus(false)
          setPinned(false)
          setDismissed(false)
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
