import { useEffect, useState } from "react";
import { api, type AnomalyResponse, type Company, type Finding } from "../api";
import { MONTHS, SCOPE_NAME, categoryName, num } from "../format";

function reason(f: Finding): string {
  const m = f.times_same_month;
  const month = MONTHS[f.reporting_month - 1] ?? "month";
  if (m === null) return "Unusual pattern for this series.";
  if (m >= 1.5 || m <= 0.67) return `${m.toFixed(2)}× the usual ${month}.`;
  return `Close to the usual ${month} (${m.toFixed(2)}×) but flagged for its month-to-month pattern. This often happens right after an unusual month.`;
}

export default function Findings({ company }: { company: Company }) {
  const [year, setYear] = useState(2023);
  const [res, setRes] = useState<AnomalyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setRes(null);
    setError(null);
    api<AnomalyResponse>("/predictions/anomalies", {
      method: "POST",
      body: { company_id: company.id, year },
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
  }, [company.id, year]);

  return (
    <section>
      <div className="row">
        <h2>Findings to review</h2>
        <label>
          Year{" "}
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {[2022, 2023, 2024].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="muted">
        The detector compares each activity with the same calendar month in other years. It flags the most
        unusual 5% of records as a review queue, so a clean company would still get flags. Severity: high is
        2× the usual month or more (or half or less), medium is 1.5× (or 0.67×).
      </p>
      <p className="notice">
        In this demo three anomalies were planted by the author: diesel in September 2022, gas in February
        2023 and electricity in June 2024. Every other finding is not planted.
      </p>
      {error && <p className="error">{error}</p>}
      {!res && !error && <p className="muted">Scanning…</p>}
      {res && (
        <>
          <p>
            {res.findings.length} findings in {res.total_records} records ({res.anomaly_count} records flagged).
          </p>
          {res.findings.map((f) => (
            <article
              className="card"
              key={f.activity_group_id ?? `${f.reporting_year}-${f.reporting_month}-${f.records[0].record_id}`}
            >
              <div className="row">
                <h3>{MONTHS[f.reporting_month - 1]} {f.reporting_year}</h3>
                <span className={`sev sev-${f.severity}`}>{f.severity}</span>
              </div>
              <p>{reason(f)}</p>
              <table>
                <tbody>
                  {f.records.map((r) => (
                    <tr key={r.record_id}>
                      <td>{SCOPE_NAME[r.scope]}: {categoryName(r.category)}</td>
                      <td className="n">{num(r.co2_tonnes)} t</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </article>
          ))}
          {res.findings.length === 0 && <p className="muted">No findings for this year.</p>}
        </>
      )}
    </section>
  );
}
