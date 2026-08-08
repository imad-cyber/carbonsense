import { useQuery } from '@tanstack/react-query'
import { companiesApi } from '@/api/companies'

interface Props {
  value: number | null
  onChange: (companyId: number) => void
  className?: string
}

/** Dropdown of all companies — auto-selects the first one when data loads. */
export function CompanySelect({ value, onChange, className }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['companies', 'all'],
    queryFn: () => companiesApi.list(1, 100),
  })

  const companies = data?.items ?? []

  if (!isLoading && companies.length > 0 && value === null) {
    onChange(companies[0].id)
  }

  return (
    <select
      value={value ?? ''}
      onChange={(e) => onChange(Number(e.target.value))}
      disabled={isLoading || companies.length === 0}
      className={
        className ??
        'px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500 min-w-[180px]'
      }
    >
      {isLoading && <option>Loading…</option>}
      {!isLoading && companies.length === 0 && <option>No companies</option>}
      {companies.map((c) => (
        <option key={c.id} value={c.id}>{c.name}</option>
      ))}
    </select>
  )
}
