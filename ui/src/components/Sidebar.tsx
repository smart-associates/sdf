import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Database, Briefcase, ScrollText, Settings } from 'lucide-react'
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
  return (
    <aside className="w-56 bg-gray-900 text-white flex flex-col">
      <div className="px-4 py-3 border-b border-gray-700 flex flex-col items-center gap-1">
        <img src={logo} alt="Smart Associates Logo" className="w-full h-auto object-contain" />
        <h1 className="text-xs font-bold text-white leading-tight text-center">Smart Data Frameworks</h1>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {nav.map(({ to, icon: Icon, label, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors',
                isActive
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              )
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
