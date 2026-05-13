import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { getExecutions, getExecutionLogs, Execution, ExecutionTable, LogEntry } from '../api/executions'
import { getJobs } from '../api/jobs'
import StatusBadge from '../components/StatusBadge'
import SortableHeader from '../components/SortableHeader'
import { useSortableData } from '../hooks/useSortableData'

function levelColor(level: string): string {
  if (level === 'error') return 'text-red-600'
  if (level === 'detail') return 'text-gray-400'
  return 'text-gray-700'
}

function levelBadge(level: string): string {
  if (level === 'error') return 'bg-red-100 text-red-700'
  if (level === 'detail') return 'bg-gray-100 text-gray-500'
  return 'bg-blue-100 text-blue-700'
}

function StepLog({ executionId, isRunning }: { executionId: number; isRunning: boolean }) {
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['execution-logs', executionId],
    queryFn: () => getExecutionLogs(executionId),
    refetchInterval: isRunning ? 5_000 : false,
  })

  if (isLoading) return <div className="text-gray-400 text-xs py-2">Loading logs...</div>
  if (logs.length === 0) return <div className="text-gray-400 text-xs py-2">No log entries</div>

  return (
    <div className="max-h-60 overflow-y-auto border rounded bg-gray-50 text-xs font-mono">
      {logs.map((log: LogEntry) => (
        <div key={log.id} className="flex gap-3 px-3 py-1 border-b border-gray-200 last:border-b-0">
          <span className="text-gray-500 shrink-0 w-20">
            {new Date(log.created_at).toLocaleTimeString()}
          </span>
          <span className={`shrink-0 w-12 text-center rounded px-1 ${levelBadge(log.level)}`}>
            {log.level.toUpperCase()}
          </span>
          <span className={levelColor(log.level)}>{log.message}</span>
        </div>
      ))}
    </div>
  )
}

function duration(e: Execution): string {
  if (!e.completed_at) return '—'
  const ms = new Date(e.completed_at).getTime() - new Date(e.started_at).getTime()
  return ms < 60000 ? `${Math.round(ms / 1000)}s` : `${Math.round(ms / 60000)}m`
}

