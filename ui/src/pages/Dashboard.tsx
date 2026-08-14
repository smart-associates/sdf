import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { getStats } from '../api/executions'
import { getConnections } from '../api/connections'
import { getJobs } from '../api/jobs'
import StatusBadge from '../components/StatusBadge'

const COLORS = { success: '#22c55e', failed: '#ef4444', running: '#3b82f6', cancelled: '#eab308' }
type StatusKey = keyof typeof COLORS

function StatCard({ label, value, sub, onClick }: { label: string; value: number | string; sub?: string; onClick?: () => void }) {
  return (
    <div
      className={`bg-white rounded-xl p-5 shadow-sm border ${onClick ? 'cursor-pointer hover:shadow-md hover:border-gray-300 transition' : ''}`}
      onClick={onClick}
    >
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

function fmtDuration(started: string, completed?: string): string {
  if (!completed) return '—'
  const ms = new Date(completed).getTime() - new Date(started).getTime()
  return ms < 60000 ? `${Math.round(ms / 1000)}s` : `${Math.round(ms / 60000)}m`
}

function ClickableCard({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <div
      className="bg-white rounded-xl p-5 shadow-sm border cursor-pointer hover:shadow-md hover:border-gray-300 transition"
      onClick={onClick}
    >
      {children}
    </div>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [filterDays, setFilterDays] = useState<number | ''>(7)

  const goToLogs = (params: Record<string, string | number> = {}) => {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) qs.set(k, String(v))
    if (filterDays) qs.set('days', String(filterDays))
    const s = qs.toString()
    navigate(s ? `/logs?${s}` : '/logs')
  }

  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats', filterDays],
    queryFn: () => getStats(filterDays ? +filterDays : undefined),
    refetchInterval: 10_000,
  })
  const { data: connections = [] } = useQuery({ queryKey: ['connections'], queryFn: getConnections })
  const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: getJobs })

  const pieData = stats
    ? [
        { name: 'Success', value: stats.success_count, color: COLORS.success, status: 'success' },
        { name: 'Failed', value: stats.failed_count, color: COLORS.failed, status: 'failed' },
        { name: 'Running', value: stats.running_count, color: COLORS.running, status: 'running' },
        { name: 'Cancelled', value: stats.cancelled_count, color: COLORS.cancelled, status: 'cancelled' },
      ].filter(d => d.value > 0)
    : []

  const timelineData = (stats?.records_timeline || [])
    .filter(p => p.record_count > 0)
    .map(p => ({
      id: p.id,
      job_id: p.job_id,
      label: p.job_name,
      started_at: p.started_at,
      status: p.status,
      records: p.record_count,
    }))

  const fmtTick = (iso: string) => {
    const d = new Date(iso)
    if (filterDays === 1) {
      const h = d.getHours()
      return `${h % 12 || 12}${h < 12 ? 'am' : 'pm'}`
    }
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  }

  const bucketTicks: string[] = []
  let lastTickBucket = ''
  for (const p of timelineData) {
    const d = new Date(p.started_at)
    const bucket = filterDays === 1
      ? `${d.toDateString()} ${d.getHours()}`
      : d.toDateString()
    if (bucket !== lastTickBucket) {
      bucketTicks.push(p.started_at)
      lastTickBucket = bucket
    }
  }
  const MAX_X_TICKS = 5
  const xAxisTicks = bucketTicks.length <= MAX_X_TICKS
    ? bucketTicks
    : Array.from({ length: MAX_X_TICKS }, (_, i) =>
        bucketTicks[Math.round((i * (bucketTicks.length - 1)) / (MAX_X_TICKS - 1))])

  const fmtCompact = (v: number) =>
    new Intl.NumberFormat(undefined, { notation: 'compact', maximumSignificantDigits: 2 }).format(v)

  const renderPieLabel = ({ cx, cy, midAngle, outerRadius, name, value }: any) => {
    const RAD = Math.PI / 180
    const r = outerRadius + 14
    const x = cx + r * Math.cos(-midAngle * RAD)
    const y = cy + r * Math.sin(-midAngle * RAD)
    return (
      <text x={x} y={y} textAnchor={x > cx ? 'start' : 'end'} dominantBaseline="central" fontSize={11} fill="#374151">
        {`${name}: ${value}`}
      </text>
    )
  }

  const dbTypeCounts = connections.reduce((acc: Record<string, number>, c) => {
    acc[c.db_type] = (acc[c.db_type] || 0) + 1
    return acc
  }, {})

  if (isLoading) return <div className="text-gray-400 text-sm">Loading...</div>

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Data migration overview</p>
        </div>
        <select
          className="border rounded-lg px-3 py-2 text-sm"
          value={filterDays}
          onChange={e => setFilterDays(e.target.value ? +e.target.value : '')}
        >
          <option value="">All Time</option>
          <option value="1">Last 1 Day</option>
          <option value="7">Last 7 Days</option>
          <option value="30">Last 30 Days</option>
          <option value="90">Last 90 Days</option>
        </select>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Runs" value={stats?.total_runs || 0} onClick={() => goToLogs()} />
        <StatCard label="Successful" value={stats?.success_count || 0} onClick={() => goToLogs({ status: 'success' })} />
        <StatCard label="Failed" value={stats?.failed_count || 0} onClick={() => goToLogs({ status: 'failed' })} />
        <StatCard
          label="Records Migrated"
          value={(stats?.total_records || 0).toLocaleString()}
          onClick={() => goToLogs({ hide_empty: 1 })}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl p-5 shadow-sm border md:col-span-1">
          <h2 className="text-sm font-semibold mb-4">Execution Status</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={70}
                  paddingAngle={2}
                  minAngle={6}
                  dataKey="value"
                  labelLine
                  label={renderPieLabel}
                  onClick={(d: any) => goToLogs({ status: d.status })}
                  className="cursor-pointer"
                >

                  {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">No executions yet</div>
          )}
        </div>

        <div className="bg-white rounded-xl p-5 shadow-sm border md:col-span-2">
          <h2 className="text-sm font-semibold mb-4">Records over Time</h2>
          {timelineData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={timelineData} barCategoryGap={2}>
                <XAxis
                  dataKey="started_at"
                  tick={{ fontSize: 10 }}
                  tickFormatter={fmtTick}
                  ticks={xAxisTicks}
                  interval={0}
                  minTickGap={24}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickFormatter={fmtCompact}
                  width={36}
                  scale="sqrt"
                  tickCount={5}
                />
                <Tooltip
                  trigger="hover"
                  cursor={{ fill: 'rgba(0,0,0,0.04)' }}
                  labelFormatter={(_v, payload) => {
                    const p = payload?.[0]?.payload as { label: string; started_at: string } | undefined
                    return p ? `${p.label} · ${new Date(p.started_at).toLocaleString()}` : ''
                  }}
                  formatter={(v: number) => [v.toLocaleString(), 'Records']}
                />
                <Bar
                  dataKey="records"
                  maxBarSize={10}
                  radius={[3, 3, 0, 0]}
                  onClick={(d: any) => goToLogs({ job_id: d.job_id })}
                  className="cursor-pointer"
                >
                  {timelineData.map(p => (
                    <Cell key={p.id} fill={COLORS[p.status as StatusKey] || COLORS.running} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-gray-400 text-sm">No executions yet</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ClickableCard onClick={() => navigate('/connections')}>
          <h2 className="text-sm font-semibold mb-3">Connection Types</h2>
          <div className="space-y-2">
            {Object.entries(dbTypeCounts).map(([type, count]) => (
              <div key={type} className="flex items-center gap-2">
                <span className="text-xs text-gray-500 w-24 capitalize">{type}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full"
                    style={{ width: `${connections.length ? (count / connections.length) * 100 : 0}%` }}
                  />
                </div>
                <span className="text-xs font-medium">{count}</span>
              </div>
            ))}
            {connections.length === 0 && <p className="text-sm text-gray-400">No connections</p>}
          </div>
        </ClickableCard>

        <ClickableCard onClick={() => navigate('/connections')}>
          <h2 className="text-sm font-semibold mb-3">Recent Connections</h2>
          <div className="space-y-2">
            {connections.slice(0, 5).map(c => (
              <div key={c.id} className="flex items-center justify-between">
                <span className="text-sm truncate">{c.name}</span>
                <StatusBadge status={c.last_test_status || 'untested'} />
              </div>
            ))}
            {connections.length === 0 && <p className="text-sm text-gray-400">No connections</p>}
          </div>
        </ClickableCard>

        <ClickableCard onClick={() => navigate('/jobs')}>
          <h2 className="text-sm font-semibold mb-3">Recent Jobs</h2>
          <div className="space-y-2">
            {jobs.slice(0, 5).map(j => (
              <div key={j.id} className="flex items-center justify-between">
                <span className="text-sm truncate">{j.name}</span>
                <span className="text-xs text-gray-400 capitalize">{j.migration_mode}</span>
              </div>
            ))}
            {jobs.length === 0 && <p className="text-sm text-gray-400">No jobs</p>}
          </div>
        </ClickableCard>
      </div>

      <div
        className="bg-white rounded-xl shadow-sm border cursor-pointer hover:shadow-md hover:border-gray-300 transition"
        onClick={() => goToLogs()}
      >
        <div className="p-4 border-b">
          <h2 className="text-sm font-semibold">Recent Executions</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Job</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Status</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Records</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Duration</th>
              <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Started</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {(stats?.recent_executions || []).map(e => (
              <tr key={e.id} className="hover:bg-gray-50">
                <td className="px-4 py-2">{jobs.find(j => j.id === e.job_id)?.name || `Job #${e.job_id}`}</td>
                <td className="px-4 py-2"><StatusBadge status={e.status} /></td>
                <td className="px-4 py-2">{(e.record_count || 0).toLocaleString()}</td>
                <td className="px-4 py-2 text-gray-500">{fmtDuration(e.started_at, e.completed_at)}</td>
                <td className="px-4 py-2 text-gray-500">{new Date(e.started_at).toLocaleString()}</td>
              </tr>
            ))}
            {!stats?.recent_executions?.length && (
              <tr><td colSpan={5} className="px-4 py-6 text-center text-gray-400">No executions yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
