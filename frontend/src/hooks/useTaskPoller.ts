import { useState, useEffect } from 'react'
import { tasksApi } from '@/api/tasks'
import type { TaskResult, TaskStatus } from '@/types/task'

const TERMINAL_STATES: TaskStatus[] = ['SUCCESS', 'FAILURE']
const POLL_INTERVAL_MS = 2000

/**
 * Polls /tasks/{taskId} every 2 seconds until the task reaches a
 * terminal state (SUCCESS or FAILURE).
 * Used after bulk uploads, retraining and CSRD report generation.
 */
export function useTaskPoller(taskId: string | null) {
  const [result, setResult] = useState<TaskResult | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!taskId) {
      setResult(null)
      setIsPolling(false)
      return
    }

    let cancelled = false
    setResult(null)
    setError(null)
    setIsPolling(true)

    const interval = setInterval(async () => {
      try {
        const data = await tasksApi.getStatus(taskId)
        if (cancelled) return
        setResult(data)

        if (TERMINAL_STATES.includes(data.status)) {
          clearInterval(interval)
          setIsPolling(false)
        }
      } catch (err) {
        if (cancelled) return
        clearInterval(interval)
        setIsPolling(false)
        setError(err instanceof Error ? err.message : 'Polling failed')
      }
    }, POLL_INTERVAL_MS)

    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [taskId])

  return { result, isPolling, error }
}
