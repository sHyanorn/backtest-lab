import { useEffect, useId, useState, type FormEvent } from 'react'
import type { Report } from '../data.ts'
import { InfoTip } from '../InfoTip.tsx'
import { count, paramLabel, strategyTitle } from '../format.ts'
import { ReportView } from '../report/ReportView.tsx'
import { api, ApiError, type StrategyInfo, type SweepStatus } from './api.ts'
import { buildRequest, defaultText, type FormState } from './form.ts'

const POLL_MS = 1000
// Polling gives up after this many network errors in a row.
const MAX_FAILURES = 5

type Run =
  | { id: string; status: 'running'; sweep?: SweepStatus }
  | { id: string; status: 'done'; report: Report }
  | { id: string; status: 'error'; message: string }

function initial(strategy: StrategyInfo): FormState {
  return {
    strategy,
    texts: Object.fromEntries(
      strategy.params.map((p) => [p.name, defaultText(p)]),
    ),
    start: '',
    end: '',
    fee: '1',
    slippage: '5',
  }
}

/** The sweep in the URL, as last polled; running until a poll answers. */
function currentRun(sweepId: string | null, polled: Run | null): Run | null {
  if (sweepId === null) return null
  if (polled?.id === sweepId) return polled
  return { id: sweepId, status: 'running' }
}

