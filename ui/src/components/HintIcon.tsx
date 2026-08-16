import { ReactNode, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Info, AlertTriangle, AlertOctagon, CheckCircle, LucideIcon } from 'lucide-react'
import clsx from 'clsx'

export type HintVariant = 'info' | 'warning' | 'error' | 'success'

const VARIANT: Record<HintVariant, { Icon: LucideIcon; iconClass: string }> = {
  info: { Icon: Info, iconClass: 'text-gray-400 group-hover:text-gray-600' },
  warning: { Icon: AlertTriangle, iconClass: 'text-amber-500 group-hover:text-amber-600' },
  error: { Icon: AlertOctagon, iconClass: 'text-red-500 group-hover:text-red-600' },
  success: { Icon: CheckCircle, iconClass: 'text-green-600 group-hover:text-green-700' },
}

const TOOLTIP_WIDTH = 256
const EDGE_MARGIN = 12
const GAP = 6

interface Props {
  tip: ReactNode
  variant?: HintVariant
  size?: number
  className?: string
}

// The tooltip renders into a body-level portal with fixed positioning so it can
// never be clipped by an ancestor's overflow (e.g. a scrollable modal body).
// Position is measured from the icon's viewport rect: clamped horizontally to
// the viewport and flipped above the icon when there isn't room below.
export default function HintIcon({ tip, variant = 'info', size = 13, className }: Props) {
  const { Icon, iconClass } = VARIANT[variant]
  const wrapperRef = useRef<HTMLSpanElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number; ready: boolean }>({ left: 0, top: 0, ready: false })

  const recompute = () => {
    const el = wrapperRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const iconCenter = r.left + r.width / 2
    const left = Math.max(
      EDGE_MARGIN,
      Math.min(iconCenter - TOOLTIP_WIDTH / 2, window.innerWidth - TOOLTIP_WIDTH - EDGE_MARGIN),
    )
    const tipH = tipRef.current?.offsetHeight ?? 0
    const spaceBelow = window.innerHeight - r.bottom
    // Prefer below; flip above when the tooltip wouldn't fit and there's more room up top.
    const flipUp = tipH > 0 && spaceBelow < tipH + GAP + EDGE_MARGIN && r.top > spaceBelow
    const top = flipUp ? r.top - GAP - tipH : r.bottom + GAP
    setPos({ left, top, ready: true })
  }

  useLayoutEffect(() => {
    if (!open) return
    recompute()
    // Recompute if the icon moves while the tooltip is open (modal scroll, resize).
    const onMove = () => recompute()
    window.addEventListener('scroll', onMove, true)
    window.addEventListener('resize', onMove)
    return () => {
      window.removeEventListener('scroll', onMove, true)
      window.removeEventListener('resize', onMove)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  return (
    <span
      ref={wrapperRef}
      className={clsx('group relative inline-flex items-center align-middle', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => { setOpen(false); setPos(p => ({ ...p, ready: false })) }}
      onFocus={() => setOpen(true)}
      onBlur={() => { setOpen(false); setPos(p => ({ ...p, ready: false })) }}
      tabIndex={0}
    >
      <Icon
        size={size}
        className={clsx('cursor-help transition-colors', iconClass)}
        aria-hidden="true"
      />
      {open && createPortal(
        <div
          ref={tipRef}
          role="tooltip"
          style={{ position: 'fixed', left: pos.left, top: pos.top, width: TOOLTIP_WIDTH }}
          className={clsx(
            'pointer-events-none z-[60] rounded-md bg-gray-800 px-2.5 py-1.5 text-xs font-normal normal-case leading-snug text-white shadow-lg ring-1 ring-gray-700 transition-opacity duration-100',
            '[&_code]:rounded [&_code]:bg-white/10 [&_code]:px-1 [&_code]:font-mono [&_code]:text-[11px]',
            pos.ready ? 'opacity-100' : 'opacity-0',
          )}
        >
          {tip}
        </div>,
        document.body,
      )}
    </span>
  )
}
