import { useEffect, useMemo, useState } from 'react'
import { NavLink, Route, Routes, useNavigate, useParams } from 'react-router-dom'
import { AlertTriangle, ChevronLeft, Clock3, Leaf, LayoutDashboard, Search, SlidersHorizontal, Thermometer, Zap } from 'lucide-react'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from './api'
import type { Alert, AlertDetail as AlertDetailType, AlertStatus, DashboardSummary, EnergyRow, LoadType, RealtimeEnergyRow, Severity } from './api'

function getBangkokToday() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Bangkok',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(new Date())
  const values = Object.fromEntries(parts.map(part => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

const INITIAL_FILTERS = { start_date: '2018-07-01', end_date: getBangkokToday(), floor: '', zone: '', load_type: '' }
const ALERT_PAGE_SIZE = 100
const BANGKOK_TIME_ZONE = 'Asia/Bangkok'
const floors = ['Floor1', 'Floor2']
const zones = ['z1', 'z2', 'z3', 'z4']
const loads: LoadType[] = ['AC', 'Light', 'Plug']

function App() {
  return <div className="app-shell"><Sidebar /><main className="main-area"><header className="topbar"><div className="breadcrumb"><span>Workspace</span><span className="crumb-divider">/</span><strong>Energy Monitoring</strong></div></header><div className="page-content"><Routes><Route path="/" element={<Overview />} /><Route path="/analytics/weather" element={<WeatherAnalytics />} /><Route path="/alerts" element={<AlertsPage />} /><Route path="/alerts/:id" element={<AlertDetail />} /><Route path="*" element={<Overview />} /></Routes></div><footer className="footer"><span>Smart Energy Intelligence System</span><span>CU-BEMS · Open-Meteo contextual data</span></footer></main></div>
}

function Sidebar() {
  return <aside className="sidebar"><div className="brand"><div className="brand-mark"><Zap size={21} fill="currentColor" /></div><div><strong>ENERGY<span>IQ</span></strong><small>INTELLIGENCE PLATFORM</small></div></div><div className="workspace-label">WORKSPACE</div><nav className="side-nav"><NavLink to="/" end className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}><LayoutDashboard size={18} />Overview</NavLink><NavLink to="/analytics/weather" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}><Thermometer size={18} />Weather & AC</NavLink><NavLink to="/alerts" className={({ isActive }) => isActive || location.pathname.startsWith('/alerts/') ? 'nav-item active' : 'nav-item'}><AlertTriangle size={18} />Alerts</NavLink></nav><div className="sidebar-bottom"><div className="eco-card"><div className="eco-icon"><Leaf size={18} /></div><strong>Smarter energy,<br />better tomorrow.</strong><p>Monitor actual and expected usage from CU-BEMS.</p></div></div></aside>
}

function PageHeading({ eyebrow, title, subtitle, children }: { eyebrow: string; title: string; subtitle: string; children?: React.ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>{children}</div>
}

function ErrorState({ error }: { error: string }) { return <div className="state-card error-state"><AlertTriangle size={22} /><strong>Unable to load data</strong><span>{error}</span></div> }
function LoadingState() { return <div className="state-card"><span className="spinner" />Loading live data…</div> }
function EmptyState({ message = 'No data matches these filters.' }: { message?: string }) { return <div className="state-card muted">{message}</div> }
function formatNumber(value: number | null | undefined, digits = 1) { return value == null ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: digits }) }
function formatTimestamp(value: string) { return new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Bangkok', hourCycle: 'h23' }).format(new Date(value)) }
function formatTrendAxis(timestamp: number) {
  return new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: BANGKOK_TIME_ZONE,
  }).format(timestamp)
}
function formatTrendTooltip(timestamp: number) {
  const formatted = new Intl.DateTimeFormat('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: BANGKOK_TIME_ZONE,
  }).format(timestamp)
  return `${formatted} (${BANGKOK_TIME_ZONE})`
}

