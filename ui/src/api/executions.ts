import client from './client'

export interface ExecutionTable {
  id: number
  execution_id: number
  table_name: string
  status: string
  started_at: string
  completed_at?: string
  record_count: number
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

export const getStats = () =>
  client.get<ExecutionStats>('/executions/stats').then(r => r.data)

export const getExecution = (id: number) =>
  client.get<Execution>(`/executions/${id}`).then(r => r.data)

export const getExecutions = (jobId?: number, limit = 50) =>
  client.get<Execution[]>('/executions', { params: { job_id: jobId, limit } }).then(r => r.data)
