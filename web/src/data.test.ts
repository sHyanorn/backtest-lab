import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  asPostHoc,
  asReport,
  clearCache,
  DEMOS,
  demoUrl,
  loadDemo,
  loadPostHoc,
} from './data.ts'

const committed = (path: string): unknown =>
  JSON.parse(readFileSync(resolve(process.cwd(), '../results', path), 'utf8'))

function respond(body: unknown, status = 200) {
  return vi.fn(async () => new Response(JSON.stringify(body), { status }))
}

afterEach(() => {
  vi.unstubAllGlobals()
  clearCache()
})

describe('committed results', () => {
  it.each(DEMOS.map((d) => d.key))(
    '%s is a valid report with every check',
    (key) => {
      const report = asReport(committed(`demo/${key}.json`))
      expect(report.strategy.name).toBe(key)
      expect(Object.keys(report.checks)).toHaveLength(8)
      expect(report.series.dates).toHaveLength(
        report.series.selected.equity.length,
      )
    },
  )

  it('post hoc results cover the two real strategies', () => {
    const postHoc = asPostHoc(committed('posthoc/long_only.json'))
    expect(Object.keys(postHoc.searches).sort()).toEqual([
      'ma_crossover',
      'momentum',
    ])
  })

  it('every demo has an asset url', () => {
    for (const { key } of DEMOS)
      expect(demoUrl(key)).toMatch(/ma_crossover|momentum|random/)
  })
})

describe('loading', () => {
  it('fetches and caches a report', async () => {
    const fetch = respond(committed('demo/momentum.json'))
    vi.stubGlobal('fetch', fetch)
    const report = await loadDemo('momentum')
    expect(report.selected.params).toMatchObject({
      lookback: 273,
      allow_short: false,
    })
    await loadDemo('momentum')
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('rejects another schema version', async () => {
    vi.stubGlobal('fetch', respond({ schema_version: '2.0' }))
    await expect(loadDemo('momentum')).rejects.toThrow(
      'unsupported report format',
    )
  })

  it('rejects an HTTP error and retries the next time', async () => {
    vi.stubGlobal('fetch', respond({}, 404))
    await expect(loadDemo('ma_crossover')).rejects.toThrow('404')
    const fetch = respond(committed('demo/ma_crossover.json'))
    vi.stubGlobal('fetch', fetch)
    await expect(loadDemo('ma_crossover')).resolves.toBeTruthy()
  })

  it('rejects post hoc results without the label', async () => {
    vi.stubGlobal('fetch', respond({ searches: {} }))
    await expect(loadPostHoc()).rejects.toThrow('unsupported post hoc format')
  })
})
