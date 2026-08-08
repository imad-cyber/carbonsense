import { type LucideIcon } from 'lucide-react'
import { clsx } from 'clsx'

interface StatCardProps {
  label: string
  value: string | number
  unit?: string
  icon?: LucideIcon
  trend?: { value: number; label: string }
  variant?: 'default' | 'scope1' | 'scope2' | 'scope3' | 'danger'
}

const VARIANTS = {
  default: 'bg-white border-gray-200',
  scope1: 'bg-red-50 border-red-200',
  scope2: 'bg-amber-50 border-amber-200',
  scope3: 'bg-purple-50 border-purple-200',
  danger: 'bg-red-50 border-red-300',
}

const ICON_VARIANTS = {
  default: 'bg-gray-100 text-gray-600',
  scope1: 'bg-red-100 text-red-600',
  scope2: 'bg-amber-100 text-amber-600',
  scope3: 'bg-purple-100 text-purple-600',
  danger: 'bg-red-100 text-red-600',
}

export function StatCard({
  label, value, unit, icon: Icon, trend, variant = 'default',
}: StatCardProps) {
  return (
    <div className={clsx('rounded-xl border p-5', VARIANTS[variant])}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{label}</p>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-2xl font-bold text-gray-900">{value}</span>
            {unit && <span className="text-sm text-gray-500">{unit}</span>}
          </div>
          {trend && (
            <p className={clsx(
              'mt-1 text-xs font-medium',
              // For emissions, DOWN is good
              trend.value < 0 ? 'text-green-600' : 'text-red-600'
            )}>
              {trend.value > 0 ? '▲' : '▼'} {Math.abs(trend.value)}% {trend.label}
            </p>
          )}
        </div>
        {Icon && (
          <div className={clsx('p-2 rounded-lg', ICON_VARIANTS[variant])}>
            <Icon className="w-5 h-5" />
          </div>
        )}
      </div>
    </div>
  )
}
