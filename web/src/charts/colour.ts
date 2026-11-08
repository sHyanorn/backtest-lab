export const SEQ_STEPS = 7
export const DIV_HALF = 4

/** A CSS colour step for a value: one blue ramp, or blue/red around zero. */
export function colourScale(values: number[]) {
  const low = Math.min(...values)
  const high = Math.max(...values)
  if (low < 0 && high > 0) {
    const reach = Math.max(-low, high)
    const step = (v: number) => DIV_HALF + Math.round((v / reach) * DIV_HALF)
    return {
      diverging: true,
      low,
      high,
      fill: (v: number) => `var(--div-${step(v)})`,
    }
  }
  const span = high - low || 1
  const step = (v: number) => Math.round(((v - low) / span) * (SEQ_STEPS - 1))
  return {
    diverging: false,
    low,
    high,
    fill: (v: number) => `var(--seq-${step(v)})`,
  }
}
