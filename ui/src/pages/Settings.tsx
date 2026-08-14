import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save } from 'lucide-react'
import { getSettings, updateSetting, Setting } from '../api/settings'
import { errorMessage } from '../api/client'

export default function Settings() {
  const qc = useQueryClient()
  const [edits, setEdits] = useState<Record<number, string>>({})
  const [saved, setSaved] = useState<Record<number, boolean>>({})
  const timersRef = useRef<Record<number, ReturnType<typeof setTimeout>>>({})

  useEffect(() => {
    const timers = timersRef.current
    return () => { Object.values(timers).forEach(clearTimeout) }
  }, [])

  const { data: settings = [], isLoading } = useQuery({ queryKey: ['settings'], queryFn: getSettings })

  const [saveError, setSaveError] = useState<Record<number, string>>({})

  const updateMut = useMutation({
    mutationFn: ({ id, value }: { id: number; value: string }) => updateSetting(id, { value }),
    onSuccess: (_, vars) => {
      qc.invalidateQueries({ queryKey: ['settings'] })
      setSaveError(s => ({ ...s, [vars.id]: '' }))
      setSaved(s => ({ ...s, [vars.id]: true }))
      clearTimeout(timersRef.current[vars.id])
      timersRef.current[vars.id] = setTimeout(() => setSaved(s => ({ ...s, [vars.id]: false })), 2000)
    },
    onError: (e: any, vars) => {
      setSaveError(s => ({ ...s, [vars.id]: errorMessage(e, 'Save failed') }))
    },
  })

  const getValue = (s: Setting) => edits[s.id] !== undefined ? edits[s.id] : (s.value || '')

  if (isLoading) return <div className="text-gray-400 text-sm">Loading...</div>

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-gray-500 text-sm mt-1">Application configuration</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border divide-y">
        {settings.map(s => (
          <div key={s.id} className="flex items-center gap-4 px-5 py-4">
            <div className="flex-1">
              <p className="text-sm font-medium">{s.key}</p>
              {s.description && <p className="text-xs text-gray-500 mt-0.5">{s.description}</p>}
            </div>
            <div className="flex items-center gap-2">
              {s.key === 'csv_quoting' ? (
                <select
                  value={getValue(s)}
                  onChange={e => setEdits(d => ({ ...d, [s.id]: e.target.value }))}
                  className="border rounded-lg px-3 py-1.5 text-sm w-40"
                >
                  <option value="none">None (escape)</option>
                  <option value="single">Single ( ' )</option>
                  <option value="double">Double ( " )</option>
                </select>
              ) : s.key === 'log_level' ? (
                <select
                  value={getValue(s)}
                  onChange={e => setEdits(d => ({ ...d, [s.id]: e.target.value }))}
                  className="border rounded-lg px-3 py-1.5 text-sm w-40"
                >
                  <option value="minimal">Minimal</option>
                  <option value="detailed">Detailed</option>
                </select>
              ) : s.data_type === 'boolean' ? (
                <input
                  type="checkbox"
                  checked={getValue(s) === '1' || getValue(s) === 'true'}
                  onChange={e => setEdits(d => ({ ...d, [s.id]: e.target.checked ? '1' : '0' }))}
                  className="w-4 h-4"
                />
              ) : (
                <input
                  type={s.data_type === 'integer' ? 'number' : 'text'}
                  value={getValue(s)}
                  onChange={e => setEdits(d => ({ ...d, [s.id]: e.target.value }))}
                  className="border rounded-lg px-3 py-1.5 text-sm w-40"
                />
              )}
              <button
                onClick={() => updateMut.mutate({ id: s.id, value: getValue(s) })}
                disabled={updateMut.isPending}
                className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg transition-colors ${
                  saved[s.id]
                    ? 'bg-green-100 text-green-700'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                <Save size={13} />
                {saved[s.id] ? 'Saved' : 'Save'}
              </button>
              {saveError[s.id] && <span className="text-xs text-red-500">{saveError[s.id]}</span>}
            </div>
          </div>
        ))}
        {settings.length === 0 && (
          <div className="px-5 py-8 text-center text-gray-400">No settings</div>
        )}
      </div>
    </div>
  )
}