/** The sweep in the URL (#/sweep/<id>) survives a tab switch or a reload. */
export default function SweepView({
  strategies,
  sweepId,
}: {
  strategies: StrategyInfo[]
  sweepId: string | null
}) {
  const [form, setForm] = useState<FormState>(() =>
    initial(strategies[0] as StrategyInfo),
  )
  const [sending, setSending] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [polled, setPolled] = useState<Run | null>(null)
  const [touched, setTouched] = useState(false)
  const built = buildRequest(form)
  const errors = built.ok ? {} : built.errors
  const shownErrors = touched ? errors : {}
  const zeroCost = Number(form.fee) === 0 && Number(form.slippage) === 0
  const run = currentRun(sweepId, polled)
  const busy = sending || run?.status === 'running'
  const id = useId()

  // Poll the sweep until it finishes, then fetch its report.
  useEffect(() => {
    if (sweepId === null) return
    let live = true
    let failures = 0
    let timer: ReturnType<typeof setTimeout> | undefined
    async function tick(job: string) {
      try {
        const sweep = await api.sweep(job)
        failures = 0
        if (!live) return
        if (sweep.status === 'failed') {
          setPolled({
            id: job,
            status: 'error',
            message: sweep.error ?? 'The sweep failed',
          })
          return
        }
        if (sweep.status === 'done') {
          const report = await api.report(job)
          if (live) setPolled({ id: job, status: 'done', report })
          return
        }
        setPolled({ id: job, status: 'running', sweep })
      } catch (error) {
        if (!live) return
        failures += 1
        // A client error, such as an unknown id, will not go away on its own.
        const permanent = error instanceof ApiError && error.status < 500
        if (permanent || failures >= MAX_FAILURES) {
          setPolled({
            id: job,
            status: 'error',
            message: (error as Error).message,
          })
          return
        }
      }
      if (live) timer = setTimeout(() => void tick(job), POLL_MS)
    }
    void tick(sweepId)
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [sweepId])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setTouched(true)
    if (!built.ok) return
    setSending(true)
    setSubmitError(null)
    try {
      const { id: created } = await api.createSweep(built.request)
      window.location.assign(`#/sweep/${created}`)
    } catch (error) {
      setSubmitError((error as Error).message)
    } finally {
      setSending(false)
    }
  }

  const set = (patch: Partial<FormState>) =>
    setForm((f) => ({ ...f, ...patch }))

  return (
    <div className="view">
      <form className="panel sweep-form" onSubmit={submit} noValidate>
        <label className="field strategy-field">
          <span>Strategy</span>
          <select
            value={form.strategy.name}
            onChange={(e) => {
              const next = strategies.find((s) => s.name === e.target.value)
              if (next) setForm(initial(next))
            }}
          >
            {strategies.map((s) => (
              <option key={s.name} value={s.name}>
                {strategyTitle(s.name)}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="sweep-group">
          <legend>
            Parameters
            <InfoTip label="How to search a parameter">
              Separate values with commas to search over them, for example 10,
              20, 50. Every combination is one setting.
            </InfoTip>
          </legend>
          <div className="sweep-grid">
            {form.strategy.params.map((p) => {
              const error = shownErrors[p.name]
              const text = form.texts[p.name] ?? ''
              const update = (value: string) =>
                set({ texts: { ...form.texts, [p.name]: value } })
              return (
                <label className="field" key={p.name}>
                  <span>{paramLabel(p.name)}</span>
                  {p.type === 'bool' ? (
                    <select
                      value={text}
                      onChange={(e) => update(e.target.value)}
                    >
                      <option value="false">false</option>
                      <option value="true">true</option>
                      <option value="false, true">both</option>
                    </select>
                  ) : (
                    <input
                      value={text}
                      inputMode={p.type === 'str' ? 'text' : 'decimal'}
                      autoCapitalize={
                        p.symbol === 'ticker' ? 'characters' : 'off'
                      }
                      spellCheck={false}
                      aria-invalid={error ? true : undefined}
                      aria-describedby={error ? `${id}-${p.name}` : undefined}
                      onChange={(e) => update(e.target.value)}
                    />
                  )}
                  {error && (
                    <small className="field-error" id={`${id}-${p.name}`}>
                      {error}
                    </small>
                  )}
                </label>
              )
            })}
          </div>
        </fieldset>
        <fieldset className="sweep-group">
          <legend>Sample and costs</legend>
          <div className="sweep-grid">
            <label className="field">
              <span>Start</span>
              <input
                type="date"
                value={form.start}
                onChange={(e) => set({ start: e.target.value })}
              />
            </label>
            <label className="field">
              <span>End</span>
              <input
                type="date"
                value={form.end}
                aria-invalid={shownErrors.end ? true : undefined}
                onChange={(e) => set({ end: e.target.value })}
              />
              {shownErrors.end && (
                <small className="field-error">{shownErrors.end}</small>
              )}
            </label>
            <label className="field">
              <span>Fees, bps</span>
              <input
                value={form.fee}
                inputMode="decimal"
                aria-invalid={shownErrors.fee ? true : undefined}
                onChange={(e) => set({ fee: e.target.value })}
              />
              {shownErrors.fee && (
                <small className="field-error">{shownErrors.fee}</small>
              )}
            </label>
            <label className="field">
              <span>Slippage, bps</span>
              <input
                value={form.slippage}
                inputMode="decimal"
                aria-invalid={shownErrors.slippage ? true : undefined}
                onChange={(e) => set({ slippage: e.target.value })}
              />
              {shownErrors.slippage && (
                <small className="field-error">{shownErrors.slippage}</small>
              )}
            </label>
          </div>
        </fieldset>
        <div className="sweep-foot">
          <span className="sweep-count" aria-live="polite">
            {errors.grid ? (
              <span className={touched ? 'field-error' : 'muted'}>
                {errors.grid}
              </span>
            ) : !built.ok ? (
              <span className="muted">Fix the marked fields</span>
            ) : (
              <>
                {count(built.trials)}{' '}
                {built.trials === 1 ? 'setting' : 'settings'}
              </>
            )}
            {zeroCost && <span className="cost zero">Zero-cost reference</span>}
          </span>
          <button className="primary" type="submit" disabled={busy}>
            {busy ? 'Running…' : 'Run sweep'}
          </button>
        </div>
      </form>
      {submitError && (
        <p className="error" role="alert">
          {submitError}
        </p>
      )}
      {run && <Progress run={run} />}
      {run?.status === 'done' && (
        <ReportView
          report={run.report}
          title={`${strategyTitle(run.report.strategy.name)} sweep`}
          kind="Exploratory"
        />
      )}
    </div>
  )
}

function Progress({ run }: { run: Run }) {
  if (run.status === 'error') {
    return (
      <p className="error" role="alert">
        {run.message}
      </p>
    )
  }
  if (run.status !== 'running') return null
  const sweep = run.sweep
  const total = sweep?.n_trials ?? 1
  const done = sweep?.done ?? 0
  const label =
    sweep === undefined || sweep.status === 'queued'
      ? 'Queued'
      : done < total
        ? `${count(done)} of ${count(total)} settings`
        : 'Building the report'
  return (
    <div className="progress" role="status">
      <span>{label}</span>
      <progress max={total} value={done} aria-label="Sweep progress" />
    </div>
  )
}
