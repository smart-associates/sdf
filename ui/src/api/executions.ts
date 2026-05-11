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

export interface ExecutionStats {
  total_runs: number
  success_count: number
  failed_count: number
  running_count: number
  total_records: number
  recent_executions: Execution[]
}

export interface LogEntry {
  id: number
  execution_id: number
  exec_table_id?: number
  level: string
  event_type: string
  message: string
  metadata?: Record<string, unknown>
  created_at: string
}

export const getExecutionLogs = (execId: number) =>
  client.get<LogEntry[]>(`/executions/${execId}/logs`).then(r => r.data)

export const getStats = (days?: number) =>
  client.get<ExecutionStats>('/executions/stats', { params: { days } }).then(r => r.data)

export const getExecution = (id: number) =>
  client.get<Execution>(`/executions/${id}`).then(r => r.data)

export const getExecutions = (jobId?: number, limit = 50, days?: number, offset = 0) =>
  client.get<Execution[]>('/executions', { params: { job_id: jobId, limit, days, offset } }).then(r => r.data)

export const stopExecution = (jobId: number, executionId: number) =>
  client.post(`/jobs/${jobId}/executions/${executionId}/stop`).then(r => r.data)
