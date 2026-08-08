export type EmissionScope = 'scope_1' | 'scope_2' | 'scope_3'

export type EmissionCategory =
  | 'stationary_combustion' | 'mobile_combustion'
  | 'purchased_electricity' | 'purchased_heat'
  | 'business_travel' | 'employee_commuting'
  | 'supply_chain' | 'waste'

export interface EmissionRecord {
  id: number
  company_id: number
  scope: EmissionScope
  category: EmissionCategory
  co2_tonnes: number
  reporting_year: number
  reporting_month: number | null
  data_source: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface EmissionSummary {
  company_id: number
  reporting_year: number
  scope_1_total: number
  scope_2_total: number
  scope_3_total: number
  grand_total: number
  record_count: number
}

export interface EmissionCreate {
  company_id: number
  scope: EmissionScope
  category: EmissionCategory
  co2_tonnes: number
  reporting_year: number
  reporting_month?: number
  data_source?: string
  notes?: string
}

export interface EmissionListResponse {
  items: EmissionRecord[]
  total: number
  page: number
  page_size: number
}