function FilterBar({ value, onChange, includeLoad = true, children, className = '' }: { value: typeof INITIAL_FILTERS; onChange: (value: typeof INITIAL_FILTERS) => void; includeLoad?: boolean; children?: React.ReactNode; className?: string }) {
  const update = (key: keyof typeof INITIAL_FILTERS, next: string) => onChange({ ...value, [key]: next })
  return <div className={`filter-bar ${className}`}><div className="filter-intro"><SlidersHorizontal size={16} /><strong>Filters</strong></div><label className="filter-select"><span>Start date</span><input type="date" value={value.start_date} onChange={e => update('start_date', e.target.value)} /></label><label className="filter-select"><span>End date</span><input type="date" value={value.end_date} onChange={e => update('end_date', e.target.value)} /></label><SelectFilter label="Floor" value={value.floor} options={floors} onChange={next => update('floor', next)} /><SelectFilter label="Zone" value={value.zone} options={zones} onChange={next => update('zone', next)} />{includeLoad && <SelectFilter label="Load type" value={value.load_type} options={loads} onChange={next => update('load_type', next)} />}{children}</div>
}
function SelectFilter({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (value: string) => void }) {
  return <label className="filter-select"><span>{label}</span><select value={value} onChange={e => onChange(e.target.value)}><option value="">All</option>{options.map(option => <option key={option}>{option}</option>)}</select></label>
}
function MetricCard({ title, value, unit, icon, tint }: { title: string; value: string; unit: string; icon: React.ReactNode; tint: string }) { return <div className="metric-card"><div className="metric-top"><span>{title}</span><div className={`metric-icon ${tint}`}>{icon}</div></div><div className="metric-value">{value}<small>{unit}</small></div></div> }
function SeverityBadge({ severity }: { severity: Severity }) { return <span className={`badge severity-${severity.toLowerCase()}`}><i />{severity}</span> }
function StatusBadge({ status }: { status: AlertStatus }) { return <span className={`badge status-${status.toLowerCase()}`}>{status}</span> }

function useSummary(filters: typeof INITIAL_FILTERS) {
  const [state, setState] = useState<{ data?: DashboardSummary; error?: string; loading: boolean }>({ loading: true })
  useEffect(() => {
    let active = true
    const load = (initial = false) => {
      if (initial) setState({ loading: true })
      api.summary(filters).then(data => { if (active) setState({ data, loading: false }) }).catch(error => { if (active) setState({ error: error.message, loading: false }) })
    }
    load(true)
    const interval = window.setInterval(() => load(), 15000)
    return () => { active = false; window.clearInterval(interval) }
  }, [filters])
  return state
}

