import { type ReactNode } from 'react'
import { clsx } from 'clsx'

interface CardProps {
  title?: string
  subtitle?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  noPadding?: boolean
}

export function Card({ title, subtitle, actions, children, className, noPadding }: CardProps) {
  return (
    <div className={clsx('bg-white rounded-xl border border-gray-200', className)}>
      {(title || actions) && (
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <div>
            {title && <h3 className="text-sm font-semibold text-gray-900">{title}</h3>}
            {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      <div className={noPadding ? undefined : 'p-5'}>{children}</div>
    </div>
  )
}
