import { Copy, Edit2, Plug, Trash2 } from 'lucide-react'
import { DatabaseConnection } from '../api/connections'
import StatusBadge from './StatusBadge'
import VendorIcon, { VENDOR_LABEL } from './VendorIcon'
import KebabMenu from './KebabMenu'

interface Props {
  connection: DatabaseConnection
  onEdit: () => void
  onTest: () => void
  onClone: () => void
  onDelete: () => void
  testing?: boolean
}

export default function ConnectionCard({ connection: c, onEdit, onTest, onClone, onDelete, testing }: Props) {
  const isFs = c.db_type === 'filesystem'

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onEdit()
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onEdit}
      onKeyDown={handleKey}
      className="bg-white rounded-xl p-5 shadow-sm border hover:shadow-md hover:border-blue-200 cursor-pointer transition flex flex-col gap-3 focus:outline-none focus:ring-2 focus:ring-blue-400"
    >
      <div className="flex items-start gap-3">
        <div className="shrink-0 w-10 h-10 flex items-center justify-center rounded-lg bg-gray-50">
          <VendorIcon type={c.db_type} size={28} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold truncate" title={c.name}>{c.name}</div>
          <div className="text-xs text-gray-500">
            {VENDOR_LABEL[c.db_type]}
            {isFs && c.staging_format ? ` · ${c.staging_format}` : ''}
          </div>
        </div>
        <KebabMenu
          items={[
            { label: testing ? 'Testing…' : 'Test connection', icon: <Plug size={14} />, onClick: onTest, disabled: testing },
            { label: 'Edit', icon: <Edit2 size={14} />, onClick: onEdit },
            { label: 'Clone', icon: <Copy size={14} />, onClick: onClone },
            { label: 'Delete', icon: <Trash2 size={14} />, onClick: onDelete, danger: true, confirm: 'Delete connection?' },
          ]}
        />
      </div>

      <div className="text-sm text-gray-600 space-y-1">
        {isFs ? (
          <div className="font-mono text-xs truncate" title={c.database}>{c.database || '—'}</div>
        ) : (
          <>
            <div className="truncate" title={`${c.host}:${c.port}`}>{c.host}:{c.port}</div>
            <div className="text-xs text-gray-500 truncate" title={c.database}>{c.database}</div>
          </>
        )}
      </div>

      <div className="flex items-center justify-between pt-2 border-t">
        <div className="flex flex-col gap-0.5 min-w-0">
          <StatusBadge status={c.last_test_status || 'untested'} />
          {c.last_test_error && (
            <span className="text-xs text-red-400 truncate max-w-[14rem]" title={c.last_test_error}>
              {c.last_test_error}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
