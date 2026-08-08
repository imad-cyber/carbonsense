export type IndustrySector =
  | 'energy' | 'manufacturing' | 'transport'
  | 'finance' | 'technology' | 'retail'
  | 'healthcare' | 'other'

export interface Company {
  id: number
  name: string
  sector: IndustrySector
  country: string
  description: string | null
  employee_count: number | null
  annual_revenue_eur: number | null
  created_at: string
  updated_at: string
}

export interface CompanyListResponse {
  items: Company[]
  total: number
  page: number
  page_size: number
}

export interface CompanyCreate {
  name: string
  sector: IndustrySector
  country: string
  description?: string
  employee_count?: number
  annual_revenue_eur?: number
}
