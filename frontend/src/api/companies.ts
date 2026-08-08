import { apiClient } from './client'
import type { Company, CompanyCreate, CompanyListResponse } from '@/types/company'

export const companiesApi = {
  list: (page = 1, pageSize = 20) =>
    apiClient
      .get<CompanyListResponse>('/companies/', { params: { page, page_size: pageSize } })
      .then(r => r.data),

  get: (id: number) =>
    apiClient.get<Company>(`/companies/${id}`).then(r => r.data),

  create: (data: CompanyCreate) =>
    apiClient.post<Company>('/companies/', data).then(r => r.data),

  update: (id: number, data: Partial<CompanyCreate>) =>
    apiClient.patch<Company>(`/companies/${id}`, data).then(r => r.data),

  delete: (id: number) =>
    apiClient.delete(`/companies/${id}`),
}
