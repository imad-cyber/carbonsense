import { apiClient } from './client'
import type {
  AnomalyResult, FeatureImportanceItem, ForecastResult, ModelStatus,
} from '@/types/prediction'
import type { TaskResponse } from '@/types/task'

export const predictionsApi = {
  status: () =>
    apiClient.get<ModelStatus>('/predictions/status').then(r => r.data),

  forecast: (data: {
    company_id: number
    scope: string
    category: string
    reporting_year: number
    reporting_month: number
  }) =>
    apiClient.post<ForecastResult>('/predictions/forecast', data).then(r => r.data),

  detectAnomalies: (companyId: number, year: number) =>
    apiClient
      .post<AnomalyResult>('/predictions/anomalies', {
        company_id: companyId,
        year,
      })
      .then(r => r.data),

  featureImportance: () =>
    apiClient
      .get<{ feature_importance: FeatureImportanceItem[] }>('/predictions/feature-importance')
      .then(r => r.data),

  triggerRetrain: () =>
    apiClient.post<TaskResponse>('/predictions/retrain').then(r => r.data),
}
