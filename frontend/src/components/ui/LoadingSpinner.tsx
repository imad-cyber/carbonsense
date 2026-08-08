import { clsx } from 'clsx'

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string
}

const SIZES = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-10 h-10' }

export function LoadingSpinner({ size = 'md', className, label }: LoadingSpinnerProps) {
  return (
    <div className={clsx('flex flex-col items-center justify-center gap-2', className)}>
      <div
        className={clsx(
          'border-2 border-primary-600 border-t-transparent rounded-full animate-spin',
          SIZES[size],
        )}
      />
      {label && <p className="text-xs text-gray-500">{label}</p>}
    </div>
  )
}
