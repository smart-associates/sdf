import client from './client'

export interface ExecutionTable {
  id: number
  execution_id: number
  table_name: string
  status: string
  started_at: string
  completed_at?: string
  record_count: number
  estimated_row_count?: number
  error_message?: string
}

export interface Execution {
  id: number
  job_id: number
  status: string
  started_at: string
  completed_at?: string
  record_count: number
  error_message?: string
  tables: ExecutionTable[]
}

export interface RecordsTimelinePoint {
  id: number
  job_id: number
  job_name: string
  started_at: string
  status: string
  record_count: number
}

export interface ExecutionStats {
  total_runs: number
  success_count: number
  failed_count: number
  running_count: number
  cancelled_count: number
  total_records: number
  recent_executions: Execution[]
  records_timeline: RecordsTimelinePoint[]
}

export interface LogEntry {
  id: number
  execution_id: number
  exec_table_id?: number
  level: string
  event_type: string
  message: string
  meta?: Record<string, unknown>
  created_at: string
}

// `level=info` on the backend filters OUT detail rows; passing no param returns
// info + detail + error. Callers pass `includeDetail=true` to get the full set.
export const getExecutionLogs = (execId: number, includeDetail = false) =>
  client.get<LogEntry[]>(`/executions/${execId}/logs`,
    { params: includeDetail ? undefined : { level: 'info' } })
    .then(r => r.data)

export const getStats = (days?: number) =>
  client.get<ExecutionStats>('/executions/stats', { params: { days } }).then(r => r.data)

export const getExecution = (id: number) =>
  client.get<Execution>(`/executions/${id}`).then(r => r.data)

export const getExecutions = (jobId?: number, limit = 50, days?: number, offset = 0, status?: string, hideEmpty = false) =>
  client.get<Execution[]>('/executions', { params: { job_id: jobId, limit, days, offset, status, hide_empty: hideEmpty || undefined } }).then(r => r.data)

export const stopExecution = (jobId: number, executionId: number) =>
  client.post(`/jobs/${jobId}/executions/${executionId}/stop`).then(r => r.data)
