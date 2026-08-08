import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import type { EmissionSummary } from '@/types/emission'
import { formatCO2 } from '@/utils/formatters'
import { EmptyState } from '@/components/ui/EmptyState'
import { PieChart as PieIcon } from 'lucide-react'

interface Props { summary: EmissionSummary }

export function ScopeBreakdownChart({ summary }: Props) {
  const data = [
    { name: 'Scope 1 (Direct)', value: summary.scope_1_total, color: '#ef4444' },
    { name: 'Scope 2 (Energy)', value: summary.scope_2_total, color: '#f59e0b' },
    { name: 'Scope 3 (Value chain)', value: summary.scope_3_total, color: '#8b5cf6' },
  ].filter(d => d.value > 0)

  if (data.length === 0) {
    return (
      <EmptyState
        icon={PieIcon}
        title="No emission data"
        description="Add emission records to see the scope breakdown."
      />
    )
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={70}
          outerRadius={100}
          paddingAngle={3}
          dataKey="value"
        >
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.color} stroke="none" />
          ))}
        </Pie>
        <Tooltip formatter={(value) => [formatCO2(Number(value)), 'CO₂e']} />
        <Legend
          formatter={(value) => <span className="text-xs text-gray-600">{value}</span>}
        />
      </PieChart>
    </ResponsiveContainer>
  )
}
