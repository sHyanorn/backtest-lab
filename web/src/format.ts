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
  return `${bps(costs.fee_bps)} bp fees + ${bps(costs.slippage_bps)} bps slippage`
}

export function count(value: number): string {
  return value.toLocaleString('en-US')
}

export function years(value: number | null | undefined): string {
  if (value === null || value === undefined) return MISSING
  return `${num(value, 1)} y`
}

/** A parameter value as a reader would say it. */
export function paramText(name: string, value: Value): string {
  if (name === 'allow_short') return value ? 'long/short' : 'long only'
  if (typeof value === 'boolean')
    return `${name.replace(/_/g, ' ')} ${value ? 'on' : 'off'}`
  return `${name.replace(/_/g, ' ')} ${value}`
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
