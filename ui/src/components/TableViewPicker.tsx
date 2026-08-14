import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, Trash2, Filter, GripVertical, ChevronDown, Search } from 'lucide-react'
import clsx from 'clsx'
import { JobTableItem } from '../api/jobs'
import { listConnectionSchemas, listConnectionObjects, listConnectionFiles, ConnectionObject } from '../api/connections'
import { errorMessage } from '../api/client'

// One row's object entry is edited as a single "schema.object" string, split on
// the first dot into schema_name / object_name.
function entryOf(t: JobTableItem): string {
  return t.schema_name ? `${t.schema_name}.${t.object_name ?? ''}` : (t.object_name ?? '')
}

function fieldsFor(value: string): Pick<JobTableItem, 'schema_name' | 'object_name'> {
  const i = value.indexOf('.')
  return i >= 0
    ? { schema_name: value.slice(0, i) || null, object_name: value.slice(i + 1) }
    : { schema_name: null, object_name: value }
}

interface Props {
  tables: JobTableItem[]
  onTablesChange: (next: JobTableItem[]) => void
  sourceConnectionId?: number
  sourceType?: string
}

export default function TableViewPicker({ tables, onTablesChange, sourceConnectionId, sourceType }: Props) {
  const isFilesystem = sourceType === 'filesystem'
  const hasConn = !!sourceConnectionId

  // Rows whose WHERE-filter input is expanded (a row also expands when it
  // already carries a filter). Keyed by row index.
  const [filterOpen, setFilterOpen] = useState<Set<number>>(new Set())
  // Drag-to-reorder state. `dragRow` gates a row's draggable attr so drags only
  // start from the grip handle (leaving the inputs freely selectable).
  const [dragRow, setDragRow] = useState<number | null>(null)
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [overIndex, setOverIndex] = useState<number | null>(null)

  const [browseOpen, setBrowseOpen] = useState(false)
  const [browseSchema, setBrowseSchema] = useState('')
  const [browseQuery, setBrowseQuery] = useState('')

  const emit = (next: JobTableItem[]) => onTablesChange(next.map((t, i) => ({ ...t, position: i })))

  const patch = (i: number, next: Partial<JobTableItem>) =>
    emit(tables.map((t, j) => (j === i ? { ...t, ...next } : t)))
  const addRow = () =>
    emit([...tables, { schema_name: null, object_name: '', table_filter: null, enabled: true, position: tables.length }])
  const addRef = (schema: string | null, name: string) => {
    emit([...tables, { schema_name: schema, object_name: name, table_filter: null, enabled: true, position: tables.length }])
  }
  const deleteRow = (i: number) => emit(tables.filter((_, j) => j !== i))

  const existingRefs = new Set(tables.map(entryOf))

  const schemasQ = useQuery({
    queryKey: ['conn-schemas', sourceConnectionId],
    queryFn: () => listConnectionSchemas(sourceConnectionId!),
    enabled: hasConn && browseOpen && !isFilesystem,
    staleTime: 60_000,
  })

  useEffect(() => {
    if (browseOpen && !browseSchema && schemasQ.data && schemasQ.data.length > 0) {
      setBrowseSchema(schemasQ.data[0])
    }
  }, [browseOpen, browseSchema, schemasQ.data])

  const objectsQ = useQuery({
    queryKey: ['conn-objects', sourceConnectionId, browseSchema],
    queryFn: () => listConnectionObjects(sourceConnectionId!, browseSchema || undefined),
    enabled: hasConn && browseOpen && !isFilesystem && !!browseSchema,
    staleTime: 60_000,
  })

  const filesQ = useQuery({
    queryKey: ['conn-files', sourceConnectionId],
    queryFn: () => listConnectionFiles(sourceConnectionId!),
    enabled: hasConn && browseOpen && isFilesystem,
    staleTime: 60_000,
  })

  const q = browseQuery.trim().toLowerCase()
  const filteredObjects = (objectsQ.data ?? []).filter(o => !q || o.name.toLowerCase().includes(q))
  const filteredFiles = (filesQ.data ?? []).filter(f => !q || f.table.toLowerCase().includes(q))

  const refOf = (o: ConnectionObject) => (o.schema ? `${o.schema}.${o.name}` : o.name)

  const moveRow = (from: number, to: number) => {
    if (from === to) return
    const rows = tables.slice()
    const [moved] = rows.splice(from, 1)
    rows.splice(to, 0, moved)
    emit(rows)
    // Row indices shifted; clear transient expanded state (filled filters stay
    // open via their table_filter value).
    setFilterOpen(new Set())
  }
  const endDrag = () => { setDragRow(null); setDragIndex(null); setOverIndex(null) }

  return (
    <div className="space-y-2">
      <p className="text-[11px] text-gray-400">
        Add the tables and views to replicate. Enter a name like{' '}
        <code>sales.orders</code>, and optionally attach a per-object{' '}
        <code>WHERE</code> filter.
      </p>

      {/* Object rows */}
      <div className="border rounded-lg divide-y">
        {tables.length === 0 ? (
          <div className="px-3 py-4 text-xs text-gray-400 italic text-center">
            No tables or views selected.
          </div>
        ) : (
          tables.map((it, i) => (
            <div
              key={i}
              draggable={dragRow === i}
              onDragStart={e => { setDragIndex(i); e.dataTransfer.effectAllowed = 'move' }}
              onDragOver={e => { if (dragIndex !== null) { e.preventDefault(); setOverIndex(i) } }}
              onDrop={e => { e.preventDefault(); if (dragIndex !== null) moveRow(dragIndex, i); endDrag() }}
              onDragEnd={endDrag}
              className={clsx(
                'flex items-center gap-2 px-2 py-1.5',
                !it.enabled && 'bg-gray-50',
                dragIndex === i && 'opacity-40',
                overIndex === i && dragIndex !== null && dragIndex !== i && 'border-t-2 border-t-blue-400',
              )}
            >
              <span
                onMouseDown={() => setDragRow(i)}
                onMouseUp={() => setDragRow(null)}
                title="Drag to reorder"
                className="shrink-0 cursor-grab text-gray-300 hover:text-gray-500 active:cursor-grabbing"
              >
                <GripVertical size={14} />
              </span>
              <button
                type="button"
                onClick={() => patch(i, { enabled: !it.enabled })}
                title={it.enabled ? 'Enabled — click to disable' : 'Disabled — click to enable'}
                className={clsx(
                  'shrink-0 w-5 h-5 rounded border flex items-center justify-center text-xs font-bold',
                  it.enabled ? 'bg-green-50 border-green-300 text-green-700' : 'bg-gray-100 border-gray-300 text-gray-400',
                )}
              >
                {it.enabled ? '✓' : '✗'}
              </button>
              <input
                className={clsx(
                  'flex-1 bg-transparent border-none focus:ring-0 px-1 py-0.5 text-sm font-mono outline-none',
                  !it.enabled && 'line-through text-gray-400',
                )}
                value={entryOf(it)}
                onChange={e => patch(i, fieldsFor(e.target.value))}
                placeholder="schema.table or table"
              />
              {(filterOpen.has(i) || !!it.table_filter) ? (
                <input
                  className="shrink-0 w-40 border rounded px-1.5 py-0.5 text-xs font-mono bg-white"
                  placeholder="WHERE filter…"
                  title="Optional per-object WHERE clause"
                  value={it.table_filter || ''}
                  onChange={e => patch(i, { table_filter: e.target.value || null })}
                  onBlur={() => {
                    if (!it.table_filter) {
                      setFilterOpen(prev => { const n = new Set(prev); n.delete(i); return n })
                    }
                  }}
                />
              ) : (
                <button
                  type="button"
                  onClick={() => setFilterOpen(prev => new Set(prev).add(i))}
                  title="Add a WHERE filter"
                  className="shrink-0 text-gray-400 hover:text-blue-600 p-1"
                >
                  <Filter size={13} />
                </button>
              )}
              <button
                type="button"
                onClick={() => deleteRow(i)}
                className="shrink-0 text-gray-400 hover:text-red-600 p-1"
                aria-label="Remove"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))
        )}
      </div>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => { if (hasConn) setBrowseOpen(o => !o) }}
          disabled={!hasConn}
          className={clsx(
            'flex items-center gap-1 px-2 py-1 text-xs rounded border',
            hasConn ? 'text-purple-700 border-purple-200 hover:bg-purple-50' : 'text-gray-300 border-gray-200 cursor-not-allowed',
          )}
          title={hasConn ? (isFilesystem ? 'Browse files' : 'Browse tables and views') : 'Select a source connection first'}
        >
          <Plus size={12} /> Browse{browseOpen ? '' : '…'}
          <ChevronDown size={12} className={clsx('transition-transform', browseOpen && 'rotate-180')} />
        </button>
        <button
          type="button"
          onClick={addRow}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-gray-200 text-gray-600 hover:bg-gray-50"
          title="Add an object to type — a name like sales.orders"
        >
          <Plus size={12} /> Add entry
        </button>
        <span className="text-xs text-gray-400 ml-auto">
          {tables.length === 0 ? '' : `${tables.filter(t => t.enabled).length}/${tables.length} enabled`}
        </span>
      </div>

      {browseOpen && hasConn && (
        <div className="border rounded-lg bg-gray-50 p-3 space-y-2">
          <div className="flex items-center gap-2">
            {!isFilesystem && (
              <>
                <label className="text-xs font-medium text-gray-600">Schema</label>
                <select
                  className="border rounded px-2 py-1 text-sm bg-white"
                  value={browseSchema}
                  onChange={e => setBrowseSchema(e.target.value)}
                  disabled={schemasQ.isLoading || !!schemasQ.error}
                >
                  {schemasQ.isLoading && <option>Loading…</option>}
                  {schemasQ.error && <option>Error</option>}
                  {schemasQ.data?.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </>
            )}
            <div className="flex-1 flex items-center gap-1 bg-white border rounded px-2 py-1">
              <Search size={12} className="text-gray-400" />
              <input
                placeholder="Filter…"
                className="flex-1 text-sm outline-none bg-transparent"
                value={browseQuery}
                onChange={e => setBrowseQuery(e.target.value)}
              />
            </div>
          </div>

          {!isFilesystem && schemasQ.error && (
            <p className="text-xs text-red-600">Could not list schemas: {errorMessage(schemasQ.error)}</p>
          )}

          {isFilesystem ? (
            <div className="bg-white border rounded max-h-64 overflow-y-auto">
              {filesQ.isLoading ? (
                <p className="px-3 py-4 text-xs text-gray-400 text-center">Loading…</p>
              ) : filesQ.error ? (
                <p className="px-3 py-4 text-xs text-red-600 text-center">{errorMessage(filesQ.error)}</p>
              ) : filteredFiles.length === 0 ? (
                <p className="px-3 py-4 text-xs text-gray-400 text-center italic">
                  {filesQ.data && filesQ.data.length > 0 ? 'No matches.' : 'No matching files in this directory.'}
                </p>
              ) : (
                <ul className="divide-y">
                  {filteredFiles.map(f => {
                    const already = existingRefs.has(f.table)
                    return (
                      <li key={f.name} className="flex items-center gap-2 px-2 py-1 text-sm">
                        <span className={clsx('font-mono flex-1', already && 'text-gray-400')} title={f.name}>{f.table}</span>
                        {already ? (
                          <span className="shrink-0 text-[10px] text-gray-400 px-2 py-0.5">added</span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => addRef(null, f.table)}
                            className="shrink-0 flex items-center gap-1 px-2 py-0.5 text-xs text-purple-700 border border-purple-200 rounded hover:bg-purple-50"
                          >
                            <Plus size={11} /> Add
                          </button>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          ) : (
            <div className="bg-white border rounded max-h-64 overflow-y-auto">
              {!browseSchema || objectsQ.isLoading ? (
                <p className="px-3 py-4 text-xs text-gray-400 text-center">Loading…</p>
              ) : objectsQ.error ? (
                <p className="px-3 py-4 text-xs text-red-600 text-center">{errorMessage(objectsQ.error)}</p>
              ) : filteredObjects.length === 0 ? (
                <p className="px-3 py-4 text-xs text-gray-400 text-center italic">
                  {objectsQ.data && objectsQ.data.length > 0 ? 'No matches.' : 'No tables or views in this schema.'}
                </p>
              ) : (
                <ul className="divide-y">
                  {filteredObjects.map(o => {
                    const ref = refOf(o)
                    const already = existingRefs.has(ref)
                    return (
                      <li key={ref} className="flex items-center gap-2 px-2 py-1 text-sm">
                        <span className={clsx('font-mono flex-1', already && 'text-gray-400')}>{ref}</span>
                        <span className={clsx(
                          'shrink-0 px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded border',
                          o.kind === 'view' ? 'bg-purple-100 text-purple-700 border-purple-200' : 'bg-blue-50 text-blue-700 border-blue-200',
                        )}>
                          {o.kind}
                        </span>
                        {already ? (
                          <span className="shrink-0 text-[10px] text-gray-400 px-2 py-0.5">added</span>
                        ) : (
                          <button
                            type="button"
                            onClick={() => addRef(o.schema, o.name)}
                            className="shrink-0 flex items-center gap-1 px-2 py-0.5 text-xs text-purple-700 border border-purple-200 rounded hover:bg-purple-50"
                          >
                            <Plus size={11} /> Add
                          </button>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )}

          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={() => { setBrowseOpen(false); setBrowseQuery('') }}
              className="px-2 py-1 text-xs text-gray-600 hover:text-gray-900"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
