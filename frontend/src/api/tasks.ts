import { apiClient } from './client'
import type { TaskResult } from '@/types/task'

export const tasksApi = {
  getStatus: (taskId: string) =>
    apiClient.get<TaskResult>(`/tasks/${taskId}`).then(r => r.data),
}
