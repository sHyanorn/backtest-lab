import { useCallback, useEffect, useState } from 'react'

export interface Async<T> {
  status: 'loading' | 'done' | 'error'
  /** The last loaded value, which may belong to an earlier key. */
  value?: T
  /** The key `value` was loaded for. */
  valueKey?: string
  error?: Error
  retry: () => void
}

interface Settled<T> {
  /** The key and attempt this result answers. */
  request: string
  error?: Error
  value?: T
  valueKey?: string
}

/** Runs `load` whenever `key` changes; the last value stays while the next loads. */
export function useAsync<T>(key: string, load: () => Promise<T>): Async<T> {
  const [attempt, setAttempt] = useState(0)
  const [settled, setSettled] = useState<Settled<T>>({ request: '' })
  const request = `${key}\n${attempt}`
  useEffect(() => {
    let live = true
    load().then(
      (value) => live && setSettled({ request, value, valueKey: key }),
      (error: unknown) =>
        live &&
        setSettled((s) => ({
          ...s,
          request,
          error: error instanceof Error ? error : new Error(String(error)),
        })),
    )
    return () => {
      live = false
    }
    // `load` is derived from `key`, and `request` from `key` and `attempt`.
  }, [request]) // oxlint-disable-line react-hooks/exhaustive-deps
  const retry = useCallback(() => setAttempt((a) => a + 1), [])
  const current = settled.request === request
  return {
    status: !current ? 'loading' : settled.error ? 'error' : 'done',
    value: settled.value,
    valueKey: settled.valueKey,
    error: current ? settled.error : undefined,
    retry,
  }
}
