import { ChevronUp, ChevronDown } from 'lucide-react'
import type { SortDirection } from '../hooks/useSortableData'

interface Props {
  label: string
  sortKey: string
  activeSortKey: string
  sortDirection: SortDirection
  onSort: (key: any) => void
  className?: string
}

export default function SortableHeader({ label, sortKey, activeSortKey, sortDirection, onSort, className = '' }: Props) {
  const active = sortKey === activeSortKey
  return (
    <th
      className={`px-4 py-3 text-left text-xs font-medium text-gray-500 cursor-pointer select-none hover:text-gray-700 ${className}`}
      onClick={() => onSort(sortKey)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active && (
          sortDirection === 'asc'
            ? <ChevronUp size={12} className="text-gray-400" />
            : <ChevronDown size={12} className="text-gray-400" />
        )}
      </span>
    </th>
  )
}
