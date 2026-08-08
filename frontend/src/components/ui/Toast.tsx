import { create } from 'zustand'
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react'
import { clsx } from 'clsx'

type ToastType = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  type: ToastType
  message: string
}

interface ToastState {
  toasts: ToastItem[]
  push: (type: ToastType, message: string) => void
  dismiss: (id: number) => void
}

let nextId = 1

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (type, message) => {
    const id = nextId++
    set((s) => ({ toasts: [...s.toasts, { id, type, message }] }))
    setTimeout(() => {
      set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
    }, 5000)
  },
  dismiss: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))

export const toast = {
  success: (msg: string) => useToastStore.getState().push('success', msg),
  error: (msg: string) => useToastStore.getState().push('error', msg),
  info: (msg: string) => useToastStore.getState().push('info', msg),
}

const ICONS = { success: CheckCircle2, error: AlertCircle, info: Info }
const STYLES = {
  success: 'border-green-200 bg-green-50 text-green-800',
  error: 'border-red-200 bg-red-50 text-red-800',
  info: 'border-blue-200 bg-blue-50 text-blue-800',
}

/** Render once at the app root — displays stacked toasts bottom-right. */
export function ToastContainer() {
  const { toasts, dismiss } = useToastStore()

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => {
        const Icon = ICONS[t.type]
        return (
          <div
            key={t.id}
            className={clsx(
              'flex items-start gap-2 px-4 py-3 rounded-lg border shadow-sm text-sm',
              STYLES[t.type],
            )}
          >
            <Icon className="w-4 h-4 mt-0.5 shrink-0" />
            <p className="flex-1">{t.message}</p>
            <button onClick={() => dismiss(t.id)} aria-label="Dismiss">
              <X className="w-3.5 h-3.5 opacity-60 hover:opacity-100" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
