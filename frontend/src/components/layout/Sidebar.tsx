import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Building2, Leaf, BrainCircuit,
  MessageSquare, FileText, Users, LogOut, Zap,
} from 'lucide-react'
import { clsx } from 'clsx'
import { useAuthStore } from '@/store/authStore'
import { useLogout } from '@/hooks/useAuth'

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['admin', 'analyst', 'auditor', 'supplier'] },
  { to: '/companies', label: 'Companies', icon: Building2, roles: ['admin', 'analyst', 'auditor'] },
  { to: '/emissions', label: 'Emissions', icon: Leaf, roles: ['admin', 'analyst', 'auditor', 'supplier'] },
  { to: '/predictions', label: 'Predictions', icon: BrainCircuit, roles: ['admin', 'analyst', 'auditor'] },
  { to: '/chat', label: 'ESG Assistant', icon: MessageSquare, roles: ['admin', 'analyst', 'auditor'] },
  { to: '/reports', label: 'CSRD Reports', icon: FileText, roles: ['admin', 'analyst', 'auditor'] },
  { to: '/admin', label: 'Admin', icon: Users, roles: ['admin'] },
]

export function Sidebar() {
  const user = useAuthStore((s) => s.user)
  const logout = useLogout()

  return (
    <aside className="w-16 lg:w-64 bg-white border-r border-gray-200 flex flex-col shrink-0 transition-all">
      {/* Logo */}
      <div className="p-4 lg:p-6 border-b border-gray-200">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center shrink-0">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <div className="hidden lg:block">
            <p className="font-semibold text-gray-900 text-sm">CarbonSense</p>
            <p className="text-xs text-gray-500">CSRD Intelligence</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 lg:p-4 space-y-1 overflow-y-auto scrollbar-thin">
        {nav
          .filter(item => user && item.roles.includes(user.role))
          .map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              title={label}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                )
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="hidden lg:inline">{label}</span>
            </NavLink>
          ))}
      </nav>

      {/* User + Logout */}
      <div className="p-2 lg:p-4 border-t border-gray-200">
        <div className="hidden lg:flex items-center gap-3 mb-3">
          <div className="w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center shrink-0">
            <span className="text-primary-700 text-xs font-bold uppercase">
              {user?.full_name?.[0] ?? user?.email[0] ?? '?'}
            </span>
          </div>
          <div className="min-w-0">
            <p className="text-xs font-medium text-gray-900 truncate">
              {user?.full_name ?? user?.email}
            </p>
            <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
          </div>
        </div>
        <button
          onClick={logout}
          title="Sign out"
          className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4 shrink-0" />
          <span className="hidden lg:inline">Sign out</span>
        </button>
      </div>
    </aside>
  )
}
