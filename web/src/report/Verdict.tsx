import type { CheckVerdict as V } from '../report.gen.ts'
import { VERDICT_LABEL } from './checks.ts'

/** A status glyph on its status fill; the label beside it carries the meaning. */
export function VerdictIcon({
  verdict,
  size = 16,
}: {
  verdict: V
  size?: number
}) {
  return (
    <svg
      className={`verdict-icon ${verdict}`}
      width={size}
      height={size}
      viewBox="0 0 16 16"
      aria-hidden="true"
    >
      <circle cx="8" cy="8" r="8" />
      {verdict === 'green' && <path d="M4.6 8.3 7 10.6l4.4-4.9" />}
      {verdict === 'yellow' && <path d="M8 4.2v4.6M8 11.6v.1" />}
      {verdict === 'red' && <path d="m5.3 5.3 5.4 5.4m0-5.4-5.4 5.4" />}
      {verdict === 'not_assessable' && <path d="M5 8h6" />}
    </svg>
  )
}

export function Verdict({ verdict, size }: { verdict: V; size?: number }) {
  return (
    <span className={`verdict ${verdict}`}>
      <VerdictIcon verdict={verdict} size={size} />
      {VERDICT_LABEL[verdict]}
    </span>
  )
}
