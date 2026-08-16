import { Fragment, useEffect, useRef, useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Edit2, Play, CheckCircle, Square, Copy, Download, Upload, LayoutGrid, List } from 'lucide-react'
import clsx from 'clsx'
import {
  getJobs, createJob, updateJob, deleteJob, validateJob, executeJob, cloneJob, Job,
  exportJob, exportAllJobs, importJobs, JobExportDocument, JobImportResult,
} from '../api/jobs'
import { errorMessage } from '../api/client'
import { downloadJson } from '../lib/download'
import { getConnections } from '../api/connections'
import { getExecution, stopExecution } from '../api/executions'
import StatusBadge from '../components/StatusBadge'
import Modal from '../components/Modal'
import SortableHeader from '../components/SortableHeader'
import VendorIcon from '../components/VendorIcon'
import TableViewPicker from '../components/TableViewPicker'
import KebabMenu from '../components/KebabMenu'
import HintIcon from '../components/HintIcon'
import JobCard from '../components/JobCard'
import { useSortableData } from '../hooks/useSortableData'

type ViewMode = 'card' | 'list'
const VIEW_MODE_KEY = 'jobs:view'

const MIGRATION_MODES = ['append', 'truncate_load'] as const

function empty(): Partial<Job> {
  return {
    name: '', source_connection_id: 0, tables: [],
    target_connection_id: 0, target_schema: '', create_target_table: false, migration_mode: 'append'
  }
}

