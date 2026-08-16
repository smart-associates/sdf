import { Copy, Download, Edit2, Play, Trash2 } from 'lucide-react'
import { Job } from '../api/jobs'
import { DatabaseConnection } from '../api/connections'
import VendorIcon from './VendorIcon'
import KebabMenu from './KebabMenu'

interface Props {
  job: Job
  sourceName: string
  sourceType?: DatabaseConnection['db_type']
  targetName: string
  targetType?: DatabaseConnection['db_type']
  onEdit: () => void
  onExecute: () => void
  onClone: () => void
  onExport: () => void
  onDelete: () => void
  onViewExecution: () => void
  executing?: boolean
}

export default function JobCard({
  job: j,
  sourceName, sourceType, targetName, targetType,
  onEdit, onExecute, onClone, onExport, onDelete, onViewExecution,
  executing,
}: Props) {
  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onEdit()
    }
  }

  const stop = (fn: () => void) => (e: React.MouseEvent) => {
    e.stopPropagation()
    fn()
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onEdit}
      onKeyDown={handleKey}
      className="bg-white rounded-xl p-5 shadow-sm border hover:shadow-md hover:border-blue-200 cursor-pointer transition flex flex-col gap-3 focus:outline-none focus:ring-2 focus:ring-blue-400"
    >
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <div className="font-semibold truncate" title={j.name}>{j.name}</div>
          <div className="text-xs text-gray-500 capitalize mt-0.5">{j.migration_mode.replace('_', ' ')}</div>
        </div>
        <KebabMenu
          items={[
            j.running_execution_id
              ? { label: 'View running execution', icon: <Play size={14} />, onClick: onViewExecution }
              : { label: executing ? 'Executing…' : 'Execute', icon: <Play size={14} />, onClick: onExecute, disabled: executing },
            { label: 'Edit', icon: <Edit2 size={14} />, onClick: onEdit },
            { label: 'Clone', icon: <Copy size={14} />, onClick: onClone },
            { label: 'Export', icon: <Download size={14} />, onClick: onExport },
            { label: 'Delete', icon: <Trash2 size={14} />, onClick: onDelete, danger: true, confirm: 'Delete job?' },
          ]}
        />
      </div>

      <div className="text-sm text-gray-600 space-y-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs text-gray-400 w-12 shrink-0">Source</span>
          {sourceType && <VendorIcon type={sourceType} size={16} className="shrink-0" />}
          <span className="truncate" title={sourceName}>{sourceName}</span>
        </div>
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs text-gray-400 w-12 shrink-0">Target</span>
          {targetType && <VendorIcon type={targetType} size={16} className="shrink-0" />}
          <span className="truncate" title={targetName}>{targetName}</span>
        </div>
      </div>

      {j.running_execution_id && (
        <div className="flex items-center justify-end pt-2 border-t">
          <button
            onClick={stop(onViewExecution)}
            className="flex items-center gap-1 px-2 py-1 text-xs text-blue-600 border border-blue-200 rounded-lg hover:bg-blue-50"
            title="View running execution"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
            Running
          </button>
        </div>
      )}
    </div>
  )
}
