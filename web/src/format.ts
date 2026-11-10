type Value = boolean | number | string

const MISSING = 'n/a'

const MINUS = '\u2212'

/** A fixed-decimal number with a true minus sign. */
export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return MISSING
  const text = value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
  // A value that rounds to zero carries no sign.
  return /^-0(\.0*)?$/.test(text) ? text.slice(1) : text.replace('-', MINUS)
}

/** A probability; values that round to 1 are shown as above 0.999. */
export function prob(value: number | null | undefined): string {
  if (value === null || value === undefined) return MISSING
  return value >= 0.9995 ? '> 0.999' : num(value, 3)
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return MISSING
  return `${num(value * 100, digits)}%`
}

/** A formatted difference with an explicit sign. */
export function signed(text: string): string {
  if (text === MISSING || text.startsWith(MINUS)) return text
  return /^0(\.0+)?(%| |$)/.test(text) ? text : `+${text}`
}

export function costText(costs: {
  fee_bps: number
  slippage_bps: number
}): string {
  const bps = (v: number) => num(v, Number.isInteger(v) ? 0 : 1)
  return `${bps(costs.fee_bps)} bp fees + ${bps(costs.slippage_bps)} bps slippage per side`
}

export function count(value: number): string {
  return value.toLocaleString('en-US')
}

export function years(value: number | null | undefined): string {
  if (value === null || value === undefined) return MISSING
  return `${num(value, 1)} y`
}

const TITLES: Record<string, string> = {
  ma_crossover: 'Moving-average crossover',
  momentum: 'Simplified time-series momentum',
  random_signal: 'Random-signal control',
  mean_reversion: 'Mean reversion',
  rate_rotation: 'Rate rotation',
}

/** A registry name as a heading. */
export function strategyTitle(name: string): string {
  return TITLES[name] ?? paramLabel(name)
}

/** A parameter name as a form label. */
export function paramLabel(name: string): string {
  const words = name.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** A parameter value as a reader would say it. */
export function paramText(name: string, value: Value): string {
  if (name === 'allow_short') return value ? 'long/short' : 'long only'
  const words = name.replace(/_/g, ' ')
  if (typeof value === 'boolean') return `${words} ${value ? 'on' : 'off'}`
  return `${words} ${value}`
}

/** The parameters that vary in the grid, in grid order. */
export function settingText(
  params: Record<string, Value>,
  grid: Record<string, unknown>,
): string {
  const names = Object.keys(grid).filter((name) => name in params)
  return names.map((name) => paramText(name, params[name] as Value)).join(' · ')
}

const dateFormat = new Intl.DateTimeFormat('en-US', {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  timeZone: 'UTC',
})

export function date(iso: string): string {
  return dateFormat.format(new Date(`${iso}T00:00:00Z`))
}

/** The parameters of a trial; trials enumerate the grid with the last axis fastest (D023). */
export function trialParams(
  grid: Record<string, Value[]>,
  fixed: Record<string, Value>,
  trial: number,
): Record<string, Value> {
  const params: Record<string, Value> = { ...fixed }
  let rest = trial
  for (const [name, values] of Object.entries(grid).reverse()) {
    params[name] = values[rest % values.length] as Value
    rest = Math.floor(rest / values.length)
  }
  return params
}
