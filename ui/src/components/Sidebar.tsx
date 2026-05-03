import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Database,
  Briefcase,
  ScrollText,
  Settings,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import clsx from 'clsx'
import logo from '../assets/logo.png'

const nav = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/connections', icon: Database, label: 'Connections' },
  { to: '/jobs', icon: Briefcase, label: 'Jobs' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={clsx(
        'group/aside relative bg-gray-900 text-white flex flex-col transition-[width] duration-200',
        collapsed ? 'w-16' : 'w-56'
      )}
    >
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="absolute top-4 -right-2.5 z-10 flex h-5 w-5 items-center justify-center rounded-full bg-gray-800 text-gray-300 opacity-0 ring-1 ring-gray-700 transition-opacity hover:bg-gray-700 hover:text-white focus-visible:opacity-100 group-hover/aside:opacity-100"
      >
        {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
      </button>
      <div
        className={clsx(
          'border-b border-gray-700 flex flex-col items-center gap-1',
          collapsed ? 'px-2 py-3' : 'px-4 py-3'
        )}
      >
        <img
          src={logo}
          alt="Smart Associates Logo"
          className="w-full h-auto object-contain"
        />
        {!collapsed && (
          <h1 className="text-xs font-bold text-white leading-tight text-center">
            Smart Data Frameworks
          </h1>
        )}
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {nav.map(({ to, icon: Icon, label, end }) => (
          <div key={to} className="group relative">
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                  collapsed && 'justify-center',
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                )
              }
            >
              <Icon size={18} />
              {!collapsed && label}
            </NavLink>
            {collapsed && (
              <span
                role="tooltip"
                className="pointer-events-none absolute left-full top-1/2 z-20 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md bg-gray-800 px-2 py-1 text-xs text-white opacity-0 shadow-lg ring-1 ring-gray-700 transition-opacity group-hover:opacity-100"
              >
                {label}
              </span>
            )}
          </div>
        ))}
      </nav>
    </aside>
  )
}
