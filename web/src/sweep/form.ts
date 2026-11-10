import type { ParamInfo, StrategyInfo, SweepRequest, Value } from './api.ts'

export const MAX_TRIALS = 500 // the API's limit (D017)

export type Parsed = { values: Value[] } | { error: string }

/** A field's text as one value, or a comma-separated list of values to search. */
export function parseValues(param: ParamInfo, text: string): Parsed {
  const parts = text
    .split(',')
    .map((p) => p.trim())
    .filter((p) => p !== '')
  if (parts.length === 0) return { error: 'Enter a value' }
  const values: Value[] = []
  for (const part of parts) {
    if (param.type === 'str') {
      values.push(param.symbol === 'ticker' ? part.toUpperCase() : part)
    } else if (param.type === 'bool') {
      if (part !== 'true' && part !== 'false')
        return { error: 'Use true or false' }
      values.push(part === 'true')
    } else {
      const n = Number(part)
      if (!Number.isFinite(n)) return { error: `${part} is not a number` }
      if (param.type === 'int' && !Number.isInteger(n)) {
        return { error: `${part} is not a whole number` }
      }
      values.push(n)
    }
  }
  if (param.type === 'str' && values.length > 1)
    return { error: 'One value only' }
  if (new Set(values).size !== values.length) return { error: 'Values repeat' }
  if (values.length > 1 && param.type !== 'str' && param.type !== 'bool') {
    const sorted = values as number[]
    if (sorted.some((v, i) => i > 0 && v <= (sorted[i - 1] as number))) {
      return { error: 'List numbers in increasing order' }
    }
  }
  return { values }
}

export function defaultText(param: ParamInfo): string {
  return String(param.default)
}

export interface FormState {
  strategy: StrategyInfo
  texts: Record<string, string>
  start: string
  end: string
  fee: string
  slippage: string
}

export type Built =
  | { ok: true; request: SweepRequest; trials: number }
  | { ok: false; errors: Record<string, string>; trials: number }

/** A sweep request: parameters with several values become grid axes. */
export function buildRequest(form: FormState): Built {
  const errors: Record<string, string> = {}
  const axes: Record<string, Value[]> = {}
  const fixed: Record<string, Value> = {}
  for (const param of form.strategy.params) {
    const parsed = parseValues(param, form.texts[param.name] ?? '')
    if ('error' in parsed) errors[param.name] = parsed.error
    else if (parsed.values.length > 1) axes[param.name] = parsed.values
    else fixed[param.name] = parsed.values[0] as Value
  }
  const categorical = form.strategy.params
    .filter((p) => p.categorical && p.name in axes)
    .map((p) => p.name)
  const trials = Object.values(axes).reduce((n, v) => n * v.length, 1)
  const fee = Number(form.fee)
  const slippage = Number(form.slippage)
  if (form.fee === '' || !(fee >= 0)) errors.fee = 'Enter 0 or more'
  if (form.slippage === '' || !(slippage >= 0))
    errors.slippage = 'Enter 0 or more'
  if (form.start && form.end && form.start >= form.end)
    errors.end = 'End after the start'
  if (Object.keys(axes).length === 0 && Object.keys(errors).length === 0) {
    errors.grid = 'List two or more values for at least one parameter'
  }
  if (trials > MAX_TRIALS)
    errors.grid = `${trials} settings; the limit is ${MAX_TRIALS}`
  if (Object.keys(errors).length > 0) return { ok: false, errors, trials }
  return {
    ok: true,
    trials,
    request: {
      strategy: form.strategy.name,
      axes,
      fixed,
      categorical,
      ...(form.start ? { start: form.start } : {}),
      ...(form.end ? { end: form.end } : {}),
      costs: { fee_bps: fee, slippage_bps: slippage },
    },
  }
}
