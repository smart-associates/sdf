import client from './client'

export interface Setting {
  id: number
  key: string
  value?: string
  description?: string
  data_type: 'string' | 'integer' | 'boolean'
}

export const getSettings = () =>
  client.get<Setting[]>('/settings').then(r => r.data)

export const updateSetting = (id: number, data: Partial<Setting>) =>
  client.put<Setting>(`/settings/${id}`, data).then(r => r.data)
