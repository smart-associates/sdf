import { ReactNode, useEffect, useRef, useState } from 'react'
import { MoreVertical } from 'lucide-react'
import clsx from 'clsx'

export interface KebabMenuItem {
  label: string
  icon?: ReactNode
  onClick: () => void
  disabled?: boolean
  danger?: boolean
  confirm?: string
}

interface Props {
  items: KebabMenuItem[]
  title?: string
  align?: 'left' | 'right'
}

export default function KebabMenu({ items, title = 'Actions', align = 'right' }: Props) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDocClick = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const handleItem = (item: KebabMenuItem) => (e: React.MouseEvent) => {
    e.stopPropagation()
    setOpen(false)
    if (item.disabled) return
    if (item.confirm && !confirm(item.confirm)) return
    item.onClick()
  }

  return (
    <div ref={containerRef} className="relative inline-block" onClick={e => e.stopPropagation()}>
      <button
        type="button"
        onClick={e => { e.stopPropagation(); setOpen(o => !o) }}
        className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded"
        title={title}
        aria-label={title}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <MoreVertical size={16} />
      </button>
      {open && (
        <div
          role="menu"
          className={clsx(
            'absolute z-20 mt-1 min-w-[10rem] bg-white border rounded-lg shadow-lg py-1',
            align === 'right' ? 'right-0' : 'left-0',
          )}
        >
          {items.map((item, i) => (
            <button
              key={i}
              type="button"
              role="menuitem"
              onClick={handleItem(item)}
              disabled={item.disabled}
              className={clsx(
                'w-full flex items-center gap-2 px-3 py-1.5 text-sm text-left',
                item.disabled
                  ? 'text-gray-300 cursor-not-allowed'
                  : item.danger
                    ? 'text-red-600 hover:bg-red-50'
                    : 'text-gray-700 hover:bg-gray-50',
              )}
            >
              {item.icon && <span className="shrink-0 w-4 h-4 flex items-center justify-center">{item.icon}</span>}
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
