import { useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const KEY = 'theme'

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

function system(): Theme {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light'
}

/** The page theme: the system setting until the reader picks one. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => stored() ?? system())
  useEffect(() => {
    document.documentElement.dataset.theme = theme
  }, [theme])
  function toggle() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    try {
      localStorage.setItem(KEY, next)
    } catch {
      // Private windows may refuse storage; the choice lasts for this visit.
    }
  }
  return [theme, toggle] as const
}