function Overview() {
  const [filters, setFilters] = useState(INITIAL_FILTERS)
  const summary = useSummary(filters)
  const [energy, setEnergy] = useState<EnergyRow[]>([])
  const [realtimeEnergy, setRealtimeEnergy] = useState<RealtimeEnergyRow[]>([])
  const [weather, setWeather] = useState<Awaited<ReturnType<typeof api.weatherAc>> | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    const load = () => Promise.all([
      api.energy(filters),
      api.realtimeEnergy({ floor: filters.floor || undefined, zone: filters.zone || undefined, load_type: filters.load_type || undefined }),
      api.weatherAc({ start_date: filters.start_date, end_date: filters.end_date, floor: filters.floor || undefined, zone: filters.zone || undefined }),
    ]).then(([energyData, realtimeData, weatherData]) => {
      if (active) {
        setEnergy(energyData.data)
        setRealtimeEnergy(realtimeData.data)
        setWeather(weatherData)
        setError('')
      }
    }).catch(e => { if (active) setError(e.message) })
    load()
    const interval = window.setInterval(load, 5000)
    return () => { active = false; window.clearInterval(interval) }
  }, [filters])
  const trend = useMemo(() => {
    const historical = energy.map(row => ({
      timestamp: Date.parse(`${row.date}T00:00:00+07:00`),
      actual: row.actual_energy_kwh ?? 0,
      expected: row.expected_energy_kwh ?? 0,
    }))
    const live = realtimeEnergy.map(row => ({
      timestamp: Date.parse(row.timestamp),
      actual: row.actual_kwh,
      expected: null,
    }))
    return [...historical, ...live].sort((a, b) => a.timestamp - b.timestamp)
  }, [energy, realtimeEnergy])
  if (summary.loading) return <LoadingState />
  if (summary.error) return <ErrorState error={summary.error} />
  const data = summary.data!
  return <><PageHeading eyebrow="OVERVIEW" title="Energy Overview" subtitle="Live metrics from the CU-BEMS database and cached Open-Meteo context." /><FilterBar value={filters} onChange={setFilters} />{error && <ErrorState error={error} />}<section className="metric-grid"><MetricCard title="Actual Energy" value={formatNumber(data.actual_energy_kwh)} unit="kWh" icon={<Zap size={19} />} tint="teal" /><MetricCard title="Expected Energy" value={formatNumber(data.expected_energy_kwh)} unit="kWh" icon={<ActivityIcon />} tint="blue" /><MetricCard title="Potential Events" value={data.potential_anomaly_event_count.toLocaleString()} unit="events" icon={<AlertTriangle size={19} />} tint="amber" /><MetricCard title="Excess Energy" value={formatNumber(data.excess_energy_kwh)} unit="kWh" icon={<Leaf size={19} />} tint="green" /></section><section className="analytics-grid"><div className="panel trend-panel"><div className="panel-heading"><div><h2>Energy Consumption Trend</h2><p>Actual versus Expected daily energy (kWh)</p></div></div>{trend.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><AreaChart data={trend}><CartesianGrid stroke="#edf1f4" vertical={false} /><XAxis dataKey="timestamp" type="number" scale="time" tickFormatter={formatTrendAxis} axisLine={false} tickLine={false} /><YAxis axisLine={false} tickLine={false} /><Tooltip labelFormatter={label => formatTrendTooltip(Number(label))} /><Area type="monotone" dataKey="actual" stroke="#159a8a" fill="#dff3ee" name="Actual" /><Area type="monotone" dataKey="expected" stroke="#9eabb5" fill="none" strokeDasharray="5 5" name="Expected" /></AreaChart></ResponsiveContainer></div> : <EmptyState />}</div><WeatherPanel weather={weather} /></section><section className="panel recent-panel"><div className="panel-heading"><div><h2>Data quality and context</h2><p>Values are sourced from processed CU-BEMS records; missing data is not imputed.</p></div></div><div className="quality-grid"><div><strong>{data.missing_observations.toLocaleString()}</strong><span>Missing observations</span></div><div><strong>{data.partial_component_observations.toLocaleString()}</strong><span>Partial AC observations</span></div><div><strong>{data.severity_counts.High ?? 0}</strong><span>High severity events</span></div><div><strong>{data.cost_status}</strong><span>Cost status</span></div></div></section></>
}
function ActivityIcon() { return <Thermometer size={19} /> }
function WeatherPanel({ weather }: { weather: Awaited<ReturnType<typeof api.weatherAc>> | null }) {
  const points = weather?.data.filter(row => row.temperature_2m_c != null && row.ac_power_kw != null).slice(0, 100) ?? []
  return <div className="panel weather-panel"><div className="panel-heading"><div><h2>Weather & AC Context</h2><p>Cached Open-Meteo hourly observations</p></div><Thermometer size={20} color="#159a8a" /></div>{weather ? <><div className="weather-stats"><div><strong>{formatNumber(points[0]?.temperature_2m_c, 1)}°C</strong><span>Latest visible temperature</span></div><div><strong>{formatNumber(points[0]?.ac_power_kw, 1)} kW</strong><span>AC power context</span></div></div><div className="context-note">Weather is contextual information and does not change anomaly severity.</div></> : <EmptyState message="Weather context unavailable." />}</div>
}
function WeatherAnalytics() {
  const [filters, setFilters] = useState(INITIAL_FILTERS)
  const [state, setState] = useState<{ data: Awaited<ReturnType<typeof api.weatherAc>> | null; loading: boolean; error?: string }>({ data: null, loading: true })
  useEffect(() => { setState({ data: null, loading: true }); api.weatherAc({ start_date: filters.start_date, end_date: filters.end_date, floor: filters.floor || undefined, zone: filters.zone || undefined }).then(data => setState({ data, loading: false })).catch(error => setState({ data: null, loading: false, error: error.message })) }, [filters])
  const points = state.data?.data.reduce<Array<{ x: number; y: number; timestamp: string; floor: string; zone: string }>>((validPoints, point) => {
    const temperature = Number(point.temperature_2m_c)
    const acPower = Number(point.ac_power_kw)
    if (Number.isFinite(temperature) && Number.isFinite(acPower)) {
      validPoints.push({ x: temperature, y: acPower, timestamp: point.timestamp, floor: point.floor, zone: point.zone })
    }
    return validPoints
  }, []) ?? []
  return <><PageHeading eyebrow="ANALYTICS" title="Weather & AC Analytics" subtitle="Explore cached hourly weather alongside AC power. This is contextual analysis, not causal proof." /><FilterBar value={filters} onChange={setFilters} includeLoad={false} />{state.loading ? <LoadingState /> : state.error ? <ErrorState error={state.error} /> : <section className="analytics-grid"><div className="panel trend-panel"><div className="panel-heading"><div><h2>Temperature versus AC power</h2><p>{points.length.toLocaleString()} joined hourly observations · {state.data?.source}</p></div></div>{points.length ? <div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ top: 16, right: 18, bottom: 12, left: 8 }}><CartesianGrid stroke="#edf1f4" /><XAxis dataKey="x" type="number" name="Temperature" unit="°C" tickLine={false} /><YAxis dataKey="y" type="number" name="AC power" unit=" kW" tickLine={false} /><Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={(value: number, name: string) => [formatNumber(value, 2), name === 'x' ? 'Temperature (°C)' : 'AC Power (kW)']} /><Scatter name="Hourly observations" data={points} fill="#159a8a" /></ScatterChart></ResponsiveContainer></div> : <EmptyState message="No complete Temperature and AC Power observations match these filters." />}</div><WeatherPanel weather={state.data} /></section>}</>
}

