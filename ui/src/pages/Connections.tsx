import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Edit2, Plug } from 'lucide-react'
import {
  getConnections, createConnection, updateConnection,
  deleteConnection, testConnection, DatabaseConnection
} from '../api/connections'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'
import SortableHeader from '../components/SortableHeader'
import { useSortableData } from '../hooks/useSortableData'

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

  const { sortedData: sortedConnections, sortKey, sortDirection, onSort } = useSortableData<DatabaseConnection, string>(
    connections, 'name', 'asc'
  )

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

      <div className="bg-white rounded-xl shadow-sm border">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <SortableHeader label="Name" sortKey="name" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <SortableHeader label="Type" sortKey="db_type" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <SortableHeader label="Host" sortKey="host" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <SortableHeader label="Database" sortKey="database" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <SortableHeader label="Status" sortKey="last_test_status" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {sortedConnections.map(c => (
              <tr key={c.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{c.name}</td>
                <td className="px-4 py-3 uppercase text-xs text-gray-500">{c.db_type === 'mssql' ? 'MS SQL' : c.db_type === 'filesystem' ? `Filesystem (${c.staging_format || 'parquet'})` : c.db_type}</td>
                <td className="px-4 py-3 text-gray-600">{c.db_type === 'filesystem' ? '—' : `${c.host}:${c.port}`}</td>
                <td className="px-4 py-3 text-gray-600 max-w-xs truncate" title={c.database}>{c.database}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-col gap-1">
                    <StatusBadge status={c.last_test_status || 'untested'} />
                    {c.last_test_error && <span className="text-xs text-red-400 truncate max-w-xs">{c.last_test_error}</span>}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2 justify-end">
                    <button onClick={() => testMut.mutate(c.id)} disabled={testMut.isPending} className="p-1 text-gray-400 hover:text-blue-600" title="Test">
                      <Plug size={15} />
                    </button>
                    <button onClick={() => openEdit(c)} className="p-1 text-gray-400 hover:text-blue-600">
                      <Edit2 size={15} />
                    </button>
                    <button onClick={() => { if (confirm('Delete connection?')) deleteMut.mutate(c.id) }} className="p-1 text-gray-400 hover:text-red-600">
                      <Trash2 size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {connections.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No connections yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

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
                  {DB_TYPES.map(t => <option key={t} value={t}>{t === 'mssql' ? 'MS SQL' : t === 'filesystem' ? 'Local Filesystem' : t.toUpperCase()}</option>)}
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
