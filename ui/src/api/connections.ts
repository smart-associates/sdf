import client from './client'

export interface DatabaseConnection {
  id: number
  name: string
  db_type: 'postgresql' | 'mysql' | 'mssql' | 'filesystem'
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
