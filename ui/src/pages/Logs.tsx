import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { getExecutions, Execution } from '../api/executions'
import { getJobs } from '../api/jobs'
import StatusBadge from '../components/StatusBadge'

function duration(e: Execution): string {
  if (!e.completed_at) return '—'
  const ms = new Date(e.completed_at).getTime() - new Date(e.started_at).getTime()
  return ms < 60000 ? `${Math.round(ms / 1000)}s` : `${Math.round(ms / 60000)}m`
}

export default function Logs() {
  const [expanded, setExpanded] = useState<number | null>(null)
  const [filterJob, setFilterJob] = useState<number | ''>('')

  const { data: executions = [], isLoading } = useQuery({
    queryKey: ['executions', filterJob],
    queryFn: () => getExecutions(filterJob ? +filterJob : undefined, 100),
    refetchInterval: 15_000,
  })

  const { data: jobs = [] } = useQuery({ queryKey: ['jobs'], queryFn: getJobs })

  const jobName = (id: number) => jobs.find(j => j.id === id)?.name || `Job #${id}`

  if (isLoading) return <div className="text-gray-400 text-sm">Loading...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Execution Logs</h1>
          <p className="text-gray-500 text-sm mt-1">History of all migration runs</p>
        </div>
        <select
          className="border rounded-lg px-3 py-2 text-sm"
          value={filterJob}
          onChange={e => setFilterJob(e.target.value ? +e.target.value : '')}
        >
          <option value="">All Jobs</option>
          {jobs.map(j => <option key={j.id} value={j.id}>{j.name}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl shadow-sm border">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 w-6" />
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">ID</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Job</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Status</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Records</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Duration</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Started</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {executions.map(e => (
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
                {expanded === e.id && e.tables.length > 0 && (
                  <tr key={`${e.id}-tables`}>
                    <td colSpan={7} className="px-8 py-2 bg-gray-50">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-gray-500">
                            <th className="text-left py-1">Table</th>
                            <th className="text-left py-1">Status</th>
                            <th className="text-right py-1">Records</th>
                            <th className="text-left py-1 pl-4">Error</th>
                          </tr>
                        </thead>
                        <tbody>
                          {e.tables.map(t => (
                            <tr key={t.id} className="border-t border-gray-200">
                              <td className="py-1 font-mono">{t.table_name}</td>
                              <td className="py-1"><StatusBadge status={t.status} /></td>
                              <td className="py-1 text-right">{t.record_count.toLocaleString()}</td>
                              <td className="py-1 pl-4 text-red-500">{t.error_message || ''}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
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
      </div>
    </div>
  )
}
