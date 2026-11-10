import { useRef, type ReactNode } from 'react'
import { Columns } from '../charts/Columns.tsx'
import { count, date, num, pct, settingText, trialParams } from '../format.ts'
import type { Report } from '../report.gen.ts'
import type { CheckKey } from './checks.ts'
import { TableToggle } from '../TableToggle.tsx'

type Strategy = Report['strategy']

/** A "Details" button that opens the check's charts and tables in a modal dialog. */
export function DetailsButton({
  report,
  check,
}: {
  report: Report
  check: CheckKey
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const title = report.checks[check].title
  return (
    <>
      <button
        type="button"
        className="text-button"
        onClick={() => dialog.current?.showModal()}
      >
        Details
        <span className="visually-hidden"> of {title}</span>
      </button>
      <dialog
        ref={dialog}
        className="dialog"
        aria-labelledby={`${check}-dialog-title`}
        onClick={(e) => e.target === e.currentTarget && e.currentTarget.close()}
      >
        <div className="dialog-body">
          <div className="dialog-head">
            <h2 id={`${check}-dialog-title`}>{title}</h2>
            <button
              type="button"
              className="icon-button"
              aria-label="Close"
              onClick={() => dialog.current?.close()}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 14 14"
                aria-hidden="true"
              >
                <path
                  d="m3 3 8 8m0-8-8 8"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <p className="dialog-summary">{report.checks[check].summary}</p>
          <Body report={report} check={check} />
        </div>
      </dialog>
    </>
  )
}

function Body({ report, check }: { report: Report; check: CheckKey }) {
  const setting = (trial: number) => settingOf(report.strategy, trial)
  switch (check) {
    case 'holdout': {
      const { metrics, details } = report.checks.holdout
      return (
        <dl className="facts">
          <Fact name="Split date">{date(metrics.split_date)}</Fact>
          <Fact name="In-sample share">{pct(details.fraction, 0)}</Fact>
          <Fact name="Picked in sample">
            {settingText(details.params, report.strategy.grid)}
          </Fact>
          <Fact name="Sharpe in sample">{num(metrics.is_sharpe)}</Fact>
          <Fact name="Sharpe out of sample">{num(metrics.oos_sharpe)}</Fact>
          <Fact name="Retention">{pct(metrics.retention, 0)}</Fact>
        </dl>
      )
    }
    case 'walk_forward': {
      const { windows, is_days, oos_days } = report.checks.walk_forward.details
      return (
        <>
          <p className="note">
            Out-of-sample Sharpe ratio of each {oos_days}-day window, picked on
            the {is_days} days before it
          </p>
          <Columns
            label="Out-of-sample Sharpe ratio by walk-forward window"
            format={(v) => num(v, 1)}
            columns={windows.map((w) => ({
              label: w.oos_start.slice(0, 4),
              value: w.oos_sharpe,
              detail: `${date(w.oos_start)} to ${date(w.oos_end)} · ${setting(w.trial)}`,
              tone: 'accent',
            }))}
          />
          <Table
            label="Walk-forward windows"
            head={[
              'Out of sample',
              'Picked setting',
              'IS Sharpe',
              'OOS Sharpe',
            ]}
            rows={windows.map((w) => [
              `${w.oos_start} to ${w.oos_end}`,
              setting(w.trial),
              num(w.is_sharpe),
              num(w.oos_sharpe),
            ])}
          />
        </>
      )
    }
    case 'purged_cv': {
      const { metrics, details } = report.checks.purged_cv
      return (
        <>
          <p className="note">
            Held-out Sharpe ratio of each fold; {metrics.embargo_days} days
            embargoed after each test fold
          </p>
          <Columns
            label="Test-fold Sharpe ratio by fold"
            format={(v) => num(v, 1)}
            columns={details.folds.map((f, i) => ({
              label: String(i + 1),
              value: f.test_sharpe,
              detail: `Fold ${i + 1} · ${date(f.test_start)} to ${date(f.test_end)} · ${setting(f.trial)}`,
              tone: 'accent',
            }))}
          />
          <Table
            label="Purged cross-validation folds"
            head={[
              'Test fold',
              'Training days',
              'Picked setting',
              'Train Sharpe',
              'Test Sharpe',
            ]}
            rows={details.folds.map((f) => [
              `${f.test_start} to ${f.test_end}`,
              count(f.n_train),
              setting(f.trial),
              num(f.train_sharpe),
              num(f.test_sharpe),
            ])}
          />
        </>
      )
    }
    case 'pbo': {
      const { metrics, details } = report.checks.pbo
      const { edges, counts } = details.logits
      // The edges are symmetric about zero, but the centre one can be off by an ulp.
      const half = counts.length / 2
      return (
        <>
          <p className="note">
            Rank logit of the in-sample winner out of sample, over{' '}
            {count(metrics.n_combinations)} splits; below zero it ranked in the
            bottom half
          </p>
          <Columns
            label="Histogram of the out-of-sample rank logits"
            format={(v) => count(Math.round(v))}
            marker={{ before: half, label: '0' }}
            columns={counts.map((c, i) => {
              const from = edges[i] ?? 0
              const to = edges[i + 1] ?? 0
              return {
                label: num((from + to) / 2, 1),
                value: c,
                detail: `Logit ${num(from, 2)} to ${num(to, 2)}`,
                tone: i < half ? 'accent' : 'ref',
              }
            })}
          />
          <p className="axis-caption">Rank logit, centre of each bin</p>
          <Table
            label="Logit histogram"
            head={['Logit', 'Splits', 'Share']}
            rows={counts.map((c, i) => [
              `${num(edges[i], 2)} to ${num(edges[i + 1], 2)}`,
              count(c),
              pct(c / metrics.n_combinations),
            ])}
          />
          <dl className="facts">
            <Fact name="PBO">{num(metrics.pbo, 3)}</Fact>
            <Fact name="Blocks">{metrics.n_blocks}</Fact>
            <Fact name="Degradation slope">
              {num(metrics.degradation_slope)}
            </Fact>
            <Fact name="Chance of an OOS loss">
              {pct(metrics.prob_oos_loss, 0)}
            </Fact>
          </dl>
        </>
      )
    }
    default:
      return null
  }
}

function settingOf(strategy: Strategy, trial: number): string {
  return settingText(
    trialParams(strategy.grid, strategy.fixed, trial),
    strategy.grid,
  )
}

function Fact({ name, children }: { name: string; children: ReactNode }) {
  return (
    <div>
      <dt>{name}</dt>
      <dd>{children}</dd>
    </div>
  )
}

function Table({
  label,
  head,
  rows,
}: {
  label: string
  head: string[]
  rows: string[][]
}) {
  return (
    <TableToggle label={label}>
      <thead>
        <tr>
          {head.map((h) => (
            <th scope="col" key={h}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {r.map((c, j) =>
              j === 0 ? (
                <th scope="row" key={j}>
                  {c}
                </th>
              ) : (
                <td key={j}>{c}</td>
              ),
            )}
          </tr>
        ))}
      </tbody>
    </TableToggle>
  )
}
