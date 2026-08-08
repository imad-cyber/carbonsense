import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import type { AnomalyRecord } from '@/types/prediction'

interface Props { records: AnomalyRecord[] }

export function AnomalyScatterChart({ records }: Props) {
  const normal = records.filter(r => !r.is_anomaly)
  const anomalies = records.filter(r => r.is_anomaly)

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis
          dataKey="reporting_month"
          name="Month"
          type="number"
          domain={[1, 12]}
          tickCount={12}
          tick={{ fontSize: 11 }}
        />
        <YAxis dataKey="co2_tonnes" name="CO₂e (t)" tick={{ fontSize: 11 }} width={70} />
        <Tooltip cursor={{ strokeDasharray: '3 3' }} />
        <Legend />
        <ReferenceLine y={0} stroke="#e5e7eb" />
        <Scatter name="Normal" data={normal} fill="#22c55e" fillOpacity={0.6} />
        <Scatter name="Anomaly" data={anomalies} fill="#ef4444" fillOpacity={0.9} />
      </ScatterChart>
    </ResponsiveContainer>
  )
}
