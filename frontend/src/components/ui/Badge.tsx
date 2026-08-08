import { type ReactNode } from 'react'
import { clsx } from 'clsx'

interface BadgeProps {
  children: ReactNode
  variant?: 'default' | 'scope1' | 'scope2' | 'scope3' | 'success' | 'warning' | 'danger' | 'info'
  className?: string
}

const VARIANTS = {
  default: 'bg-gray-100 text-gray-700',
  scope1: 'bg-red-100 text-red-700',
  scope2: 'bg-amber-100 text-amber-700',
  scope3: 'bg-purple-100 text-purple-700',
  success: 'bg-green-100 text-green-700',
  warning: 'bg-amber-100 text-amber-700',
  danger: 'bg-red-100 text-red-700',
  info: 'bg-blue-100 text-blue-700',
}

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
        VARIANTS[variant],
        className,
      )}
    >
      {children}
    </span>
  )
}

export function scopeBadgeVariant(scope: string): 'scope1' | 'scope2' | 'scope3' | 'default' {
  if (scope === 'scope_1') return 'scope1'
  if (scope === 'scope_2') return 'scope2'
  if (scope === 'scope_3') return 'scope3'
  return 'default'
}