export default function Jobs() {
  const qc = useQueryClient()
  const [modal, setModal] = useState<'create' | 'edit' | 'execution' | 'import' | null>(null)
  const [form, setForm] = useState<Partial<Job>>(empty())
  const [isDirty, setIsDirty] = useState(false)
  const skipDirtyRef = useRef(true)
  const [error, setError] = useState('')
  const [validation, setValidation] = useState<any>(null)
  const [executionId, setExecutionId] = useState<number | null>(null)
  const [importText, setImportText] = useState('')
  const [importError, setImportError] = useState('')
  const [importResult, setImportResult] = useState<JobImportResult | null>(null)
  const importFileRef = useRef<HTMLInputElement>(null)
  const [viewMode, setViewMode] = useState<ViewMode>(
    () => (localStorage.getItem(VIEW_MODE_KEY) === 'card' ? 'card' : 'list')
  )

  useEffect(() => {
    localStorage.setItem(VIEW_MODE_KEY, viewMode)
  }, [viewMode])

  useEffect(() => {
    if (skipDirtyRef.current) { skipDirtyRef.current = false; return }
    setIsDirty(true)
  }, [form])

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['jobs'],
    queryFn: getJobs,
    refetchInterval: (query) => query.state.data?.some(j => j.running_execution_id) ? 5000 : false,
  })
  const { data: connections = [] } = useQuery({ queryKey: ['connections'], queryFn: getConnections })
  const sortedConnections = useMemo(
    () => [...connections].sort((a, b) => a.name.localeCompare(b.name)),
    [connections],
  )
  const [execJobId, setExecJobId] = useState<number | null>(null)

  const { data: execStatus, isError: execError } = useQuery({
    queryKey: ['execution', executionId],
    queryFn: () => getExecution(executionId!),
    enabled: !!executionId && modal === 'execution',
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'running' ? 5000 : false
    },
  })

  const createMut = useMutation({
    mutationFn: (d: Omit<Job, 'id'>) => createJob(d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }); skipDirtyRef.current = true; setIsDirty(false); setForm(empty()); setError(''); setModal(null) },
    onError: (e: any) => setError(errorMessage(e)),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<Job> }) => updateJob(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['jobs'] }); skipDirtyRef.current = true; setIsDirty(false); setForm(empty()); setError(''); setModal(null) },
    onError: (e: any) => setError(errorMessage(e)),
  })

  const deleteMut = useMutation({
    mutationFn: deleteJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
    onError: (e: any) => alert(errorMessage(e, 'Cannot delete')),
  })

  const validateMut = useMutation({
    mutationFn: (id: number) => validateJob(id),
    onSuccess: (r) => {
      setValidation(r)
      // Apply the source-catalog qualifications to the open form (matched by
      // the entry as currently typed). Save persists them; unmatched rows are
      // left untouched.
      if (r.qualified.length) {
        const qmap = new Map(r.qualified.map(q => [q.original.toLowerCase(), q]))
        setForm(f => ({
          ...f,
          tables: (f.tables || []).map(t => {
            const entry = t.schema_name ? `${t.schema_name}.${t.object_name ?? ''}` : (t.object_name ?? '')
            const q = qmap.get(entry.toLowerCase())
            return q ? { ...t, schema_name: q.schema_name ?? null, object_name: q.object_name } : t
          }),
        }))
      }
    },
  })

  const executeMut = useMutation({
    mutationFn: (id: number) => executeJob(id),
    onSuccess: (r, id) => {
      setExecutionId(r.execution_id)
      setExecJobId(id)
      setModal('execution')
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (e: any) => alert(errorMessage(e, 'Execute failed')),
    onSettled: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })

  const stopMut = useMutation({
    mutationFn: () => stopExecution(execJobId!, executionId!),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['execution', executionId] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (e: any) => alert(errorMessage(e, 'Stop failed')),
  })

  const cloneMut = useMutation({
    mutationFn: cloneJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
    onError: (e: any) => alert(errorMessage(e, 'Clone failed')),
  })

  const exportJobMut = useMutation({
    mutationFn: exportJob,
    onSuccess: (doc, id) => {
      const name = jobs.find(j => j.id === id)?.name || `job-${id}`
      downloadJson(`${name.replace(/[^a-z0-9_-]+/gi, '_')}-export.json`, doc)
    },
    onError: (e: any) => alert(errorMessage(e, 'Export failed')),
  })

  const exportAllMut = useMutation({
    mutationFn: exportAllJobs,
    onSuccess: (doc) => downloadJson('jobs-export.json', doc),
    onError: (e: any) => alert(errorMessage(e, 'Export failed')),
  })

  const importMut = useMutation({
    mutationFn: (doc: JobExportDocument) => importJobs(doc),
    onSuccess: (result) => {
      setImportResult(result)
      setImportError('')
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
    onError: (e: any) => { setImportError(errorMessage(e, 'Import failed')); setImportResult(null) },
  })

  const openCreate = () => { skipDirtyRef.current = true; setIsDirty(false); setForm(empty()); setError(''); setValidation(null); createMut.reset(); updateMut.reset(); setModal('create') }
  const openEdit = (j: Job) => { skipDirtyRef.current = true; setIsDirty(false); setForm({ ...j }); setError(''); setValidation(null); createMut.reset(); updateMut.reset(); setModal('edit') }
  const openImport = () => { setImportText(''); setImportError(''); setImportResult(null); importMut.reset(); setModal('import') }

  const submitImport = (text: string) => {
    setImportError('')
    setImportResult(null)
    let doc: JobExportDocument
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

  const handleSubmit = () => {
    // Drop blank rows and renumber positions to the current visual order.
    const cleaned = (form.tables || [])
      .filter(r => (r.object_name || '').trim())
      .map((r, i) => ({ ...r, object_name: r.object_name.trim(), position: i }))
    const payload = { ...form, tables: cleaned }
    if (modal === 'create') createMut.mutate(payload as any)
    else if (form.id) updateMut.mutate({ id: form.id, data: payload })
  }

  const connName = (id: number) => connections.find(c => c.id === id)?.name || `#${id}`
  const connType = (id: number) => connections.find(c => c.id === id)?.db_type

  const jobKeyExtractors = useMemo(() => ({
    source: (j: Job) => connName(j.source_connection_id),
    target: (j: Job) => connName(j.target_connection_id),
  }), [connections])

  const { sortedData: sortedJobs, sortKey, sortDirection, onSort } = useSortableData<Job, string>(
    jobs, 'name', 'asc', jobKeyExtractors
  )

  if (isLoading) return <div className="text-gray-400 text-sm">Loading...</div>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Jobs</h1>
          <p className="text-gray-500 text-sm mt-1">Configure and run migration jobs</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex rounded-lg border bg-white p-0.5" role="group" aria-label="View mode">
            <button
              type="button"
              onClick={() => setViewMode('card')}
              aria-pressed={viewMode === 'card'}
              title="Card view"
              className={clsx(
                'flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-md transition',
                viewMode === 'card' ? 'bg-gray-100 text-gray-900' : 'text-gray-500 hover:text-gray-700'
              )}
            >
              <LayoutGrid size={14} /> Cards
            </button>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              aria-pressed={viewMode === 'list'}
              title="List view"
              className={clsx(
                'flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-md transition',
                viewMode === 'list' ? 'bg-gray-100 text-gray-900' : 'text-gray-500 hover:text-gray-700'
              )}
            >
              <List size={14} /> List
            </button>
          </div>
          {jobs.length > 0 && (
            <button
              onClick={() => exportAllMut.mutate()}
              disabled={exportAllMut.isPending}
              title="Export every job's configuration as a portable JSON file (no credentials)"
              className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <Download size={14} /> {exportAllMut.isPending ? 'Exporting…' : 'Export all'}
            </button>
          )}
          <button
            onClick={openImport}
            title="Import job configuration from a previously exported JSON file"
            className="flex items-center gap-1.5 px-3 py-2 text-sm border rounded-lg hover:bg-gray-50"
          >
            <Upload size={14} /> Import
          </button>
          <button onClick={openCreate} className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            <Plus size={16} /> New Job
          </button>
        </div>
      </div>

      {jobs.length === 0 ? (
        <div className="bg-white rounded-xl p-10 shadow-sm border text-center text-gray-400 text-sm">
          No jobs yet — click New Job to get started.
        </div>
      ) : viewMode === 'card' ? (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {sortedJobs.map(j => (
            <JobCard
              key={j.id}
              job={j}
              sourceName={connName(j.source_connection_id)}
              sourceType={connType(j.source_connection_id)}
              targetName={connName(j.target_connection_id)}
              targetType={connType(j.target_connection_id)}
              onEdit={() => openEdit(j)}
              onExecute={() => executeMut.mutate(j.id)}
              onClone={() => cloneMut.mutate(j.id)}
              onExport={() => exportJobMut.mutate(j.id)}
              onDelete={() => deleteMut.mutate(j.id)}
              onViewExecution={() => { setExecutionId(j.running_execution_id!); setExecJobId(j.id); setModal('execution') }}
              executing={executeMut.isPending && executeMut.variables === j.id}
            />
          ))}
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <SortableHeader label="Name" sortKey="name" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
                <SortableHeader label="Source" sortKey="source" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
                <SortableHeader label="Target" sortKey="target" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
                <SortableHeader label="Mode" sortKey="migration_mode" activeSortKey={sortKey} sortDirection={sortDirection} onSort={onSort} />
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {sortedJobs.map(j => (
                <tr key={j.id} onClick={() => openEdit(j)} className="hover:bg-gray-50 cursor-pointer">
                  <td className="px-4 py-3 font-medium">{j.name}</td>
                  <td className="px-4 py-3 text-gray-600">
                    <div className="flex items-center gap-2">
                      {connType(j.source_connection_id) && (
                        <VendorIcon type={connType(j.source_connection_id)!} size={16} className="shrink-0" />
                      )}
                      <span className="truncate">{connName(j.source_connection_id)}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    <div className="flex items-center gap-2">
                      {connType(j.target_connection_id) && (
                        <VendorIcon type={connType(j.target_connection_id)!} size={16} className="shrink-0" />
                      )}
                      <span className="truncate">{connName(j.target_connection_id)}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 capitalize">{j.migration_mode.replace('_', ' ')}</td>
                  <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                    <div className="flex items-center gap-2 justify-end">
                      {j.running_execution_id && (
                        <button
                          onClick={() => { setExecutionId(j.running_execution_id!); setExecJobId(j.id); setModal('execution') }}
                          className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50"
                          title="View running execution"
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
                          Running
                        </button>
                      )}
                      <KebabMenu
                        items={[
                          j.running_execution_id
                            ? { label: 'View running execution', icon: <Play size={14} />, onClick: () => { setExecutionId(j.running_execution_id!); setExecJobId(j.id); setModal('execution') } }
                            : { label: executeMut.isPending && executeMut.variables === j.id ? 'Executing…' : 'Execute', icon: <Play size={14} />, onClick: () => executeMut.mutate(j.id), disabled: executeMut.isPending && executeMut.variables === j.id },
                          { label: 'Edit', icon: <Edit2 size={14} />, onClick: () => openEdit(j) },
                          { label: 'Clone', icon: <Copy size={14} />, onClick: () => cloneMut.mutate(j.id) },
                          { label: 'Export', icon: <Download size={14} />, onClick: () => exportJobMut.mutate(j.id) },
                          { label: 'Delete', icon: <Trash2 size={14} />, onClick: () => deleteMut.mutate(j.id), danger: true, confirm: 'Delete job?' },
                        ]}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {(modal === 'create' || modal === 'edit') && (
        <Modal
          title={modal === 'create' ? 'New Migration Job' : 'Edit Job'}
          onClose={() => setModal(null)}
          size="xl"
          footer={
            <div className="flex gap-2 justify-between">
              <div className="flex gap-2">
                {form.id && (
                  <button
                    onClick={() => validateMut.mutate(form.id!)}
                    disabled={validateMut.isPending || isDirty}
                    title={isDirty ? 'Save your changes before validating' : undefined}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-50"
                  >
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
                {validation.qualified.length > 0 && (
                  <div className="mt-2 text-blue-700 text-xs">
                    Qualified {validation.qualified.length} entr{validation.qualified.length !== 1 ? 'ies' : 'y'} against the source catalog (save to keep):{' '}
                    {validation.qualified.map((q: any) => `${q.original} → ${q.schema_name ? `${q.schema_name}.${q.object_name}` : q.object_name}`).join(', ')}
                  </div>
                )}
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
                  {sortedConnections.map(c => <option key={c.id} value={c.id}>{c.name} ({c.db_type})</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Target Connection *</label>
                <select className="w-full border rounded-lg px-3 py-2 text-sm" value={form.target_connection_id || 0} onChange={e => setForm(f => ({ ...f, target_connection_id: +e.target.value }))}>
                  <option value={0}>— Select —</option>
                  {sortedConnections.map(c => <option key={c.id} value={c.id}>{c.name} ({c.db_type})</option>)}
                </select>
              </div>
              <div className="col-span-2">
                <label className="block text-xs font-medium text-gray-700 mb-1">Tables &amp; Views</label>
                <TableViewPicker
                  tables={form.tables || []}
                  onTablesChange={(next) => setForm(f => ({ ...f, tables: next }))}
                  sourceConnectionId={form.source_connection_id || undefined}
                  sourceType={sortedConnections.find(c => c.id === form.source_connection_id)?.db_type}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-gray-700 mb-1 flex items-center gap-1.5">
                  Migration Mode
                  <HintIcon tip={<><code>append</code> adds rows on every run. <code>truncate_load</code> empties each target table first, then loads a fresh copy.</>} />
                </label>
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
                <label htmlFor="create_target_table" className="text-sm flex items-center gap-1.5">
                  Auto-create target tables from source schema
                  <HintIcon tip={<>Only creates a target table when it doesn't already exist — never alters or replaces an existing one.</>} />
                </label>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {modal === 'import' && (
        <Modal title="Import Pipeline Configuration" onClose={() => setModal(null)} size="lg">
          <div className="space-y-3">
            <p className="text-sm text-gray-500">
              Import a job configuration document exported from this or another SDF instance.
              Connections are matched by name — jobs are created or, if a job with the same
              name already exists here, updated in place.
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
              placeholder="Paste an exported jobs JSON document here — or use Upload file below…"
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

      {modal === 'execution' && (
        <Modal title={execStatus ? `Execution #${execStatus.id}` : 'Starting execution…'} onClose={() => setModal(null)} size="xl">
          {execError ? (
            <div className="py-10 text-center text-red-500 text-sm">Failed to load execution status</div>
          ) : !execStatus ? (
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
                    return (<Fragment key={t.id}>
                      <tr>
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
                      {t.status === 'failed' && t.error_message && (
                        <tr key={`${t.id}-err`}>
                          <td colSpan={4} className="px-3 pb-2 pt-0">
                            <div className="text-xs text-red-600 bg-red-50 rounded px-2 py-1 break-words">{t.error_message}</div>
                          </td>
                        </tr>
                      )}
                    </Fragment>)
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
