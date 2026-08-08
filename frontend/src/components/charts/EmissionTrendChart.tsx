import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { formatCO2 } from '@/utils/formatters'
import { EmptyState } from '@/components/ui/EmptyState'
import { TrendingUp } from 'lucide-react'

export interface TrendPoint {
  month: string
  scope_1: number
  scope_2: number
  scope_3: number
}

interface Props { data: TrendPoint[] }

export function EmissionTrendChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <EmptyState
        icon={TrendingUp}
        title="No trend data"
        description="Monthly emission records are needed to plot the trend."
      />
    )
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="month" tick={{ fontSize: 11 }} />
        <YAxis tickFormatter={(v) => formatCO2(Number(v), true)} tick={{ fontSize: 11 }} width={80} />
        <Tooltip formatter={(v) => formatCO2(Number(v))} />
        <Legend />
        <Line type="monotone" dataKey="scope_1" stroke="#ef4444" strokeWidth={2} dot={false} name="Scope 1" />
        <Line type="monotone" dataKey="scope_2" stroke="#f59e0b" strokeWidth={2} dot={false} name="Scope 2" />
        <Line type="monotone" dataKey="scope_3" stroke="#8b5cf6" strokeWidth={2} dot={false} name="Scope 3" />
      </LineChart>
    </ResponsiveContainer>
  )
}
