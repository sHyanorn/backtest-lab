import { useEffect, useState } from 'react'

export type Async<T> =
  | { status: 'loading'; value?: T }
  | { status: 'done'; value: T }
  | { status: 'error'; error: Error; value?: T }

/** Runs `load` whenever `key` changes; the last value stays while the next loads. */
export function useAsync<T>(key: string, load: () => Promise<T>): Async<T> {
  const [state, setState] = useState<Async<T> & { key?: string }>({
    status: 'loading',
  })
  useEffect(() => {
    let live = true
    setState((s) => ({ status: 'loading', value: s.value }))
    load().then(
      (value) => live && setState({ status: 'done', value, key }),
      (error: unknown) =>
        live &&
        setState((s) => ({
          status: 'error',
          error: error instanceof Error ? error : new Error(String(error)),
          value: s.value,
        })),
    )
    return () => {
      live = false
    }
    // `load` is derived from `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  return state
}
