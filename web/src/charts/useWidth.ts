import { useLayoutEffect, useRef, useState } from 'react'

/** The content width of an element, kept current as it resizes. */
export function useWidth<T extends HTMLElement>(initial = 640) {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(initial)
  useLayoutEffect(() => {
    const element = ref.current
    if (element === null) return
    setWidth(element.clientWidth || initial)
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      if (entry) setWidth(Math.round(entry.contentRect.width))
    })
    observer.observe(element)
    return () => observer.disconnect()
  }, [initial])
  return [ref, width] as const
}
