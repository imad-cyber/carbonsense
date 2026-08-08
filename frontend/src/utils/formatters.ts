/**
 * CO₂ formatter — always shows "t CO₂e" unit.
 * compact = true → "45.3k" instead of "45,300"
 */
export function formatCO2(tonnes: number, compact = false): string {
  if (compact) {
    if (tonnes >= 1_000_000) return `${(tonnes / 1_000_000).toFixed(1)}M t CO₂e`
    if (tonnes >= 1_000) return `${(tonnes / 1_000).toFixed(1)}k t CO₂e`
  }
  return `${tonnes.toLocaleString('fr-FR', { maximumFractionDigits: 1 })} t CO₂e`
}

export function formatNumber(n: number): string {
  return n.toLocaleString('fr-FR')
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR', {
    year: 'numeric', month: 'short', day: 'numeric',
  })
}

export function formatMonthYear(year: number, month: number): string {
  return new Date(year, month - 1).toLocaleDateString('fr-FR', {
    year: 'numeric', month: 'short',
  })
}

export const SCOPE_LABELS: Record<string, string> = {
  scope_1: 'Scope 1',
  scope_2: 'Scope 2',
  scope_3: 'Scope 3',
}

export const SCOPE_COLOURS: Record<string, string> = {
  scope_1: '#ef4444',
  scope_2: '#f59e0b',
  scope_3: '#8b5cf6',
}

export const CATEGORY_LABELS: Record<string, string> = {
  stationary_combustion: 'Stationary combustion',
  mobile_combustion: 'Mobile combustion',
  purchased_electricity: 'Purchased electricity',
  purchased_heat: 'Purchased heat',
  business_travel: 'Business travel',
  employee_commuting: 'Employee commuting',
  supply_chain: 'Supply chain',
  waste: 'Waste',
}
