import { useSyncExternalStore } from 'react'

function subscribe(onChange: () => void) {
  window.addEventListener('hashchange', onChange)
  return () => window.removeEventListener('hashchange', onChange)
}

/** The path in the URL hash, so views can be linked on a static host. */
export function useHashRoute(): string {
  return useSyncExternalStore(
    subscribe,
    () => window.location.hash.replace(/^#\/?/, ''),
    () => '',
  )
}
