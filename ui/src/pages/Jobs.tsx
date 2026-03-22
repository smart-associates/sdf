import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Edit2, Play, CheckCircle, Square } from 'lucide-react'
import { getJobs, createJob, updateJob, deleteJob, validateJob, executeJob, Job } from '../api/jobs'
import { getConnections } from '../api/connections'
import { getExecution, stopExecution } from '../api/executions'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'

const MIGRATION_MODES = ['append', 'truncate_load'] as const

function empty(): Partial<Job> {
  return {
    name: '', source_connection_id: 0, source_tables: '', table_filter: '',
    target_connection_id: 0, target_schema: '', create_target_table: false, migration_mode: 'append'
  }
}

export default function Jobs() {
  const qc = useQueryClient()
  const [modal, setModal] = useState<'create' | 'edit' | 'execution' | null>(null)
  const [form, setForm] = useState<Partial<Job>>(empty())
  const [error, setError] = useState('')
  const [validation, setValidation] = useState<any>(null)
  const [executionId, setExecutionId] = useState<number | null>(null)

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: getJobs,
    refetchInterval: (query) => query.state.data?.some(j => j.running_execution_id) ? 2000 : false,
  })
  const { data: connections = [] } = useQuery({ queryKey: ['connections'], queryFn: getConnections })
  const [execJobId, setExecJobId] = useState<number | null>(null)

  const { data: execStatus } = useQuery({
    queryKey: ['execution', executionId],
    queryFn: () => getExecution(executionId!),
    enabled: !!executionId && modal === 'execution',
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'running' ? 2000 : false
    },
  })

  const createMut = useMutation({
    mutationFn: (d: Omit<Job, 'id'>) => createJob(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }); setForm(empty()); setError(''); setModal(null) },
    onError: (e: any) => setError(e.response?.data?.detail || 'Error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Job> }) => updateJob(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }); setForm(empty()); setError(''); setModal(null) },
    onError: (e: any) => setError(e.response?.data?.detail || 'Error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
    onError: (e: any) => alert(e.response?.data?.detail || 'Cannot delete'),
  })

  const validateMut = useMutation({
    mutationFn: (id: number) => validateJob(id),
    onSuccess: (r) => setValidation(r),
  })

  const executeMut = useMutation({
    mutationFn: (id: number) => executeJob(id),
    onSuccess: (r, id) => {
      setExecutionId(r.execution_id)
      setExecJobId(id)
      setModal('execution')
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (e: any) => alert(e.response?.data?.detail || 'Execute failed'),
    onSettled: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const stopMut = useMutation({
    mutationFn: () => stopExecution(execJobId!, executionId!),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['execution', executionId] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (e: any) => alert(e.response?.data?.detail || 'Stop failed'),
  })

  const openCreate = () => { setForm(empty()); setError(''); setValidation(null); createMut.reset(); updateMut.reset(); setModal('create') }
  const openEdit = (j: Job) => { setForm({ ...j }); setError(''); setValidation(null); createMut.reset(); updateMut.reset(); setModal('edit') }

  const handleSubmit = () => {
    if (modal === 'create') createMut.mutate(form as any)
    else if (form.id) updateMut.mutate({ id: form.id, data: form })
  }

  const connName = (id: number) => connections.find(c => c.id === id)?.name || `#${id}`

  if (isLoading) return <div className="text-gray-400 text-sm">Loading...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Jobs</h1>
          <p className="text-gray-500 text-sm mt-1">Configure and run migration jobs</p>
        </div>
        <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
          <Plus size={16} /> New Job
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Name</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Source</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Target</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Mode</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {jobs.map(j => (
              <tr key={j.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium">{j.name}</td>
                <td className="px-4 py-3 text-gray-600">{connName(j.source_connection_id)}</td>
                <td className="px-4 py-3 text-gray-600">{connName(j.target_connection_id)}</td>
                <td className="px-4 py-3 text-xs text-gray-500 capitalize">{j.migration_mode.replace('_', ' ')}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2 justify-end">
                    {j.running_execution_id ? (
                      <button
                        onClick={() => { setExecutionId(j.running_execution_id!); setExecJobId(j.id); setModal('execution') }}
                        className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50"
                        title="View running execution"
                      >
                        <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
                        Running
                      </button>
                    ) : (
                      <button onClick={() => executeMut.mutate(j.id)} disabled={executeMut.isPending && executeMut.variables === j.id} className="p-1 text-gray-400 hover:text-green-600" title="Execute">
                        <Play size={15} />
                      </button>
                    )}
                    <button onClick={() => openEdit(j)} className="p-1 text-gray-400 hover:text-blue-600">
                      <Edit2 size={15} />
                    </button>
                    <button onClick={() => { if (confirm('Delete job?')) deleteMut.mutate(j.id) }} className="p-1 text-gray-400 hover:text-red-600">
                      <Trash2 size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">No jobs yet</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {(modal === 'create' || modal === 'edit') && (
        <Modal
          title={modal === 'create' ? 'New Migration Job' : 'Edit Job'}
          onClose={() => setModal(null)}
          size="xl"
          footer={
            <div className="flex gap-2 justify-between">
              <div className="flex gap-2">
                {form.id && (
                  <button onClick={() => validateMut.mutate(form.id!)} disabled={validateMut.isPending} className="flex items-center gap-1 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50">
                    <CheckCircle size={14} /> Validate
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <button onClick={() => setModal(null)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Cancel</button>
                <button onClick={handleSubmit} disabled={createMut.isPending || updateMut.isPending} className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                  {modal === 'create' ? 'Create' : 'Save'}
                </button>
              </div>
            </div>
          }
        >
          <div className="space-y-3">
            {error && <div className="p-2 bg-red-50 text-red-600 text-sm rounded">{error}</div>}
            {validation && (
              <div className={`p-3 text-sm rounded border ${validation.valid ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                <p className="font-medium mb-2">{validation.valid ? 'Validation passed' : 'Validation failed'}</p>
                {validation.items.map((item: any, i: number) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className={item.exists ? 'text-green-600' : 'text-red-600'}>●</span>
                    <span>{item.table_name}: {item.message}</span>
                  </div>
                ))}
                {validation.warnings.map((w: string, i: number) => (
                  <div key={i} className="text-yellow-700 mt-1">⚠ {w}</div>
                ))}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Job Name *</label>
                <input className="w-full border rounded-lg px-3 py-2 text-sm" value={form.name || ''} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Source Connection *</label>
                <select className="w-full border rounded-lg px-3 py-2 text-sm" value={form.source_connection_id || 0} onChange={e => setForm(f => ({ ...f, source_connection_id: +e.target.value }))}>
                  <option value={0}>— Select —</option>
                  {connections.map(c => <option key={c.id} value={c.id}>{c.name} ({c.db_type})</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Target Connection *</label>
                <select className="w-full border rounded-lg px-3 py-2 text-sm" value={form.target_connection_id || 0} onChange={e => setForm(f => ({ ...f, target_connection_id: +e.target.value }))}>
                  <option value={0}>— Select —</option>
                  {connections.map(c => <option key={c.id} value={c.id}>{c.name} ({c.db_type})</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Tables (one per line, schema.table or table)</label>
                <textarea rows={4} className="w-full border rounded-lg px-3 py-2 text-sm font-mono" placeholder="public.users&#10;public.orders&#10;public.products" value={form.source_tables || ''} onChange={e => setForm(f => ({ ...f, source_tables: e.target.value }))} />
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Table Filter (WHERE clause, applied to all tables)</label>
                <input className="w-full border rounded-lg px-3 py-2 text-sm font-mono" placeholder="created_at > '2024-01-01'" value={form.table_filter || ''} onChange={e => setForm(f => ({ ...f, table_filter: e.target.value }))} />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Migration Mode</label>
                <select className="w-full border rounded-lg px-3 py-2 text-sm" value={form.migration_mode || 'append'} onChange={e => setForm(f => ({ ...f, migration_mode: e.target.value as any }))}>
                  {MIGRATION_MODES.map(m => <option key={m} value={m}>{m.replace('_', ' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Target Schema (optional)</label>
                <input className="w-full border rounded-lg px-3 py-2 text-sm" placeholder="public" value={form.target_schema || ''} onChange={e => setForm(f => ({ ...f, target_schema: e.target.value }))} />
              </div>
              <div className="col-span-2 flex items-center gap-2">
                <input type="checkbox" id="create_target_table" checked={form.create_target_table || false} onChange={e => setForm(f => ({ ...f, create_target_table: e.target.checked }))} />
                <label htmlFor="create_target_table" className="text-sm">Auto-create target tables from source schema</label>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {modal === 'execution' && (
        <Modal title={execStatus ? `Execution #${execStatus.id}` : 'Starting execution…'} onClose={() => setModal(null)} size="lg">
          {!execStatus ? (
            <div className="py-10 text-center text-gray-400 text-sm">Loading…</div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <StatusBadge status={execStatus.status} />
                  <span className="text-sm text-gray-500">{execStatus.record_count.toLocaleString()} records</span>
                  {execStatus.completed_at && (
                    <span className="text-sm text-gray-500">
                      {Math.round((new Date(execStatus.completed_at).getTime() - new Date(execStatus.started_at).getTime()) / 1000)}s
                    </span>
                  )}
                </div>
                {execStatus.status === 'running' && (
                  <button
                    onClick={() => stopMut.mutate()}
                    disabled={stopMut.isPending}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 disabled:opacity-50"
                  >
                    <Square size={13} /> Stop
                  </button>
                )}
              </div>
              {execStatus.error_message && (
                <div className="p-2 bg-red-50 text-red-600 text-sm rounded">{execStatus.error_message}</div>
              )}
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Table</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500">Records</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 w-40">Progress</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {execStatus.tables.map(t => {
                    const pct = t.estimated_row_count && t.estimated_row_count > 0
                      ? Math.min(100, Math.round(t.record_count / t.estimated_row_count * 100))
                      : null
                    return (
                      <tr key={t.id}>
                        <td className="px-3 py-2 font-mono text-xs">{t.table_name}</td>
                        <td className="px-3 py-2"><StatusBadge status={t.status} /></td>
                        <td className="px-3 py-2 text-right whitespace-nowrap">
                          {t.record_count.toLocaleString()}
                          {t.estimated_row_count != null && t.status !== 'success' && (
                            <span className="text-gray-400"> / ~{t.estimated_row_count.toLocaleString()}</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {t.status === 'success' ? (
                            <div className="w-full bg-green-100 rounded-full h-1.5">
                              <div className="bg-green-500 h-1.5 rounded-full w-full" />
                            </div>
                          ) : t.status === 'failed' ? (
                            <div className="w-full bg-red-100 rounded-full h-1.5">
                              <div className="bg-red-500 h-1.5 rounded-full w-full" />
                            </div>
                          ) : pct != null ? (
                            <div className="flex items-center gap-1.5">
                              <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                                <div className="bg-blue-500 h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
                              </div>
                              <span className="text-xs text-gray-500 w-8 text-right">{pct}%</span>
                            </div>
                          ) : (
                            <span className="text-xs text-gray-400">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Modal>
      )}
    </div>
  )
}
