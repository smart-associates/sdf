import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Plug } from 'lucide-react'
import {
  getConnections, createConnection, updateConnection,
  deleteConnection, testConnection, cloneConnection, DatabaseConnection
} from '../api/connections'
import Modal from '../components/Modal'
import ConnectionCard from '../components/ConnectionCard'
import { VENDOR_LABEL } from '../components/VendorIcon'

const DB_TYPES = ['postgresql', 'mysql', 'mssql', 'filesystem'] as const
const DEFAULT_PORTS: Record<string, number> = { postgresql: 5432, mysql: 3306, mssql: 1433 }

function empty(): Partial<DatabaseConnection> {
  return { name: '', db_type: 'postgresql', host: '', port: 5432, database: '', username: '', password: '' }
}

export default function Connections() {
  const qc = useQueryClient()
  const [modal, setModal] = useState<'create' | 'edit' | null>(null)
  const [form, setForm] = useState<Partial<DatabaseConnection>>(empty())
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [error, setError] = useState('')

  const { data: connections = [], isLoading } = useQuery({ queryKey: ['connections'], queryFn: getConnections })

  const sortedConnections = [...connections].sort((a, b) => a.name.localeCompare(b.name))

  const createMut = useMutation({
    mutationFn: (d: Omit<DatabaseConnection, 'id'>) => createConnection(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['connections'] }); setForm(empty()); setError(''); setModal(null) },
    onError: (e: any) => setError(e.response?.data?.detail || 'Error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<DatabaseConnection> }) => updateConnection(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['connections'] }); setForm(empty()); setError(''); setModal(null) },
    onError: (e: any) => setError(e.response?.data?.detail || 'Error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteConnection,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connections'] }),
    onError: (e: any) => alert(e.response?.data?.detail || 'Cannot delete'),
  })

  const testMut = useMutation({
    mutationFn: testConnection,
    onSuccess: (r) => {
      setTestResult(r)
      qc.invalidateQueries({ queryKey: ['connections'] })
    },
  })

  const cloneMut = useMutation({
    mutationFn: cloneConnection,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connections'] }),
    onError: (e: any) => alert(e.response?.data?.detail || 'Clone failed'),
  })

  const openCreate = () => { setForm(empty()); setError(''); setTestResult(null); createMut.reset(); updateMut.reset(); setModal('create') }
  const openEdit = (c: DatabaseConnection) => { setForm({ ...c, password: '********' }); setError(''); setTestResult(null); createMut.reset(); updateMut.reset(); setModal('edit') }

  const handleDbTypeChange = (t: string) => {
    if (t === 'filesystem') {
      setForm(f => ({ ...f, db_type: t as any, host: '', port: undefined, username: '', password: '', staging_format: f.staging_format || 'parquet' }))
    } else {
      setForm(f => ({ ...f, db_type: t as any, port: DEFAULT_PORTS[t] || 5432 }))
    }
  }

  const handleSubmit = () => {
    if (modal === 'create') createMut.mutate(form as any)
    else if (form.id) updateMut.mutate({ id: form.id, data: form })
  }

  if (isLoading) return <div className="text-gray-400 text-sm">Loading...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Connections</h1>
          <p className="text-gray-500 text-sm mt-1">Manage database connections</p>
        </div>
        <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          <Plus size={16} /> Add Connection
        </button>
      </div>

      {connections.length === 0 ? (
        <div className="bg-white rounded-xl p-10 shadow-sm border text-center text-gray-400 text-sm">
          No connections yet — click Add Connection to get started.
        </div>
      ) : (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {sortedConnections.map(c => (
            <ConnectionCard
              key={c.id}
              connection={c}
              onEdit={() => openEdit(c)}
              onTest={() => testMut.mutate(c.id)}
              onClone={() => cloneMut.mutate(c.id)}
              onDelete={() => deleteMut.mutate(c.id)}
              testing={testMut.isPending && testMut.variables === c.id}
            />
          ))}
        </div>
      )}

      {modal && (
        <Modal
          title={modal === 'create' ? 'Add Connection' : 'Edit Connection'}
          onClose={() => setModal(null)}
          size="lg"
          footer={
            <div className="flex gap-2 justify-end">
              <button onClick={() => setModal(null)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Cancel</button>
              <button onClick={handleSubmit} disabled={createMut.isPending || updateMut.isPending} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                {modal === 'create' ? 'Create' : 'Save'}
              </button>
            </div>
          }
        >
          <div className="space-y-3">
            {error && <div className="p-2 bg-red-50 text-red-600 text-sm rounded">{error}</div>}
            {testResult && (
              <div className={`p-2 text-sm rounded ${testResult.success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
                {testResult.message}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Name *</label>
                <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form.name || ''} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Type *</label>
                <select className="w-full border rounded-lg px-3 py-2 text-sm" value={form.db_type || 'postgresql'} onChange={e => handleDbTypeChange(e.target.value)}>
                  {DB_TYPES.map(t => <option key={t} value={t}>{VENDOR_LABEL[t]}</option>)}
                </select>
              </div>
              {form.db_type === 'filesystem' ? (
                <>
                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-gray-700 mb-1">Directory Path *</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm font-mono" placeholder="/data/files" value={form.database || ''} onChange={e => setForm(f => ({ ...f, database: e.target.value }))} />
                    <p className="text-xs text-gray-400 mt-1">
                      Each table maps to a file: &lt;directory&gt;/&lt;table&gt;.{form.staging_format || 'parquet'}
                    </p>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Output Format</label>
                    <select className="w-full border rounded-lg px-3 py-2 text-sm" value={form.staging_format || 'parquet'} onChange={e => setForm(f => ({ ...f, staging_format: e.target.value }))}>
                      <option value="parquet">Parquet</option>
                      <option value="csv">CSV</option>
                      <option value="avro">Avro</option>
                    </select>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Host *</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form.host || ''} onChange={e => setForm(f => ({ ...f, host: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Port</label>
                    <input type="number" className="w-full border rounded-lg px-3 py-2 text-sm" value={form.port || ''} onChange={e => setForm(f => ({ ...f, port: +e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Database *</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form.database || ''} onChange={e => setForm(f => ({ ...f, database: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Username</label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form.username || ''} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} />
                  </div>
                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-gray-700 mb-1">Password</label>
                    <input type="password" className="w-full border rounded-lg px-3 py-2 text-sm" value={form.password || ''} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} />
                  </div>
                </>
              )}
            </div>
            {modal === 'edit' && form.id && (
              <button
                onClick={() => testMut.mutate(form.id!)}
                disabled={testMut.isPending}
                className="flex items-center gap-2 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50"
              >
                <Plug size={14} /> Test Connection
              </button>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}
