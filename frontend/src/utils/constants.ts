import type { EmissionCategory, EmissionScope } from '@/types/emission'
import type { IndustrySector } from '@/types/company'
import type { UserRole } from '@/types/auth'

export const SCOPES: EmissionScope[] = ['scope_1', 'scope_2', 'scope_3']

/** Valid categories per scope — mirrors the backend's GHG Protocol mapping */
export const SCOPE_CATEGORIES: Record<EmissionScope, EmissionCategory[]> = {
  scope_1: ['stationary_combustion', 'mobile_combustion'],
  scope_2: ['purchased_electricity', 'purchased_heat'],
  scope_3: ['business_travel', 'employee_commuting', 'supply_chain', 'waste'],
}

export const SECTORS: IndustrySector[] = [
  'energy', 'manufacturing', 'transport', 'finance',
  'technology', 'retail', 'healthcare', 'other',
]

export const ROLES: UserRole[] = ['admin', 'analyst', 'auditor', 'supplier']

export const YEARS = [2022, 2023, 2024, 2025]

export const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

export const SUGGESTED_QUESTIONS = [
  'What are Scope 3 reporting requirements under ESRS E1?',
  'What is the CSRD double materiality assessment?',
  'Which companies must report under CSRD in 2024?',
  'What verification requirements does CSRD mandate?',
  'How do I calculate Scope 2 market-based emissions?',
]

export const ROLE_BADGE_STYLES: Record<UserRole, string> = {
  admin: 'bg-red-100 text-red-700',
  analyst: 'bg-blue-100 text-blue-700',
  auditor: 'bg-amber-100 text-amber-700',
  supplier: 'bg-gray-100 text-gray-600',
}
