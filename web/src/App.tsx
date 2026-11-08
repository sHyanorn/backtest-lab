import { DEMOS, type DemoKey } from './data.ts'
import { DemoView } from './DemoView.tsx'
import { useHashRoute } from './route.ts'
import { useTheme } from './theme.ts'

export default function App() {
  const route = useHashRoute()
  const [theme, toggleTheme] = useTheme()
  const demo: DemoKey =
    DEMOS.find((d) => d.key === route)?.key ?? 'ma_crossover'

  return (
    <div className="shell">
      <header className="top">
        <span className="brand">backtest-lab</span>
        <span className="chip">
          <span className="chip-dot" />
          Static · precomputed
        </span>
        <button
          type="button"
          className="icon-button"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Use light theme' : 'Use dark theme'}
        >
          <ThemeIcon dark={theme === 'dark'} />
        </button>
      </header>
      <nav className="tabs" aria-label="Searches">
        {DEMOS.map((d) => (
          <a
            key={d.key}
            className="tab"
            href={`#/${d.key}`}
            aria-current={d.key === demo ? 'page' : undefined}
          >
            {d.label}
          </a>
        ))}
      </nav>
      <main>
        <DemoView demo={demo} />
      </main>
    </div>
  )
}

function ThemeIcon({ dark }: { dark: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
      {dark ? (
        <path
          d="M13.5 9.6A5.8 5.8 0 0 1 6.4 2.5a5.8 5.8 0 1 0 7.1 7.1Z"
          fill="currentColor"
        />
      ) : (
        <g stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
          <circle cx="8" cy="8" r="3" fill="currentColor" stroke="none" />
          <path d="M8 1v1.5M8 13.5V15M1 8h1.5M13.5 8H15M3 3l1 1M12 12l1 1M3 13l1-1M12 4l1-1" />
        </g>
      )}
    </svg>
  )
}
