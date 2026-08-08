import { clsx } from 'clsx'
import type { PredictionExplanation } from '@/types/prediction'
import { formatCO2 } from '@/utils/formatters'

interface Props { explanation: PredictionExplanation }

/**
 * SHAP driver visualisation — horizontal bar list from base value to
 * final prediction. Red bars push emissions up, green bars pull down.
 */
export function ForecastChart({ explanation }: Props) {
  const maxAbs = Math.max(
    ...explanation.top_drivers.map((d) => Math.abs(d.shap_value)),
    1,
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>Base value: {formatCO2(explanation.base_value)}</span>
        <span>Prediction: {formatCO2(explanation.prediction)}</span>
      </div>

      <div className="space-y-2">
        {explanation.top_drivers.slice(0, 5).map((driver) => {
          const widthPct = Math.max((Math.abs(driver.shap_value) / maxAbs) * 100, 4)
          const increases = driver.direction === 'increases_emission'
          return (
            <div key={driver.feature}>
              <div className="flex items-center justify-between text-xs mb-0.5">
                <span className="font-mono text-gray-700">{driver.feature}</span>
                <span className={clsx('font-medium', increases ? 'text-red-600' : 'text-green-600')}>
                  {increases ? '+' : ''}{driver.shap_value.toFixed(1)} t
                </span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={clsx('h-full rounded-full', increases ? 'bg-red-400' : 'bg-green-400')}
                  style={{ width: `${widthPct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      <p className="text-xs text-gray-400">Method: {explanation.explanation_method}</p>
    </div>
  )
}
