import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { asPostHoc, asReport, type Report } from '../data.ts'
import { colourScale } from '../charts/colour.ts'
import { num, pct, signed, trialParams } from '../format.ts'
import { CheckCards } from './CheckCards.tsx'
import { checkViews } from './checks.ts'
import { Overview } from './Overview.tsx'
import { PostHoc } from './PostHoc.tsx'

const load = (key: string): Report =>
  asReport(
    JSON.parse(
      readFileSync(
        resolve(process.cwd(), `../results/demo/${key}.json`),
        'utf8',
      ),
    ),
  )

afterEach(cleanup)

describe('overview', () => {
  it('labels the overall verdict in words', () => {
    render(
      <Overview
        report={load('ma_crossover')}
        title="MA"
        kind="Pre-registered"
      />,
    )
    const panel = screen.getByRole('region', { name: 'Overfitting checks' })
    expect(within(panel).getByText('Borderline')).toBeTruthy()
    expect(within(panel).getByText(/1 of 8 are borderline/)).toBeTruthy()
  })

  it('keeps the benchmark out of the verdict panel', () => {
    render(
      <Overview
        report={load('ma_crossover')}
        title="MA"
        kind="Pre-registered"
      />,
    )
    const checks = screen.getByRole('region', { name: 'Overfitting checks' })
    const benchmark = screen.getByRole('region', {
      name: 'Against SPY buy and hold',
    })
    expect(checks.textContent).not.toMatch(/buy and hold|CAGR/i)
    expect(within(benchmark).getByText('Not part of the verdict')).toBeTruthy()
    expect(within(benchmark).getByText('0.64')).toBeTruthy()
    expect(within(benchmark).getByText('−55.2%')).toBeTruthy()
  })

  it('states the costs, and marks a zero-cost run as a reference', () => {
    const report = load('momentum')
    const { unmount } = render(
      <Overview report={report} title="M" kind="Pre-registered" />,
    )
    expect(
      screen.getByText('Net of 1 bp fees + 5 bps slippage per side'),
    ).toBeTruthy()
    unmount()
    render(
      <Overview
        report={{ ...report, costs: { fee_bps: 0, slippage_bps: 0 } }}
        title="M"
        kind="Pre-registered"
      />,
    )
    expect(screen.getByText('Zero-cost reference')).toBeTruthy()
  })
})

describe('check cards', () => {
  it('shows every check with its verdict in words', () => {
    render(<CheckCards report={load('random_signal')} />)
    const items = screen.getAllByRole('listitem')
    expect(items).toHaveLength(8)
    const verdicts = items.map(
      (li) => li.querySelector('.verdict')?.textContent,
    )
    expect(verdicts).toEqual([
      'Fail',
      'Fail',
      'Fail',
      'Borderline',
      'Fail',
      'Borderline',
      'Fail',
      'Fail',
    ])
  })

  it('shows the headline numbers of the registered results', () => {
    render(<CheckCards report={load('ma_crossover')} />)
    const dsr = screen.getByRole('heading', { name: 'Deflated Sharpe ratio' })
      .parentElement as HTMLElement
    expect(within(dsr).getByText('0.945')).toBeTruthy()
    expect(within(dsr).getByText('Borderline')).toBeTruthy()
  })

  it('shows an undefined metric as n/a', () => {
    const report = load('momentum')
    const holdout = {
      ...report.checks.holdout,
      verdict: 'red' as const,
      metrics: { ...report.checks.holdout.metrics, retention: null },
    }
    render(
      <CheckCards
        report={{ ...report, checks: { ...report.checks, holdout } }}
      />,
    )
    const card = screen.getByRole('heading', { name: 'Holdout split' })
      .parentElement as HTMLElement
    expect(card.querySelector('.figure-value')?.textContent).toBe('n/a')
    expect(card.querySelector('.verdict')?.textContent).toBe('Fail')
  })

  it('gives no verdict or headline number to a check that is not assessable', () => {
    const report = load('ma_crossover')
    const pbo = { ...report.checks.pbo, verdict: 'not_assessable' as const }
    render(
      <CheckCards report={{ ...report, checks: { ...report.checks, pbo } }} />,
    )
    const card = screen.getByRole('heading', {
      name: 'Probability of backtest overfitting',
    }).parentElement as HTMLElement
    expect(card.querySelector('.verdict')?.textContent).toBe('Not assessable')
    expect(card.querySelector('.figure-value')?.textContent).toBe('–')
    const dsr = screen.getByRole('heading', { name: 'Deflated Sharpe ratio' })
      .parentElement as HTMLElement
    expect(dsr.querySelector('.figure-value')?.textContent).toBe('0.945')
  })

  it('states the floor on independent settings only for reports built under it', () => {
    const report = load('ma_crossover')
    const rule = (r: Report) => checkViews(r).find((c) => c.key === 'pbo')?.rule
    expect(rule(report)).not.toContain('Not assessed')
    expect(rule({ ...report, schema_version: '1.1' })).toContain(
      'Not assessed when fewer than 10 independent settings were tried.',
    )
  })

  it('notes that the seed sensitivity verdict is uninformative', () => {
    render(<CheckCards report={load('random_signal')} />)
    expect(screen.getByText(/Neighbouring seeds are unrelated/)).toBeTruthy()
  })
})

describe('format', () => {
  it('uses a true minus sign and drops the sign of zero', () => {
    expect(num(-0.4231)).toBe('−0.42')
    expect(pct(-0.0001)).toBe('0.0%')
    expect(signed(num(0.16))).toBe('+0.16')
    expect(signed(num(-1.1, 1))).toBe('−1.1')
  })
})

describe('grid helpers', () => {
  it('recovers trial parameters with the last axis fastest', () => {
    const { strategy, selected, checks } = load('ma_crossover')
    expect(trialParams(strategy.grid, strategy.fixed, selected.trial)).toEqual(
      selected.params,
    )
    expect(
      trialParams(strategy.grid, strategy.fixed, checks.holdout.details.trial),
    ).toEqual(checks.holdout.details.params)
  })

  it('colours one sign with one ramp and both signs around zero', () => {
    const seq = colourScale([0.5, 0.8])
    expect(seq.diverging).toBe(false)
    expect(seq.fill(0.5)).toBe('var(--seq-0)')
    expect(seq.fill(0.8)).toBe('var(--seq-6)')
    const div = colourScale([-0.6, 0.2])
    expect(div.diverging).toBe(true)
    expect(div.fill(0)).toBe('var(--div-4)')
    expect(div.fill(-0.6)).toBe('var(--div-0)')
  })
})

describe('post hoc', () => {
  it('is labelled as not pre-registered, with the reason', () => {
    const postHoc = asPostHoc(
      JSON.parse(
        readFileSync(
          resolve(process.cwd(), '../results/posthoc/long_only.json'),
          'utf8',
        ),
      ),
    )
    render(<PostHoc search={postHoc.searches.ma_crossover!} benchmark="SPY" />)
    const section = screen.getByRole('region', { name: 'Post hoc' })
    expect(within(section).getByText('Not pre-registered')).toBeTruthy()
    expect(
      within(section).getByRole('button', {
        name: 'Why this analysis is post hoc',
      }),
    ).toBeTruthy()
    expect(within(section).getByRole('tooltip').textContent).toMatch(
      /chosen after seeing the pre-registered results/,
    )
    expect(within(section).getByText('0.42')).toBeTruthy()
  })
})