export default function Logs() {
  const PAGE_SIZE = 50
  const [expanded, setExpanded] = useState<number | null>(null)
  const [filterJob, setFilterJob] = useState<number | ''>('')
  const [filterDays, setFilterDays] = useState<number | ''>(7)
  const [filterStatus, setFilterStatus] = useState<string>('')
  const [page, setPage] = useState(0)

  const { data: executions = [], isLoading } = useQuery({
    queryKey: ['executions', filterJob, filterDays, filterStatus, page],
    queryFn: () => getExecutions(filterJob ? +filterJob : undefined, PAGE_SIZE, filterDays ? +filterDays : undefined, page * PAGE_SIZE, filterStatus || undefined),
    refetchInterval: 15_000,
  })

  const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: getJobs })

  const jobName = (id: number) => jobs.find(j => j.id === id)?.name || `Job #${id}`

  const durationMs = (e: Execution): number => {
    if (!e.completed_at) return -1
    return new Date(e.completed_at).getTime() - new Date(e.started_at).getTime()
  }

  const logKeyExtractors = useMemo(() => ({
    job: (e: Execution) => jobName(e.job_id),
    record_count: (e: Execution) => e.record_count || 0,
    duration: (e: Execution) => durationMs(e),
  }), [jobs])

  const { sortedData: sortedExecutions, sortKey, sortDirection, onSort } = useSortableData<Execution, string>(
    executions, 'id', 'desc', logKeyExtractors
  )

  if (isLoading) return <div className="text-gray-400 text-sm">Loading...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Execution Logs</h1>
          <p className="text-gray-500 text-sm mt-1">History of all migration runs</p>
        </div>
        <div className="flex gap-2">
          <select
            className="border rounded-lg px-3 py-2 text-sm"
            value={filterDays}
            onChange={e => { setFilterDays(e.target.value ? +e.target.value : ''); setPage(0) }}
          >
            <option value="">All Time</option>
            <option value="1">Last 1 Day</option>
            <option value="7">Last 7 Days</option>
            <option value="30">Last 30 Days</option>
            <option value="90">Last 90 Days</option>
          </select>
          <select
            className="border rounded-lg px-3 py-2 text-sm"
            value={filterStatus}
            onChange={e => { setFilterStatus(e.target.value); setPage(0) }}
          >
            <option value="">All Statuses</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select
            className="border rounded-lg px-3 py-2 text-sm"
            value={filterJob}
            onChange={e => { setFilterJob(e.target.value ? +e.target.value : ''); setPage(0) }}
          >
            <option value="">All Jobs</option>
            {jobs.map(j => <option key={j.id} value={j.id}>{j.name}</option>)}
          </select>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 w-6" />
              <SortableHeader label="ID" sortKey="id" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <SortableHeader label="Job" sortKey="job" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <SortableHeader label="Status" sortKey="status" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <SortableHeader label="Records" sortKey="record_count" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <SortableHeader label="Duration" sortKey="duration" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <SortableHeader label="Started" sortKey="started_at" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
            </tr>
          </thead>
          <tbody className="divide-y">
            {sortedExecutions.map(e => (
              <>
                <tr
                  key={e.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                >
                  <td className="px-4 py-3 text-gray-400">
                    {expanded === e.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </td>
                  <td className="px-4 py-3 font-mono">#{e.id}</td>
                  <td className="px-4 py-3">{jobName(e.job_id)}</td>
                  <td className="px-4 py-3"><StatusBadge status={e.status} /></td>
                  <td className="px-4 py-3">{(e.record_count || 0).toLocaleString()}</td>
                  <td className="px-4 py-3 text-gray-500">{duration(e)}</td>
                  <td className="px-4 py-3 text-gray-500">{new Date(e.started_at).toLocaleString()}</td>
                </tr>
                {expanded === e.id && (
                  <tr key={`${e.id}-details`}>
                    <td colSpan={7} className="px-8 py-2 bg-gray-50 space-y-3">
                      {e.tables.length > 0 && (
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="text-gray-500">
                              <th className="text-left py-1">Table</th>
                              <th className="text-left py-1">Status</th>
                              <th className="text-right py-1">Records</th>
                              <th className="text-left py-1 pl-4 w-32">Progress</th>
                              <th className="text-left py-1 pl-4">Error</th>
                            </tr>
                          </thead>
                          <tbody>
                            {e.tables.map((t: ExecutionTable) => {
                              const pct = t.estimated_row_count && t.estimated_row_count > 0
                                ? Math.min(100, Math.round(t.record_count / t.estimated_row_count * 100))
                                : null
                              return (
                              <tr key={t.id} className="border-t border-gray-200">
                                <td className="py-1 font-mono">{t.table_name}</td>
                                <td className="py-1"><StatusBadge status={t.status} /></td>
                                <td className="py-1 text-right whitespace-nowrap">
                                  {t.record_count.toLocaleString()}
                                  {t.estimated_row_count != null && t.status !== 'success' && (
                                    <span className="text-gray-400"> / ~{t.estimated_row_count.toLocaleString()}</span>
                                  )}
                                </td>
                                <td className="py-1 pl-4 w-32">
                                  {t.status === 'running' && pct != null ? (
                                    <div className="flex items-center gap-1">
                                      <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                                        <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${pct}%` }} />
                                      </div>
                                      <span className="text-gray-500 w-7 text-right">{pct}%</span>
                                    </div>
                                  ) : null}
                                </td>
                                <td className="py-1 pl-4 text-red-500">{t.error_message || ''}</td>
                              </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      )}
                      <div>
                        <p className="text-xs font-medium text-gray-500 mb-1">Step Log</p>
                        <StepLog executionId={e.id} isRunning={e.status === 'running'} />
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {executions.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No executions yet</td></tr>
            )}
          </tbody>
        </table>
        {(page > 0 || executions.length === PAGE_SIZE) && (
          <div className="flex items-center justify-between px-4 py-3 border-t text-sm">
            <button
              onClick={() => setPage(p => p - 1)}
              disabled={page === 0}
              className="px-3 py-1.5 border rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-gray-500">Page {page + 1}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={executions.length < PAGE_SIZE}
              className="px-3 py-1.5 border rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
