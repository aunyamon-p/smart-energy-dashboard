const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export type AlertStatus = 'New' | 'Acknowledged' | 'Resolved'
export type Severity = 'High' | 'Medium' | 'Low'
export type LoadType = 'AC' | 'Light' | 'Plug'

export type DashboardSummary = {
  period: { start: string | null; end: string | null }
  timezone: string
  actual_energy_kwh: number
  expected_energy_kwh: number
  excess_energy_kwh: number
  potential_anomaly_event_count: number
  severity_counts: Record<string, number>
  missing_observations: number
  partial_component_observations: number
  estimated_cost: null
  cost_status: 'not_configured'
  weather_context: { source: string; timezone: string; status: string; note: string } | null
}

export type EnergyRow = {
  date: string
  floor: string
  zone: string
  load_type: LoadType
  actual_energy_kwh: number | null
  expected_energy_kwh: number | null
  excess_energy_kwh: number | null
  observations: number
  missing_observations: number
  partial_component_observations: number
}

export type RealtimeEnergyRow = {
  source_id: string
  timestamp: string
  floor: string
  zone: string
  load_type: LoadType
  actual_kw: number
  actual_kwh: number
  anomaly_detected: boolean
  alert_id: string | null
}

export type Alert = {
  alert_id: string
  created_at: string
  floor: string
  zone: string
  load_type: LoadType
  start_timestamp: string
  end_timestamp: string
  duration_minutes: number
  evidence_points: number
  actual_kw_peak: number
  expected_kw_at_peak: number
  excess_kw_peak: number
  excess_energy_kwh: number
  severity: Severity
  reason: string
  status: AlertStatus
  classification: 'Potential Anomaly'
}

export type AlertDetail = Alert & {
  evidence: Array<{
    point_alert_id: string
    timestamp: string
    actual_kw: number
    expected_kw: number
    excess_kw: number
    actual_kwh: number
    expected_kwh: number
    excess_kwh: number
    severity: Severity
    reason: string
    status: AlertStatus
    robust_score: number
  }>
  weather_context: {
    status: string
    source: string
    timezone: string
    timestamp: string | null
    temperature_2m_c: number | null
    relative_humidity_2m_pct: number | null
    ac_context: { ac_power_kw: number | null; valid_minute_count: number | null; missing_minute_count: number | null } | null
    reason?: string | null
  } | null
}

export type WeatherPoint = {
  floor: string
  zone: string
  timestamp: string
  ac_power_kw: number | null
  valid_minute_count: number | null
  expected_minute_count: number | null
  missing_minute_count: number | null
  temperature_2m_c: number | null
  relative_humidity_2m_pct: number | null
  join_status: string
}

type Page<T> = { data: T[]; pagination: { page: number; page_size: number; total: number }; timezone?: string }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Request failed (${response.status})`)
  }
  return response.json() as Promise<T>
}

function query(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value))
  })
  return search.toString()
}

export const api = {
  summary: (params: Record<string, string | undefined>) => request<DashboardSummary>(`/api/dashboard/summary?${query(params)}`),
  energy: (params: Record<string, string | number | undefined>) => request<Page<EnergyRow>>(`/api/energy?${query({ ...params, page_size: 200 })}`),
  realtimeEnergy: (params: Record<string, string | number | undefined>) => request<Page<RealtimeEnergyRow> & { timezone: string }>(`/api/energy/realtime?${query({ ...params, page_size: 200 })}`),
  alerts: (params: Record<string, string | number | undefined>) => request<Page<Alert>>(`/api/alerts?${query({ ...params, page_size: params.page_size ?? 100 })}`),
  alert: (id: string) => request<{ data: AlertDetail }>(`/api/alerts/${encodeURIComponent(id)}`),
  updateAlert: (id: string, status: AlertStatus) => request<Alert>(`/api/alerts/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  weatherAc: (params: Record<string, string | number | undefined>) => request<Page<WeatherPoint> & { source: string; note: string }>(`/api/analytics/weather-ac?${query({ ...params, page_size: 200 })}`),
}
