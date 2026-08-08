import { DataTable, type Column } from '@/components/ui/DataTable'
import { Badge, scopeBadgeVariant } from '@/components/ui/Badge'
import type { EmissionRecord } from '@/types/emission'
import { CATEGORY_LABELS, SCOPE_LABELS, formatCO2 } from '@/utils/formatters'

interface Props {
  records: EmissionRecord[]
  isLoading?: boolean
}

const columns: Column<EmissionRecord>[] = [
  {
    key: 'scope',
    header: 'Scope',
    render: (r) => <Badge variant={scopeBadgeVariant(r.scope)}>{SCOPE_LABELS[r.scope]}</Badge>,
  },
  {
    key: 'category',
    header: 'Category',
    render: (r) => CATEGORY_LABELS[r.category] ?? r.category,
  },
  {
    key: 'co2',
    header: 'CO₂e',
    render: (r) => <span className="font-medium">{formatCO2(r.co2_tonnes)}</span>,
  },
  { key: 'year', header: 'Year', render: (r) => r.reporting_year },
  { key: 'month', header: 'Month', render: (r) => r.reporting_month ?? '—' },
  { key: 'source', header: 'Source', render: (r) => r.data_source ?? '—' },
]

export function EmissionTable({ records, isLoading }: Props) {
  return (
    <DataTable
      columns={columns}
      data={records}
      keyExtractor={(r) => r.id}
      isLoading={isLoading}
      emptyMessage="No emission records found for the selected filters"
    />
  )
}
