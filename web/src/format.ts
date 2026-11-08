type Value = boolean | number | string

const MISSING = 'n/a'

export function num(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return MISSING
  return value.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return MISSING
  return `${num(value * 100, digits)}%`
}

/** Signed difference, with a true minus sign. */
export function signed(text: string): string {
  if (text === MISSING) return text
  return text.startsWith('-') ? `−${text.slice(1)}` : `+${text}`
}

export function minus(text: string): string {
  return text.startsWith('-') ? `−${text.slice(1)}` : text
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
