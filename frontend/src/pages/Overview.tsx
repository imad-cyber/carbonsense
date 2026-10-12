import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type Company, type EmissionRow, type Scope, type Summary } from "../api";
import { MONTHS, SCOPE_COLOR, SCOPE_NAME, num, tonnes } from "../format";

interface MonthRow { month: string; scope_1: number; scope_2: number; scope_3: number }
const SCOPES: Scope[] = ["scope_1", "scope_2", "scope_3"];

export default function Overview({ company }: { company: Company }) {
  const [year, setYear] = useState(2024);
  const [data, setData] = useState<{ summary: Summary; rows: EmissionRow[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    Promise.all([
      api<Summary>(`/emissions/summary/${company.id}/${year}`),
      api<{ items: EmissionRow[] }>(`/emissions/company/${company.id}?year=${year}&page_size=200`),
    ])
      .then(([summary, list]) => {
        if (!cancelled) setData({ summary, rows: list.items });
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [company.id, year]);

  const monthly: MonthRow[] = MONTHS.map((month) => ({ month, scope_1: 0, scope_2: 0, scope_3: 0 }));
  for (const r of data?.rows ?? []) {
    if (r.reporting_month && r.reporting_month >= 1 && r.reporting_month <= 12) {
      monthly[r.reporting_month - 1][r.scope] += r.co2_tonnes;
    }
  }
  const totals: Record<Scope, number> | null = data
    ? {
        scope_1: data.summary.scope_1_total,
        scope_2: data.summary.scope_2_total,
        scope_3: data.summary.scope_3_total,
      }
    : null;

  return (
    <section>
      <div className="row">
        <h2>{company.name}</h2>
        <label>
          Year{" "}
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {[2022, 2023, 2024].map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </label>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="muted">Loading…</p>}
      {data && totals && (
        <>
          <div className="cards">
            {SCOPES.map((s) => (
              <div className="card stat" key={s}>
                <div className="label">{SCOPE_NAME[s]}</div>
                <div className="value">{num(totals[s])} t</div>
              </div>
            ))}
            <div className="card stat">
              <div className="label">Total</div>
              <div className="value">{num(data.summary.grand_total)} t</div>
            </div>
          </div>
          <div className="chart">
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={monthly}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis tickFormatter={(v: number) => num(v)} />
                <Tooltip formatter={(v) => tonnes(Number(v))} />
                <Legend />
                {SCOPES.map((s) => (
                  <Bar key={s} dataKey={s} name={SCOPE_NAME[s]} stackId="a" fill={SCOPE_COLOR[s]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="muted">
            Scope 3 here contains only fuel- and energy-related upstream emissions (fuel supply chains,
            electricity generation inputs and grid losses). Purchased goods, travel and other categories are
            not part of this demo dataset. Totals are in tonnes CO₂e.
          </p>
        </>
      )}
    </section>
  );
}
