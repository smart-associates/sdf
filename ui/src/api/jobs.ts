import client from './client'

export interface Job {
  id: number
  name: string
  source_connection_id: number
  source_tables?: string
  table_filter?: string
  target_connection_id: number
  target_schema?: string
  create_target_table: boolean
  migration_mode: 'full' | 'truncate_load' | 'append'
  running_execution_id?: number
}

export interface JobValidationItem {
  table_name: string
  exists: boolean
  message: string
}

export interface JobValidationResult {
  valid: boolean
  items: JobValidationItem[]
  warnings: string[]
}

export interface JobExecuteResult {
  execution_id: number
  job_id: number
  status: string
  started_at: string
}

export const getJobs = () =>
  client.get<Job[]>('/jobs').then(r => r.data)

export const getJob = (id: number) =>
  client.get<Job>(`/jobs/${id}`).then(r => r.data)

export const createJob = (data: Omit<Job, 'id'>) =>
  client.post<Job>('/jobs', data).then(r => r.data)

export const updateJob = (id: number, data: Partial<Job>) =>
  client.put<Job>(`/jobs/${id}`, data).then(r => r.data)

export const deleteJob = (id: number) =>
  client.delete(`/jobs/${id}`)

export const validateJob = (id: number) =>
  client.post<JobValidationResult>(`/jobs/${id}/validate`).then(r => r.data)

export const executeJob = (id: number) =>
  client.post<JobExecuteResult>(`/jobs/${id}/execute`).then(r => r.data)

export const cloneJob = (id: number) =>
  client.post<Job>(`/jobs/${id}/clone`).then(r => r.data)
