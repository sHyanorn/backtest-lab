import { describe, expect, it } from 'vitest'
import type { ParamInfo, StrategyInfo } from './api.ts'
import { buildRequest, parseValues, type FormState } from './form.ts'

const int: ParamInfo = { name: 'fast', type: 'int', default: 50, symbol: null }
const ticker: ParamInfo = {
  name: 'ticker',
  type: 'str',
  default: 'SPY',
  symbol: 'ticker',
}
const flag: ParamInfo = {
  name: 'allow_short',
  type: 'bool',
  default: false,
  symbol: null,
}
const strategy: StrategyInfo = {
  name: 'ma_crossover',
  description: '',
  params: [ticker, int, { ...int, name: 'slow', default: 200 }, flag],
}

function form(
  texts: Record<string, string>,
  extra: Partial<FormState> = {},
): FormState {
  return {
    strategy,
    texts: {
      ticker: 'SPY',
      fast: '50',
      slow: '200',
      allow_short: 'false',
      ...texts,
    },
    start: '',
    end: '',
    fee: '1',
    slippage: '5',
    ...extra,
  }
}

describe('parseValues', () => {
  it('reads one value or a list', () => {
    expect(parseValues(int, '10')).toEqual({ values: [10] })
    expect(parseValues(int, '10, 20,50')).toEqual({ values: [10, 20, 50] })
    expect(parseValues(flag, 'false, true')).toEqual({ values: [false, true] })
    expect(parseValues(ticker, 'qqq')).toEqual({ values: ['QQQ'] })
  })

  it('rejects what the grid search would reject', () => {
    expect(parseValues(int, '1.5')).toEqual({
      error: '1.5 is not a whole number',
    })
    expect(parseValues(int, '20, 10')).toEqual({
      error: 'List numbers in increasing order',
    })
    expect(parseValues(int, '10, 10')).toEqual({ error: 'Values repeat' })
    expect(parseValues(int, '')).toEqual({ error: 'Enter a value' })
    expect(parseValues(ticker, 'SPY, QQQ')).toEqual({ error: 'One value only' })
  })
})

describe('buildRequest', () => {
  it('makes listed parameters axes and keeps default costs', () => {
    const built = buildRequest(
      form({ fast: '10, 20', slow: '100, 200', allow_short: 'false, true' }),
    )
    expect(built).toMatchObject({
      ok: true,
      trials: 8,
      request: {
        strategy: 'ma_crossover',
        axes: { fast: [10, 20], slow: [100, 200], allow_short: [false, true] },
        fixed: { ticker: 'SPY' },
        costs: { fee_bps: 1, slippage_bps: 5 },
      },
    })
  })

  it('needs at least one axis and at most 500 settings', () => {
    expect(buildRequest(form({}))).toMatchObject({
      ok: false,
      errors: { grid: expect.any(String) },
    })
    const many = Array.from({ length: 30 }, (_, i) => i + 1).join(',')
    expect(buildRequest(form({ fast: many, slow: many }))).toMatchObject({
      ok: false,
      trials: 900,
    })
  })

  it('rejects negative costs and an empty date range', () => {
    const built = buildRequest(
      form(
        { fast: '10, 20' },
        { fee: '-1', start: '2020-01-01', end: '2019-01-01' },
      ),
    )
    expect(built).toMatchObject({
      ok: false,
      errors: { fee: expect.any(String), end: expect.any(String) },
    })
  })
})
