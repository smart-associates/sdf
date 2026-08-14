import client from './client'

export interface JobTableItem {
  schema_name?: string | null
  object_name: string
  table_filter?: string | null
  enabled: boolean
  position: number
}

export interface Job {
  id: number
  name: string
  source_connection_id: number
  tables: JobTableItem[]
  target_connection_id: number
  target_schema?: string
  create_target_table: boolean
  migration_mode: 'truncate_load' | 'append'
  running_execution_id?: number
}

export interface JobValidationItem {
  table_name: string
  exists: boolean
  message: string
}

export interface TableQualification {
  original: string
  schema_name?: string | null
  object_name: string
}

export interface JobValidationResult {
  valid: boolean
  items: JobValidationItem[]
  warnings: string[]
  qualified: TableQualification[]
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

export interface ConnectionRef {
  name: string
  db_type: string
}

export interface JobExportItem {
  name: string
  tables: JobTableItem[]
  target_schema?: string | null
  create_target_table: boolean
  migration_mode: 'truncate_load' | 'append'
  source_connection?: ConnectionRef | null
  target_connection?: ConnectionRef | null
}

export interface JobExportDocument {
  format_version: number
  exported_at: string
  jobs: JobExportItem[]
}

export interface JobImportFailure {
  name: string
  error: string
}

export interface JobImportResult {
  created: string[]
  updated: string[]
  failed: JobImportFailure[]
}

export const exportJob = (id: number) =>
  client.get<JobExportDocument>(`/jobs/${id}/export`).then(r => r.data)

export const exportAllJobs = () =>
  client.get<JobExportDocument>('/jobs/export').then(r => r.data)

export const importJobs = (doc: JobExportDocument) =>
  client.post<JobImportResult>('/jobs/import', doc).then(r => r.data)
