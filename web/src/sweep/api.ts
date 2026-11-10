import { useEffect, useState } from 'react'
import { asReport, type Report } from '../data.ts'

/** The local API (D016) is reachable only from the dev server, which proxies /api. */
export const API_ENABLED = import.meta.env.DEV

export type Value = boolean | number | string

export interface ParamInfo {
  name: string
  type: 'str' | 'int' | 'float' | 'bool'
  default: Value
  symbol: 'ticker' | 'series' | null
  /** A number whose order means nothing, such as a seed (D019). */
  categorical: boolean
}

export interface StrategyInfo {
  name: string
  description: string
  params: ParamInfo[]
}

export interface SweepRequest {
  strategy: string
  axes: Record<string, Value[]>
  fixed: Record<string, Value>
  categorical: string[]
  start?: string
  end?: string
  costs: { fee_bps: number; slippage_bps: number }
}

export interface SweepStatus {
  id: string
  status: 'queued' | 'running' | 'done' | 'failed'
  n_trials: number
  done: number
  error: string | null
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

/** FastAPI puts a message, or a list of validation errors, in `detail`. */
function detailText(detail: unknown): string | null {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) =>
        [d.loc?.slice(1).join('.'), d.msg].filter(Boolean).join(': '),
      )
      .join('; ')
  }
  return null
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail =
      body && typeof body === 'object' && 'detail' in body
        ? detailText(body.detail)
        : null
    throw new ApiError(
      detail ?? `${response.status} ${response.statusText}`,
      response.status,
    )
  }
  return body as T
}

export const api = {
  strategies: () => call<StrategyInfo[]>('/strategies'),
  createSweep: (body: SweepRequest) =>
    call<{ id: string }>('/sweeps', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  sweep: (id: string) => call<SweepStatus>(`/sweeps/${id}`),
  report: async (id: string): Promise<Report> =>
    asReport(await call<unknown>(`/sweeps/${id}/report`)),
}

export type ApiState =
  | { status: 'off' }
  | { status: 'checking' }
  | { status: 'offline' }
  | { status: 'online'; strategies: StrategyInfo[] }

/** Whether the local API answers; never asked in a static build. */
export function useApi(): ApiState {
  const [state, setState] = useState<ApiState>(
    API_ENABLED ? { status: 'checking' } : { status: 'off' },
  )
  useEffect(() => {
    if (!API_ENABLED) return
    let live = true
    api.strategies().then(
      (strategies) => live && setState({ status: 'online', strategies }),
      () => live && setState({ status: 'offline' }),
    )
    return () => {
      live = false
    }
  }, [])
  return state
}
