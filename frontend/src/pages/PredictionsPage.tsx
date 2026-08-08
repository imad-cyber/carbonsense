import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { BrainCircuit, AlertTriangle, RefreshCw } from 'lucide-react'
import { predictionsApi } from '@/api/predictions'
import { getErrorMessage } from '@/api/client'
import { PageHeader } from '@/components/layout/PageHeader'
import { CompanySelect } from '@/components/CompanySelect'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { toast } from '@/components/ui/Toast'
import { ForecastChart } from '@/components/charts/ForecastChart'
import { AnomalyScatterChart } from '@/components/charts/AnomalyScatterChart'
import { useAuthStore } from '@/store/authStore'
import { formatCO2, SCOPE_LABELS, CATEGORY_LABELS, formatMonthYear } from '@/utils/formatters'
import { SCOPE_CATEGORIES, YEARS, MONTHS } from '@/utils/constants'
import type { EmissionScope, EmissionCategory } from '@/types/emission'
import type { ForecastResult, AnomalyResult } from '@/types/prediction'

const selectClass =
  'w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary-500'

export function PredictionsPage() {
  const [companyId, setCompanyId] = useState<number | null>(null)
  const hasRole = useAuthStore((s) => s.hasRole)

  const { data: status } = useQuery({
    queryKey: ['model-status'],
    queryFn: predictionsApi.status,
  })

  const retrain = useMutation({
    mutationFn: predictionsApi.triggerRetrain,
    onSuccess: () => toast.info('Retraining queued — this runs in the background'),
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const modelsReady = status?.forecasting_model || status?.anomaly_detector

  return (
    <div className="space-y-6">
      <PageHeader
        title="Predictions"
        subtitle="ML-powered forecasting and anomaly detection"
        actions={
          <div className="flex items-center gap-3">
            {status && (
              <div className="flex gap-2">
                <Badge variant={status.forecasting_model ? 'success' : 'default'}>
                  Forecast {status.forecasting_model ? 'ready' : 'not trained'}
                </Badge>
                <Badge variant={status.anomaly_detector ? 'success' : 'default'}>
                  Anomaly {status.anomaly_detector ? 'ready' : 'not trained'}
                </Badge>
              </div>
            )}
            {hasRole(['admin']) && (
              <Button variant="secondary" size="sm" onClick={() => retrain.mutate()} isLoading={retrain.isPending}>
                <RefreshCw className="w-3.5 h-3.5" /> Retrain
              </Button>
            )}
            <CompanySelect value={companyId} onChange={setCompanyId} />
          </div>
        }
      />

      {!modelsReady && status && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-800">
          Models are not trained yet. Run <code className="font-mono bg-amber-100 px-1 rounded">make train</code>{' '}
          on the backend or trigger a retrain to enable predictions.
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <ForecastPanel companyId={companyId} disabled={!status?.forecasting_model} />
        <AnomalyPanel companyId={companyId} disabled={!status?.anomaly_detector} />
      </div>
    </div>
  )
}

function ForecastPanel({ companyId, disabled }: { companyId: number | null; disabled: boolean }) {
  const [scope, setScope] = useState<EmissionScope>('scope_1')
  const [category, setCategory] = useState<EmissionCategory>('stationary_combustion')
  const [year, setYear] = useState(2025)
  const [month, setMonth] = useState(1)
  const [result, setResult] = useState<ForecastResult | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      predictionsApi.forecast({
        company_id: companyId!,
        scope, category,
        reporting_year: year,
        reporting_month: month,
      }),
    onSuccess: setResult,
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  return (
    <Card title="Emission forecast" subtitle="XGBoost prediction with SHAP explanation">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <select
            value={scope}
            onChange={(e) => {
              const s = e.target.value as EmissionScope
              setScope(s)
              setCategory(SCOPE_CATEGORIES[s][0])
            }}
            className={selectClass}
          >
            {(['scope_1', 'scope_2', 'scope_3'] as const).map((s) => (
              <option key={s} value={s}>{SCOPE_LABELS[s]}</option>
            ))}
          </select>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value as EmissionCategory)}
            className={selectClass}
          >
            {SCOPE_CATEGORIES[scope].map((c) => (
              <option key={c} value={c}>{CATEGORY_LABELS[c]}</option>
            ))}
          </select>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))} className={selectClass}>
            {[...YEARS, 2026].map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))} className={selectClass}>
            {MONTHS.map((m) => <option key={m} value={m}>Month {m}</option>)}
          </select>
        </div>

        <Button
          onClick={() => mutation.mutate()}
          isLoading={mutation.isPending}
          disabled={disabled || companyId === null}
          className="w-full"
        >
          <BrainCircuit className="w-4 h-4" /> Run forecast
        </Button>

        {result && (
          <div className="pt-2 border-t border-gray-100 space-y-4">
            <div className="text-center py-2">
              <p className="text-xs text-gray-500 uppercase tracking-wider">
                Predicted for {formatMonthYear(result.reporting_year, result.reporting_month)}
              </p>
              <p className="text-3xl font-bold text-primary-700 mt-1">
                {formatCO2(result.predicted_co2_tonnes)}
              </p>
            </div>
            <div>
              <p className="text-xs font-semibold text-gray-700 mb-2">Why this prediction? (SHAP drivers)</p>
              <ForecastChart explanation={result.explanation} />
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}

function AnomalyPanel({ companyId, disabled }: { companyId: number | null; disabled: boolean }) {
  const [year, setYear] = useState(2024)
  const [result, setResult] = useState<AnomalyResult | null>(null)

  const mutation = useMutation({
    mutationFn: () => predictionsApi.detectAnomalies(companyId!, year),
    onSuccess: setResult,
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  return (
    <Card title="Anomaly detection" subtitle="Isolation Forest scan of emission records">
      <div className="space-y-4">
        <div className="flex gap-3">
          <select value={year} onChange={(e) => setYear(Number(e.target.value))} className={selectClass}>
            {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
          <Button
            onClick={() => mutation.mutate()}
            isLoading={mutation.isPending}
            disabled={disabled || companyId === null}
            className="shrink-0"
          >
            <AlertTriangle className="w-4 h-4" /> Scan
          </Button>
        </div>

        {result === null ? (
          <EmptyState
            icon={AlertTriangle}
            title="No scan yet"
            description="Run an anomaly scan to spot suspicious emission records."
          />
        ) : (
          <>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-gray-600">
                {result.total_records} records scanned
              </span>
              <Badge variant={result.anomaly_count > 0 ? 'danger' : 'success'}>
                {result.anomaly_count} anomalies ({(result.anomaly_rate * 100).toFixed(1)}%)
              </Badge>
            </div>
            <AnomalyScatterChart records={result.records} />
            {result.anomaly_count > 0 && (
              <div className="space-y-1.5 max-h-48 overflow-y-auto scrollbar-thin">
                {result.records.filter((r) => r.is_anomaly).map((r) => (
                  <div
                    key={r.record_id}
                    className="flex items-center justify-between text-xs bg-red-50 border border-red-100 rounded-lg px-3 py-2"
                  >
                    <span className="text-gray-700">
                      {SCOPE_LABELS[r.scope]} · {CATEGORY_LABELS[r.category] ?? r.category} ·{' '}
                      {formatMonthYear(r.reporting_year, r.reporting_month)}
                    </span>
                    <span className="flex items-center gap-2">
                      <span className="font-medium">{formatCO2(r.co2_tonnes)}</span>
                      <Badge variant={r.anomaly_severity === 'high' ? 'danger' : 'warning'}>
                        {r.anomaly_severity ?? 'flagged'}
                      </Badge>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </Card>
  )
}
