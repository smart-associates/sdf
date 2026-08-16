import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Download, Upload } from 'lucide-react'
import {
  getConnections, createConnection, updateConnection,
  deleteConnection, testConnection, cloneConnection, DatabaseConnection,
  exportConnection, exportAllConnections, importConnections,
  ConnectionExportDocument, ConnectionImportResult,
} from '../api/connections'
import { errorMessage } from '../api/client'
import { downloadJson } from '../lib/download'
import Modal from '../components/Modal'
import ConnectionCard from '../components/ConnectionCard'
import HintIcon from '../components/HintIcon'
import { VENDOR_LABEL } from '../components/VendorIcon'

const DB_TYPES = ['postgresql', 'mysql', 'mssql', 'filesystem'] as const
const DEFAULT_PORTS: Record<string, number> = { postgresql: 5432, mysql: 3306, mssql: 1433 }

function empty(): Partial<DatabaseConnection> {
  return { name: '', db_type: 'postgresql', host: '', port: 5432, database: '', username: '', password: '' }
}

export default function Connections() {
  const qc = useQueryClient()
  const [modal, setModal] = useState<'create' | 'edit' | 'import' | null>(null)
  const [form, setForm] = useState<Partial<DatabaseConnection>>(empty())
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
  const [error, setError] = useState('')
  const [importText, setImportText] = useState('')
  const [importError, setImportError] = useState('')
  const [importResult, setImportResult] = useState<ConnectionImportResult | null>(null)
  const importFileRef = useRef<HTMLInputElement>(null)

  const { data: connections = [], isLoading } = useQuery({ queryKey: ['connections'], queryFn: getConnections })

  const sortedConnections = [...connections].sort((a, b) => a.name.localeCompare(b.name))

  const createMut = useMutation({
    mutationFn: (d: Omit<DatabaseConnection, 'id'>) => createConnection(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['connections'] }); setForm(empty()); setError(''); setModal(null) },
    onError: (e: any) => setError(errorMessage(e)),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<DatabaseConnection> }) => updateConnection(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['connections'] }); setForm(empty()); setError(''); setModal(null) },
    onError: (e: any) => setError(errorMessage(e)),
  })

  const deleteMut = useMutation({
    mutationFn: deleteConnection,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connections'] }),
    onError: (e: any) => alert(errorMessage(e, 'Cannot delete')),
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
    onError: (e: any) => alert(errorMessage(e, 'Clone failed')),
  })

  const exportConnectionMut = useMutation({
    mutationFn: exportConnection,
    onSuccess: (doc, id) => {
      const name = connections.find(c => c.id === id)?.name || `connection-${id}`
      downloadJson(`${name.replace(/[^a-z0-9_-]+/gi, '_')}-export.json`, doc)
    },
    onError: (e: any) => alert(errorMessage(e, 'Export failed')),
  })

  const exportAllMut = useMutation({
    mutationFn: exportAllConnections,
    onSuccess: (doc) => downloadJson('connections-export.json', doc),
    onError: (e: any) => alert(errorMessage(e, 'Export failed')),
  })

  const importMut = useMutation({
    mutationFn: (doc: ConnectionExportDocument) => importConnections(doc),
    onSuccess: (result) => {
      setImportResult(result)
      setImportError('')
      qc.invalidateQueries({ queryKey: ['connections'] })
    },
    onError: (e: any) => { setImportError(errorMessage(e, 'Import failed')); setImportResult(null) },
  })

  const openCreate = () => { setForm(empty()); setError(''); setTestResult(null); createMut.reset(); updateMut.reset(); setModal('create') }
  const openEdit = (c: DatabaseConnection) => { setForm({ ...c, password: '********' }); setError(''); setTestResult(null); createMut.reset(); updateMut.reset(); setModal('edit') }
  const openImport = () => { setImportText(''); setImportError(''); setImportResult(null); importMut.reset(); setModal('import') }

  const submitImport = (text: string) => {
    setImportError('')
    setImportResult(null)
    let doc: ConnectionExportDocument
    try {
      doc = JSON.parse(text)
    } catch {
      setImportError('Could not parse this as JSON')
      return
    }
    importMut.mutate(doc)
  }

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-selecting the same file
    if (!file) return
    try {
      const text = await file.text()
      setImportText(text)
      submitImport(text)
    } catch {
      setImportError('Could not read the selected file')
    }
  }

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
        <div className="flex items-center gap-2">
          {connections.length > 0 && (
            <button
              onClick={() => exportAllMut.mutate()}
              disabled={exportAllMut.isPending}
              title="Export every connection's non-secret configuration as a portable JSON file"
              className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <Download size={14} /> {exportAllMut.isPending ? 'Exporting…' : 'Export all'}
            </button>
          )}
          <button
            onClick={openImport}
            title="Import connection configuration from a previously exported JSON file"
            className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50"
          >
            <Upload size={14} /> Import
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Plus size={16} /> Add Connection
          </button>
        </div>
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
              onExport={() => exportConnectionMut.mutate(c.id)}
              onDelete={() => deleteMut.mutate(c.id)}
              testing={testMut.isPending && testMut.variables === c.id}
            />
          ))}
        </div>
      )}

      {(modal === 'create' || modal === 'edit') && (
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
                    <label className="text-xs font-medium text-gray-700 mb-1 flex items-center gap-1.5">
                      Directory Path *
                      <HintIcon tip={<>Each table maps to a file: <code>&lt;directory&gt;/&lt;table&gt;.{form.staging_format || 'parquet'}</code></>} />
                    </label>
                    <input className="w-full border rounded-lg px-3 py-2 text-sm font-mono" placeholder="/data/files" value={form.database || ''} onChange={e => setForm(f => ({ ...f, database: e.target.value }))} />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Output Format</label>
                    <select className="w-full border rounded-lg px-3 py-2 text-sm" value={form.staging_format || 'parquet'} onChange={e => setForm(f => ({ ...f, staging_format: e.target.value }))}>
                      <option value="parquet">Parquet</option>
                      <option value="csv">CSV</option>
                      <option value="tsv">TSV</option>
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
          </div>
        </Modal>
      )}

      {modal === 'import' && (
        <Modal title="Import Connection Configuration" onClose={() => setModal(null)} size="lg">
          <div className="space-y-3">
            <p className="text-sm text-gray-500">
              Import connection configuration exported from this or another SDF instance.
              Connections are matched by name — a matching connection is updated in place
              (its credentials, if any, are left untouched); everything else is created new
              with no credentials, which you'll need to add afterward.
            </p>
            <input
              ref={importFileRef}
              type="file"
              accept=".json,application/json"
              className="hidden"
              onChange={handleImportFile}
            />
            <textarea
              value={importText}
              onChange={e => { setImportText(e.target.value); setImportError(''); setImportResult(null) }}
              placeholder="Paste an exported connections JSON document here — or use Upload file below…"
              rows={6}
              className="w-full border rounded-lg px-3 py-2 text-xs font-mono"
            />
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => submitImport(importText)}
                disabled={!importText.trim() || importMut.isPending}
                className="px-4 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {importMut.isPending ? 'Importing…' : 'Import'}
              </button>
              <button
                onClick={() => importFileRef.current?.click()}
                disabled={importMut.isPending}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                <Upload size={13} /> Upload file
              </button>
            </div>

            {importError && (
              <div className="p-2 bg-red-50 text-red-600 text-sm rounded">{importError}</div>
            )}

            {importResult && (
              <div className="p-3 text-sm rounded border bg-green-50 border-green-200 space-y-2">
                <p className="font-medium text-green-700">
                  {importResult.created.length} created, {importResult.updated.length} updated
                  {importResult.failed.length > 0 && `, ${importResult.failed.length} failed`}
                </p>
                {importResult.created.length > 0 && (
                  <p className="text-xs text-gray-600">Created: {importResult.created.join(', ')}</p>
                )}
                {importResult.updated.length > 0 && (
                  <p className="text-xs text-gray-600">Updated: {importResult.updated.join(', ')}</p>
                )}
                {importResult.failed.map((f, i) => (
                  <div key={i} className="text-xs text-red-600">✗ {f.name}: {f.error}</div>
                ))}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}