function AlertsPage() {
  const navigate = useNavigate()
  const [filters, setFilters] = useState({ ...INITIAL_FILTERS, severity: '', status: '', sort: 'event_time' })
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [state, setState] = useState<{ data: Alert[]; total: number; loading: boolean; error?: string }>({ data: [], total: 0, loading: true })
  useEffect(() => {
    let active = true
    const load = (initial = false) => {
      if (initial) setState(s => ({ ...s, loading: true }))
      api.alerts({ ...filters, page, page_size: ALERT_PAGE_SIZE }).then(result => { if (active) setState({ data: result.data, total: result.pagination.total, loading: false }) }).catch(error => { if (active) setState({ data: [], total: 0, loading: false, error: error.message }) })
    }
    load(true)
    const interval = window.setInterval(() => load(), 15000)
    return () => { active = false; window.clearInterval(interval) }
  }, [filters, page])
  const totalPages = Math.max(1, Math.ceil(state.total / ALERT_PAGE_SIZE))
  useEffect(() => {
    if (!state.loading && page > totalPages) setPage(totalPages)
  }, [page, state.loading, totalPages])
  const rows = state.data.filter(row => `${row.alert_id} ${row.floor} ${row.zone} ${row.load_type}`.toLowerCase().includes(search.toLowerCase()))
  const updateFilters = (value: Partial<typeof filters>) => {
    setFilters(current => ({ ...current, ...value }))
    setPage(1)
  }
  const firstItem = state.total === 0 ? 0 : (page - 1) * ALERT_PAGE_SIZE + 1
  const lastItem = Math.min(page * ALERT_PAGE_SIZE, state.total)
  return <><PageHeading eyebrow="MONITORING" title="Potential Anomalies" subtitle="Review event-level statistical evidence and workflow status." /><FilterBar className="alerts-filter-bar" value={filters} onChange={value => updateFilters(value)} includeLoad><div className="alert-secondary-filters"><SelectFilter label="Severity" value={filters.severity} options={['High', 'Medium', 'Low']} onChange={value => updateFilters({ severity: value })} /><SelectFilter label="Status" value={filters.status} options={['New', 'Acknowledged', 'Resolved']} onChange={value => updateFilters({ status: value })} /><label className="filter-select"><span>Sort</span><select value={filters.sort} onChange={event => updateFilters({ sort: event.target.value })}><option value="event_time">Event Time</option><option value="recently_added">Recently Added</option></select></label></div></FilterBar><section className="panel alerts-table-panel">{state.loading ? <LoadingState /> : state.error ? <ErrorState error={state.error} /> : <><div className="table-toolbar"><div><h2>Alert Events <span className="count-pill">{state.total.toLocaleString()}</span></h2><p>Grouped contiguous anomalies from the real processed dataset.</p></div><label className="search-box"><Search size={16} /><input value={search} onChange={event => { setSearch(event.target.value); setPage(1) }} placeholder="Search this page…" /></label></div><div className="table-scroll"><table><thead><tr><th>ALERT ID</th><th>SCOPE</th><th>START (BKK)</th><th>DURATION</th><th>EXCESS</th><th>SEVERITY</th><th>STATUS</th></tr></thead><tbody>{rows.map(row => <tr key={row.alert_id} className="clickable-row" onClick={() => navigate(`/alerts/${row.alert_id}`)}><td className="id-cell">{row.alert_id}</td><td><strong>{row.floor} · {row.zone}</strong><small>{row.load_type}</small></td><td>{formatTimestamp(row.start_timestamp)}</td><td>{row.duration_minutes} min</td><td className="excess-cell">+{formatNumber(row.excess_energy_kwh, 2)} kWh</td><td><SeverityBadge severity={row.severity} /></td><td><StatusBadge status={row.status} /></td></tr>)}</tbody></table>{rows.length === 0 && <EmptyState />}</div><div className="pagination-bar"><span>Showing {rows.length.toLocaleString()} matching · {firstItem.toLocaleString()}–{lastItem.toLocaleString()} of {state.total.toLocaleString()}</span><div className="pagination-controls"><button className="button button-secondary" disabled={page <= 1} onClick={() => setPage(current => current - 1)}>Previous</button><span>Page {page} of {totalPages}</span><button className="button button-secondary" disabled={page >= totalPages} onClick={() => setPage(current => current + 1)}>Next</button></div></div></>}</section></>
}

