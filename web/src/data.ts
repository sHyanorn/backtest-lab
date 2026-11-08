import type { Report } from './report.gen.ts'

export type { Report }

/** The pre-registered searches in results/demo (D021), in story order. */
export const DEMOS = [
  { key: 'ma_crossover', label: 'Moving average' },
  { key: 'momentum', label: 'Momentum' },
  { key: 'random_signal', label: 'Random control' },
] as const

export type DemoKey = (typeof DEMOS)[number]['key']

/** Post hoc analysis of one real search (results/posthoc, D029). */
export interface PostHocSearch {
  n_trials: number
  annual_sharpe_range: {
    long_only: [number, number]
    long_short: [number, number]
  }
  cscv: {
    combinations: number
    long_only_winner_share: number
    distinct_winners: number
  }
  pbo: { full_grid: number; long_only_half: number }
  long_only_half_dsr: { n_trials: number; n_effective: number; dsr: number }
  selected: { trial: number; params: Record<string, boolean | number | string> }
  selected_profile: Profile
  benchmark_profile: Profile
  benchmark_drawdowns: {
    peak: string
    trough: string
    benchmark_return: number
    selected_return: number
  }[]
}

export interface Profile {
  annual_mean_return: number
  annual_volatility: number
  sharpe: number
  cagr: number
  max_drawdown: number
  time_in_market: number
}

export interface PostHoc {
  post_hoc: true
  note: string
  searches: Partial<Record<DemoKey, PostHocSearch>>
}

// Vite emits each committed file as a hashed asset; nothing is copied or regenerated.
const demoUrls = import.meta.glob<string>('../../results/demo/*.json', {
  query: '?url',
  import: 'default',
  eager: true,
})
const postHocUrl = Object.values(
  import.meta.glob<string>('../../results/posthoc/long_only.json', {
    query: '?url',
    import: 'default',
    eager: true,
  }),
)[0]

export function demoUrl(key: DemoKey): string {
  const url = demoUrls[`../../results/demo/${key}.json`]
  if (url === undefined) throw new Error(`no committed report for ${key}`)
  return url
}

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url)
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
  return response.json()
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/** Accepts a report of the schema version this build was generated from. */
export function asReport(value: unknown): Report {
  if (!isObject(value) || value.schema_version !== '1.0') {
    throw new Error('unsupported report format')
  }
  for (const key of [
    'strategy',
    'sample',
    'costs',
    'selected',
    'benchmark',
    'overall',
  ]) {
    if (!isObject(value[key])) throw new Error(`report has no ${key}`)
  }
  if (!isObject(value.checks) || !isObject(value.series)) {
    throw new Error('report has no checks')
  }
  return value as unknown as Report
}

export function asPostHoc(value: unknown): PostHoc {
  if (
    !isObject(value) ||
    value.post_hoc !== true ||
    !isObject(value.searches)
  ) {
    throw new Error('unsupported post hoc format')
  }
  return value as unknown as PostHoc
}

const cache = new Map<string, Promise<unknown>>()

function cached<T>(key: string, load: () => Promise<T>): Promise<T> {
  let promise = cache.get(key) as Promise<T> | undefined
  if (promise === undefined) {
    promise = load()
    // A failed load is retried on the next request.
    promise.catch(() => cache.delete(key))
    cache.set(key, promise)
  }
  return promise
}

export function loadDemo(key: DemoKey): Promise<Report> {
  return cached(`demo:${key}`, async () =>
    asReport(await fetchJson(demoUrl(key))),
  )
}

export function loadPostHoc(): Promise<PostHoc> {
  if (postHocUrl === undefined)
    return Promise.reject(new Error('no post hoc results'))
  return cached('posthoc', async () => asPostHoc(await fetchJson(postHocUrl)))
}

export function clearCache(): void {
  cache.clear()
}
