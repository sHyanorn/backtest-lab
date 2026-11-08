import { useEffect, useId, useState, type FormEvent } from 'react'
import { ReportView } from '../DemoView.tsx'
import type { Report } from '../data.ts'
import { InfoTip } from '../InfoTip.tsx'
import { count, paramLabel, strategyTitle } from '../format.ts'
import { api, type StrategyInfo, type SweepStatus } from './api.ts'
import { buildRequest, defaultText, type FormState } from './form.ts'

const POLL_MS = 1000

type Run =
  | { status: 'idle' }
  | { status: 'sending' }
  | { status: 'running'; sweep: SweepStatus }
  | { status: 'done'; report: Report }
  | { status: 'error'; message: string }

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

export default function SweepView({
  strategies,
}: {
  strategies: StrategyInfo[]
}) {
  const [form, setForm] = useState<FormState>(() =>
    initial(strategies[0] as StrategyInfo),
  )
  const [run, setRun] = useState<Run>({ status: 'idle' })
  const [touched, setTouched] = useState(false)
  const built = buildRequest(form)
  const errors = built.ok ? {} : built.errors
  const shownErrors = touched ? errors : {}
  const zeroCost = Number(form.fee) === 0 && Number(form.slippage) === 0
  const busy = run.status === 'sending' || run.status === 'running'
  const id = useId()

  // Poll the running sweep until it finishes, then fetch its report.
  const sweepId = run.status === 'running' ? run.sweep.id : null
  useEffect(() => {
    if (sweepId === null) return
    let live = true
    const timer = setInterval(async () => {
      try {
        const sweep = await api.sweep(sweepId)
        if (!live) return
        if (sweep.status === 'failed') {
          setRun({
            status: 'error',
            message: sweep.error ?? 'The sweep failed',
          })
        } else if (sweep.status === 'done') {
          const report = await api.report(sweepId)
          if (live) setRun({ status: 'done', report })
        } else {
          setRun({ status: 'running', sweep })
        }
      } catch (error) {
        if (live)
          setRun({ status: 'error', message: String((error as Error).message) })
      }
    }, POLL_MS)
    return () => {
      live = false
      clearInterval(timer)
    }
  }, [sweepId])

  async function submit(event: FormEvent) {
    event.preventDefault()
    setTouched(true)
    if (!built.ok) return
    setRun({ status: 'sending' })
    try {
      const { id: created } = await api.createSweep(built.request)
      setRun({
        status: 'running',
        sweep: {
          id: created,
          status: 'queued',
          n_trials: built.trials,
          done: 0,
          error: null,
        },
      })
    } catch (error) {
      setRun({ status: 'error', message: (error as Error).message })
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
      <Progress run={run} />
      {run.status === 'done' && (
        <ReportView
          report={run.report}
          title={`${strategyTitle(run.report.strategy.name)} sweep`}
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
  if (run.status !== 'running' && run.status !== 'sending') return null
  const sweep = run.status === 'running' ? run.sweep : null
  const total = sweep?.n_trials ?? 1
  const done = sweep?.done ?? 0
  const label =
    sweep === null || sweep.status === 'queued'
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
