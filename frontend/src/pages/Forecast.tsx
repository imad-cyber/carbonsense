import { useEffect, useState } from "react";
import { api, type Company, type ForecastResult, type Scope } from "../api";
import { SCOPE_NAME, categoryName, num } from "../format";

interface Series { scope: Scope; category: string }
const SERIES: Series[] = [
  { scope: "scope_1", category: "stationary_combustion" },
  { scope: "scope_1", category: "mobile_combustion" },
  { scope: "scope_2", category: "purchased_electricity" },
  { scope: "scope_3", category: "fuel_energy_related" },
];

export default function Forecast({ company }: { company: Company }) {
  const [index, setIndex] = useState(0);
  const [res, setRes] = useState<ForecastResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRes(null);
    setError(null);
    api<ForecastResult>("/predictions/forecast", {
      method: "POST",
      body: {
        company_id: company.id,
        scope: SERIES[index].scope,
        category: SERIES[index].category,
        reporting_year: 2025,
        reporting_month: 1,
      },
    })
      .then((r) => {
        if (!cancelled) setRes(r);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [company.id, index]);

  return (
    <section>
      <div className="row">
        <h2>Forecast for January 2025</h2>
        <label>
          Series{" "}
          <select value={index} onChange={(e) => setIndex(Number(e.target.value))}>
            {SERIES.map((s, i) => (
              <option key={s.category} value={i}>{SCOPE_NAME[s.scope]}: {categoryName(s.category)}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted">Forecasts exist only for the month right after the latest data.</p>
      {error && <p className="error">{error}</p>}
      {!res && !error && <p className="muted">Calculating…</p>}
      {res && (
        <>
          <div className="cards">
            <div className="card stat">
              <div className="label">January 2024 (same month last year)</div>
              <div className="value">{num(res.baseline.same_month_last_year)} t</div>
            </div>
            <div className="card stat">
              <div className="label">Baseline: last year × {res.baseline.trend_factor.toFixed(3)}</div>
              <div className="value">{num(res.baseline.forecast)} t</div>
            </div>
            <div className="card stat">
              <div className="label">XGBoost challenger</div>
              <div className="value">{num(res.challenger.forecast)} t</div>
            </div>
          </div>
          <p>
            Served: <strong>{res.model_used === "xgboost_ratio" ? "XGBoost challenger" : "baseline (same month last year × trend)"}</strong>
          </p>
          {res.models_disagree && (
            <p className="warn">The two forecasts differ by more than 15%. Treat the number with care.</p>
          )}
          <p className="muted">
            The baseline repeats last year's month and applies the typical year-on-year change. The XGBoost
            model only takes over if it beats the baseline in every walk-forward fold by at least half a
            percentage point of WAPE; see the model card for the current numbers.
          </p>
        </>
      )}
    </section>
  );
}
