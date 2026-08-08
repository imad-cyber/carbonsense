export interface ShapContribution {
  feature: string
  feature_value: number
  shap_value: number
  direction: 'increases_emission' | 'decreases_emission'
}

export interface PredictionExplanation {
  base_value: number
  prediction: number
  top_drivers: ShapContribution[]
  explanation_method: string
}

export interface ForecastResult {
  company_id: number
  scope: string
  category: string
  reporting_year: number
  reporting_month: number
  predicted_co2_tonnes: number
  explanation: PredictionExplanation
}

export interface AnomalyRecord {
  record_id: number
  company_id: number
  scope: string
  category: string
  co2_tonnes: number
  reporting_year: number
  reporting_month: number
  anomaly_score: number
  is_anomaly: boolean
  anomaly_severity: 'high' | 'medium' | 'low' | null
}

export interface AnomalyResult {
  company_id: number
  year: number
  total_records: number
  anomaly_count: number
  anomaly_rate: number
  records: AnomalyRecord[]
}

export interface FeatureImportanceItem {
  feature: string
  importance: number
  rank: number
}

export interface ModelStatus {
  forecasting_model: boolean
  anomaly_detector: boolean
}
