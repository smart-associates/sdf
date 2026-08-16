import { Copy, Download, Edit2, Plug, Trash2 } from 'lucide-react'
import { DatabaseConnection } from '../api/connections'
import StatusBadge from './StatusBadge'
import VendorIcon, { VENDOR_LABEL } from './VendorIcon'
import KebabMenu from './KebabMenu'

interface Props {
  connection: DatabaseConnection
  onEdit: () => void
  onTest: () => void
  onClone: () => void
  onExport: () => void
  onDelete: () => void
  testing?: boolean
}

export default function ConnectionRow({ connection: c, onEdit, onTest, onClone, onExport, onDelete, testing }: Props) {
  const isFs = c.db_type === 'filesystem'

  return (
    <tr onClick={onEdit} className="hover:bg-gray-50 cursor-pointer">
      <td className="px-4 py-3">
        <span className="font-medium truncate" title={c.name}>{c.name}</span>
      </td>
      <td className="px-4 py-3 text-gray-600">
        <div className="flex items-center gap-2">
          <VendorIcon type={c.db_type} size={18} className="shrink-0" />
          <span className="text-xs">
            {VENDOR_LABEL[c.db_type] || c.db_type}
            {isFs && c.staging_format ? ` · ${c.staging_format}` : ''}
          </span>
        </div>
      </td>
      <td className="px-4 py-3 text-gray-600 text-xs font-mono">
        {isFs ? (
          <span className="truncate" title={c.database}>{c.database || '—'}</span>
        ) : (
          <span className="truncate" title={`${c.host}:${c.port}`}>{c.host}{c.port ? `:${c.port}` : ''}</span>
        )}
      </td>
      <td className="px-4 py-3 text-gray-600 text-xs">
        {isFs ? <span className="text-gray-400">—</span> : <span className="truncate" title={c.database}>{c.database}</span>}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col gap-0.5 min-w-0">
          <StatusBadge status={c.last_test_status || 'untested'} />
          {c.last_test_error && (
            <span className="text-xs text-red-400 truncate max-w-[16rem]" title={c.last_test_error}>
              {c.last_test_error}
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3 text-right" onClick={e => e.stopPropagation()}>
        <KebabMenu
          items={[
            { label: testing ? 'Testing…' : 'Test connection', icon: <Plug size={14} />, onClick: onTest, disabled: testing },
            { label: 'Edit', icon: <Edit2 size={14} />, onClick: onEdit },
            { label: 'Clone', icon: <Copy size={14} />, onClick: onClone },
            { label: 'Export', icon: <Download size={14} />, onClick: onExport },
            { label: 'Delete', icon: <Trash2 size={14} />, onClick: onDelete, danger: true, confirm: 'Delete connection?' },
          ]}
        />
      </td>
    </tr>
  )
}
