import { apiClient } from './client'
import type {
  EmissionCreate, EmissionListResponse, EmissionRecord,
  EmissionScope, EmissionSummary,
} from '@/types/emission'
import type { TaskResponse } from '@/types/task'

export const emissionsApi = {
  listByCompany: (
    companyId: number,
    params?: { year?: number; scope?: EmissionScope; page?: number; page_size?: number }
  ) =>
    apiClient
      .get<EmissionListResponse>(`/emissions/company/${companyId}`, { params })
      .then(r => r.data),

  get: (id: number) =>
    apiClient.get<EmissionRecord>(`/emissions/${id}`).then(r => r.data),

  create: (data: EmissionCreate) =>
    apiClient.post<EmissionRecord>('/emissions/', data).then(r => r.data),

  update: (id: number, data: Partial<EmissionCreate>) =>
    apiClient.patch<EmissionRecord>(`/emissions/${id}`, data).then(r => r.data),

  delete: (id: number) =>
    apiClient.delete(`/emissions/${id}`),

  getSummary: (companyId: number, year: number) =>
    apiClient
      .get<EmissionSummary>(`/emissions/summary/${companyId}/${year}`)
      .then(r => r.data),

  bulkUpload: (companyId: number, records: Omit<EmissionCreate, 'company_id'>[]) =>
    apiClient
      .post<TaskResponse>(`/emissions/bulk/${companyId}`, { records })
      .then(r => r.data),

  triggerReport: (companyId: number, year: number) =>
    apiClient
      .post<TaskResponse>(`/emissions/report/${companyId}/${year}`)
      .then(r => r.data),
}
