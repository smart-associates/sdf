import client from './client'

export interface DatabaseConnection {
  id: number
  name: string
  db_type: 'postgresql' | 'mysql' | 'filesystem'
  host?: string
  port?: number
  database: string  // for filesystem: directory path
  username?: string
  password?: string
  staging_format?: string
  last_test_status?: string
  last_tested_at?: string
  last_test_error?: string
}

export interface ConnectionTestResult {
  success: boolean
  message: string
  tested_at: string
  error?: string
}

export const getConnections = () =>
  client.get<DatabaseConnection[]>('/connections').then(r => r.data)

export const getConnection = (id: number) =>
  client.get<DatabaseConnection>(`/connections/${id}`).then(r => r.data)

export const createConnection = (data: Omit<DatabaseConnection, 'id'>) =>
  client.post<DatabaseConnection>('/connections', data).then(r => r.data)

export const updateConnection = (id: number, data: Partial<DatabaseConnection>) =>
  client.put<DatabaseConnection>(`/connections/${id}`, data).then(r => r.data)

export const deleteConnection = (id: number) =>
  client.delete(`/connections/${id}`)

export const testConnection = (id: number) =>
  client.post<ConnectionTestResult>(`/connections/${id}/test`).then(r => r.data)

export const cloneConnection = (id: number) =>
  client.post<DatabaseConnection>(`/connections/${id}/clone`).then(r => r.data)

export interface ConnectionObject {
  name: string
  schema: string | null
  kind: 'table' | 'view'
}

export interface ConnectionFile {
  name: string
  table: string
}

export const listConnectionSchemas = (id: number) =>
  client.get<{ schemas: string[] }>(`/connections/${id}/schemas`).then(r => r.data.schemas)

export const listConnectionObjects = (id: number, schema?: string) =>
  client.get<{ objects: ConnectionObject[] }>(`/connections/${id}/objects`, { params: schema ? { schema } : {} })
    .then(r => r.data.objects)

export const listConnectionFiles = (id: number) =>
  client.get<{ files: ConnectionFile[] }>(`/connections/${id}/files`).then(r => r.data.files)

export interface ConnectionExportItem {
  name: string
  db_type: string
  host?: string | null
  port?: number | null
  database: string
  username?: string | null
  staging_format?: string | null
}

export interface ConnectionExportDocument {
  format_version: number
  exported_at: string
  connections: ConnectionExportItem[]
}

export interface ConnectionImportFailure {
  name: string
  error: string
}

export interface ConnectionImportResult {
  created: string[]
  updated: string[]
  failed: ConnectionImportFailure[]
}

export const exportConnection = (id: number) =>
  client.get<ConnectionExportDocument>(`/connections/${id}/export`).then(r => r.data)

export const exportAllConnections = () =>
  client.get<ConnectionExportDocument>('/connections/export').then(r => r.data)

export const importConnections = (doc: ConnectionExportDocument) =>
  client.post<ConnectionImportResult>('/connections/import', doc).then(r => r.data)
