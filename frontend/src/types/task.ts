export type TaskStatus = 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE' | 'RETRY'

export interface TaskResponse {
  task_id: string
  status: string
  message: string
}

export interface TaskResult {
  task_id: string
  status: TaskStatus
  result?: Record<string, unknown>
  error?: string
}
