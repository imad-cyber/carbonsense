import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Flame, Zap, Truck, Layers, Radio } from 'lucide-react'
import { emissionsApi } from '@/api/emissions'
import { PageHeader } from '@/components/layout/PageHeader'
import { CompanySelect } from '@/components/CompanySelect'
import { StatCard } from '@/components/ui/StatCard'
import { Card } from '@/components/ui/Card'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { ScopeBreakdownChart } from '@/components/charts/ScopeBreakdownChart'
import { EmissionTrendChart, type TrendPoint } from '@/components/charts/EmissionTrendChart'
import { useWebSocket, type WsMessage } from '@/hooks/useWebSocket'
import { toast } from '@/components/ui/Toast'
import { formatCO2, formatNumber } from '@/utils/formatters'
import { YEARS } from '@/utils/constants'
import type { EmissionScope } from '@/types/emission'

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function DashboardPage() {
  const [companyId, setCompanyId] = useState<number | null>(null)
  const [year, setYear] = useState(2024)
  const [liveEvents, setLiveEvents] = useState<WsMessage[]>([])

  const { isConnected } = useWebSocket({
    companyId: companyId ?? undefined,
    onMessage: (msg) => {
      if (msg.type === 'emission_created' || msg.type === 'anomaly_detected') {
        setLiveEvents((prev) => [msg, ...prev].slice(0, 10))
      }
    },
    onAnomalyAlert: (payload) => {
      toast.error(`Anomaly detected: ${formatCO2(Number(payload.co2_tonnes ?? 0))} (score ${Number(payload.anomaly_score ?? 0).toFixed(2)})`)
    },
  })

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ['summary', companyId, year],
    queryFn: () => emissionsApi.getSummary(companyId!, year),
    enabled: companyId !== null,
  })

  const { data: emissions } = useQuery({
    queryKey: ['emissions', companyId, year, 'trend'],
    queryFn: () => emissionsApi.listByCompany(companyId!, { year, page: 1, page_size: 100 }),
    enabled: companyId !== null,
  })

  const trendData = useMemo<TrendPoint[]>(() => {
    if (!emissions?.items) return []
    const byMonth = new Map<number, Record<EmissionScope, number>>()
    for (const r of emissions.items) {
      if (!r.reporting_month) continue
      const entry = byMonth.get(r.reporting_month) ?? { scope_1: 0, scope_2: 0, scope_3: 0 }
      entry[r.scope] += r.co2_tonnes
      byMonth.set(r.reporting_month, entry)
    }
    return [...byMonth.entries()]
      .sort(([a], [b]) => a - b)
      .map(([month, scopes]) => ({ month: MONTH_NAMES[month - 1], ...scopes }))
  }, [emissions])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle="Carbon footprint overview"
        actions={
          <div className="flex items-center gap-3">
            <CompanySelect value={companyId} onChange={setCompanyId} />
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        }
      />

      {summaryLoading && <LoadingSpinner label="Loading summary…" />}

      {summary && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <StatCard
              label="Total emissions" value={formatCO2(summary.grand_total, true)}
              icon={Layers}
            />
            <StatCard
              label="Scope 1 · Direct" value={formatCO2(summary.scope_1_total, true)}
              icon={Flame} variant="scope1"
            />
            <StatCard
              label="Scope 2 · Energy" value={formatCO2(summary.scope_2_total, true)}
              icon={Zap} variant="scope2"
            />
            <StatCard
              label="Scope 3 · Value chain" value={formatCO2(summary.scope_3_total, true)}
              icon={Truck} variant="scope3"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card title="Scope breakdown" subtitle={`${formatNumber(summary.record_count)} records in ${year}`}>
              <ScopeBreakdownChart summary={summary} />
            </Card>
            <Card title="Monthly trend" subtitle="Emissions by scope over the year">
              <EmissionTrendChart data={trendData} />
            </Card>
          </div>
        </>
      )}

      <Card
        title="Live feed"
        subtitle="Real-time emission events via WebSocket"
        actions={
          <span className="flex items-center gap-1.5 text-xs text-gray-500">
            <Radio className={isConnected ? 'w-3.5 h-3.5 text-green-500' : 'w-3.5 h-3.5 text-gray-300'} />
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        }
      >
        {liveEvents.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-4">
            No live events yet — new emission records will appear here in real time.
          </p>
        ) : (
          <ul className="space-y-2">
            {liveEvents.map((evt, i) => (
              <li key={i} className="flex items-center gap-3 text-sm py-1.5 border-b border-gray-50 last:border-0">
                <span
                  className={
                    evt.type === 'anomaly_detected'
                      ? 'w-2 h-2 rounded-full bg-red-500 shrink-0'
                      : 'w-2 h-2 rounded-full bg-green-500 shrink-0'
                  }
                />
                <span className="font-medium text-gray-700">
                  {evt.type === 'anomaly_detected' ? 'Anomaly detected' : 'Emission created'}
                </span>
                <span className="text-gray-500">
                  {formatCO2(Number(evt.payload.co2_tonnes ?? 0))}
                </span>
                <span className="text-xs text-gray-400 ml-auto">
                  {new Date(evt.timestamp).toLocaleTimeString()}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