function AlertDetail() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [state, setState] = useState<{ data?: AlertDetailType; loading: boolean; error?: string }>({ loading: true })
  useEffect(() => { setState({ loading: true }); api.alert(id).then(result => setState({ data: result.data, loading: false })).catch(error => setState({ loading: false, error: error.message })) }, [id])
  const updateStatus = (status: AlertStatus) => { if (!state.data) return; api.updateAlert(id, status).then(updated => setState(current => ({ ...current, data: current.data ? { ...current.data, ...updated } : current.data }))).catch(error => setState(current => ({ ...current, error: error.message }))) }
  if (state.loading) return <LoadingState />
  if (state.error || !state.data) return <><ErrorState error={state.error ?? 'Alert not found'} /><button className="button button-primary" onClick={() => navigate('/alerts')}>Back to alerts</button></>
  const row = state.data
  return <><button className="back-link" onClick={() => navigate('/alerts')}><ChevronLeft size={17} />Back to Alerts</button><PageHeading eyebrow="ALERT DETAILS" title="Potential Anomaly" subtitle="Statistical evidence with cached external context."><SeverityBadge severity={row.severity} /></PageHeading><div className="detail-title-row"><div><span className="detail-id">{row.alert_id}</span><span className="detail-date"><Clock3 size={14} />{formatTimestamp(row.start_timestamp)} – {formatTimestamp(row.end_timestamp)}</span></div><select aria-label="Update alert status" value={row.status} onChange={e => updateStatus(e.target.value as AlertStatus)}><option>New</option><option>Acknowledged</option><option>Resolved</option></select></div><section className="detail-grid"><div className="panel detail-main"><div className="detail-metrics"><MetricCard title="Peak actual" value={formatNumber(row.actual_kw_peak)} unit="kW" icon={<Zap size={18} />} tint="teal" /><MetricCard title="Expected at peak" value={formatNumber(row.expected_kw_at_peak)} unit="kW" icon={<ActivityIcon />} tint="blue" /><MetricCard title="Excess energy" value={formatNumber(row.excess_energy_kwh, 2)} unit="kWh" icon={<Leaf size={18} />} tint="green" /></div><div className="reason-box"><strong>{row.classification}</strong><p>{row.reason}</p><small>{row.evidence_points} evidence points · {row.duration_minutes} minutes</small></div><h2>Point evidence</h2><div className="table-scroll"><table><thead><tr><th>TIME</th><th>ACTUAL</th><th>EXPECTED</th><th>EXCESS</th><th>SCORE</th></tr></thead><tbody>{row.evidence.slice(0, 100).map(point => <tr key={point.point_alert_id}><td>{formatTimestamp(point.timestamp)}</td><td>{formatNumber(point.actual_kw)} kW</td><td>{formatNumber(point.expected_kw)} kW</td><td className="excess-cell">+{formatNumber(point.excess_kw)} kW</td><td>{formatNumber(point.robust_score, 2)}</td></tr>)}</tbody></table></div></div><div className="panel detail-side"><WeatherDetail context={row.weather_context} /><div className="detail-note"><strong>Why this matters</strong><p>Weather is shown for interpretation only. It does not change the existing anomaly formula or severity.</p></div></div></section></>
}
function WeatherDetail({ context }: { context: AlertDetailType['weather_context'] }) { return <div className="weather-detail"><div className="panel-heading"><h2>Weather context</h2><Thermometer size={20} color="#159a8a" /></div>{context ? <><div className="weather-big">{formatNumber(context.temperature_2m_c, 1)}°C</div><p>{context.source} · {context.timestamp ? formatTimestamp(context.timestamp) : 'No timestamp'}</p><div className="context-list"><span>Relative humidity <strong>{formatNumber(context.relative_humidity_2m_pct, 0)}%</strong></span><span>AC power <strong>{formatNumber(context.ac_context?.ac_power_kw)} kW</strong></span><span>Data status <strong>{context.status}</strong></span></div></> : <EmptyState message="No cached weather context for this load type." />}</div> }

export default App
