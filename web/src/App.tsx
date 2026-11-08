import { lazy, Suspense } from 'react'
import { DEMOS, type DemoKey } from './data.ts'
import { DemoView } from './DemoView.tsx'
import { InfoTip } from './InfoTip.tsx'
import { useHashRoute } from './route.ts'
import { useApi, type ApiState } from './sweep/api.ts'
import { useTheme } from './theme.ts'

// Only the dev server can reach the API, so a static build leaves this out.
const SweepView = import.meta.env.DEV
  ? lazy(() => import('./sweep/SweepView.tsx'))
  : null

export default function App() {
  const route = useHashRoute()
  const [theme, toggleTheme] = useTheme()
  const api = useApi()
  const live = api.status === 'online' && SweepView !== null
  const sweep = live && route === 'sweep'
  const demo: DemoKey =
    DEMOS.find((d) => d.key === route)?.key ?? 'ma_crossover'

  return (
    <div className="shell">
      <header className="top">
        <span className="brand">backtest-lab</span>
        <ModeChip api={api} />
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
            aria-current={!sweep && d.key === demo ? 'page' : undefined}
          >
            {d.label}
          </a>
        ))}
        {live && (
          <a
            className="tab"
            href="#/sweep"
            aria-current={sweep ? 'page' : undefined}
          >
            Custom sweep
          </a>
        )}
      </nav>
      <main>
        {sweep && api.status === 'online' && SweepView ? (
          <Suspense fallback={<div className="view" aria-busy="true" />}>
            <SweepView strategies={api.strategies} />
          </Suspense>
        ) : (
          <DemoView demo={demo} />
        )}
      </main>
    </div>
  )
}

function ModeChip({ api }: { api: ApiState }) {
  if (api.status === 'online') {
    return (
      <span className="chip">
        <span className="chip-dot live" />
        Local API
      </span>
    )
  }
  return (
    <span className="chip">
      <span className="chip-dot" />
      {api.status === 'offline' ? 'API offline' : 'Static · precomputed'}
      <InfoTip label="About this mode" align="end">
        {api.status === 'offline'
          ? 'Showing the committed results. Start the API on 127.0.0.1:8000 and reload to run new sweeps.'
          : 'Pre-registered results committed to the repository. Run the dashboard locally with the API to start new sweeps.'}
      </InfoTip>
    </span>
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
