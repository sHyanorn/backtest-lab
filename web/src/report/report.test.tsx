import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { asReport, type Report } from '../data.ts'
import { signed, num, pct } from '../format.ts'
import { CheckCards } from './CheckCards.tsx'
import { Overview } from './Overview.tsx'

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
    render(<Overview report={load('ma_crossover')} title="MA" />)
    const panel = screen.getByRole('region', { name: 'Overfitting checks' })
    expect(within(panel).getByText('Borderline')).toBeTruthy()
    expect(within(panel).getByText(/1 of 8 are borderline/)).toBeTruthy()
  })

  it('keeps the benchmark out of the verdict panel', () => {
    render(<Overview report={load('ma_crossover')} title="MA" />)
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
    const { unmount } = render(<Overview report={report} title="M" />)
    expect(screen.getByText('Net of 1 bp fees + 5 bps slippage')).toBeTruthy()
    unmount()
    render(
      <Overview
        report={{ ...report, costs: { fee_bps: 0, slippage_bps: 0 } }}
        title="M"
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
    expect(within(card).getByText('n/a')).toBeTruthy()
    expect(within(card).getByText('Fail')).toBeTruthy()
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
