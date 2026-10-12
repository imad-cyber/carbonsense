import { useState, type FormEvent } from "react";
import { api, type Breakdown, type Company, type Factor, type Scope } from "../api";
import { MONTHS, SCOPE_NAME, categoryName, num, tonnes } from "../format";

interface Option { label: string; scope: Scope; category: string }
interface Preset { label: string; q: string; sourceId: string; optionIndex: number; quantity: number; unit: string }

const OPTIONS: Option[] = [
  { label: "Scope 1: stationary combustion (boilers, heating fuel)", scope: "scope_1", category: "stationary_combustion" },
  { label: "Scope 1: mobile combustion (vehicles)", scope: "scope_1", category: "mobile_combustion" },
  { label: "Scope 2: purchased electricity", scope: "scope_2", category: "purchased_electricity" },
  { label: "Scope 3: supply chain (factor total, no split)", scope: "scope_3", category: "supply_chain" },
];

const PRESETS: Preset[] = [
  { label: "Gas boiler: 50 MWh PCS", q: "Gaz naturel - 2022", sourceId: "37133", optionIndex: 0, quantity: 50, unit: "MWh PCS" },
  { label: "Fleet diesel: 1,000 litres", q: "Gazole routier - B7", sourceId: "25775", optionIndex: 1, quantity: 1000, unit: "litre" },
  { label: "Grid electricity: 100 MWh", q: "2022 - mix moyen - consommation", sourceId: "42513", optionIndex: 2, quantity: 100, unit: "MWh" },
];

function ResultView({ result }: { result: Breakdown }) {
  const direct = result.slices[0]?.co2_tonnes ?? 0;
  const overstated =
    result.slices.length > 1 && direct > 0 ? (result.co2_tonnes_total / direct - 1) * 100 : null;
  return (
    <div className="card">
      <h3>Result</h3>
      <p className="formula">{result.formula}</p>
      <table>
        <thead>
          <tr>
            <th>Booked as</th>
            <th>Part of the factor</th>
            <th className="n">kg CO₂e per unit</th>
            <th className="n">Emissions</th>
            <th>Range (factor uncertainty)</th>
          </tr>
        </thead>
        <tbody>
          {result.slices.map((s) => (
            <tr key={`${s.scope}-${s.category}-${s.post_type}`}>
              <td>{SCOPE_NAME[s.scope]}: {categoryName(s.category)}</td>
              <td>{s.post_type}</td>
              <td className="n">{String(s.kg_co2e_per_unit)}</td>
              <td className="n">{tonnes(s.co2_tonnes)}</td>
              <td>
                {s.co2_tonnes_low === null || s.co2_tonnes_high === null
                  ? "no published uncertainty"
                  : `${num(s.co2_tonnes_low)} to ${num(s.co2_tonnes_high)} t`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p><strong>Total: {tonnes(result.co2_tonnes_total)}</strong></p>
      {overstated !== null && (
        <p className="callout">
          Booking the whole factor as direct emissions would report {tonnes(result.co2_tonnes_total)} instead
          of {tonnes(direct)}, which is {overstated.toFixed(0)}% too much. The upstream part belongs in Scope 3
          (fuel- and energy-related).
        </p>
      )}
      {result.warnings.map((w) => (
        <p className="warn" key={w}>{w}</p>
      ))}
      <p className="muted">{result.note}</p>
    </div>
  );
}

export default function Calculator({ company }: { company: Company }) {
  const [query, setQuery] = useState("");
  const [factors, setFactors] = useState<Factor[]>([]);
  const [factor, setFactor] = useState<Factor | null>(null);
  const [optionIndex, setOptionIndex] = useState(0);
  const [quantity, setQuantity] = useState("50");
  const [unit, setUnit] = useState("");
  const [year, setYear] = useState(2024);
  const [month, setMonth] = useState(1);
  const [result, setResult] = useState<Breakdown | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function search(q: string): Promise<Factor[]> {
    const r = await api<{ items: Factor[] }>(
      `/emission-factors/?q=${encodeURIComponent(q)}&geography=${encodeURIComponent("France continentale")}&page_size=15`,
    );
    setFactors(r.items);
    return r.items;
  }

  async function calculate(f: Factor, o: Option, qty: string, u: string, y: number, m: number): Promise<void> {
    const amount = Number(qty);
    if (!(amount > 0)) {
      setError("Enter a quantity above zero.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setResult(
        await api<Breakdown>("/emissions/from-activity/preview", {
          method: "POST",
          body: {
            company_id: company.id,
            scope: o.scope,
            category: o.category,
            emission_factor_id: f.id,
            quantity: amount,
            unit: u,
            reporting_year: y,
            reporting_month: m,
          },
        }),
      );
    } catch (e) {
      setResult(null);
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function onSearch(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    if (query.trim().length < 2) {
      setError("Type at least two characters.");
      return;
    }
    setError(null);
    try {
      await search(query.trim());
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function choose(f: Factor): void {
    setFactor(f);
    setUnit(f.unit);
    setResult(null);
  }

  async function usePreset(p: Preset): Promise<void> {
    setError(null);
    try {
      setQuery(p.q);
      const items = await search(p.q);
      const f = items.find((x) => x.source_id === p.sourceId);
      if (!f) {
        setError("That factor is not in the loaded dataset.");
        return;
      }
      setFactor(f);
      setOptionIndex(p.optionIndex);
      setQuantity(String(p.quantity));
      setUnit(p.unit);
      setYear(2024);
      setMonth(1);
      await calculate(f, OPTIONS[p.optionIndex], String(p.quantity), p.unit, 2024, 1);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section>
      <h2>Calculate emissions from activity data</h2>
      <p className="muted">
        Quantity × official emission factor. The factor's parts are booked to the right scope. Nothing is saved.
      </p>

      <div className="card">
        <h3>1. Choose an emission factor</h3>
        <p className="muted">Try an example:</p>
        <div className="row" style={{ justifyContent: "flex-start" }}>
          {PRESETS.map((p) => (
            <button key={p.label} type="button" className="chip" onClick={() => void usePreset(p)}>
              {p.label}
            </button>
          ))}
        </div>
        <form className="form" onSubmit={(e) => void onSearch(e)} style={{ marginTop: 12 }}>
          <label>
            Or search (names are in French, as published by ADEME)
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. Gazole routier" />
          </label>
          <button className="primary" type="submit">Search</button>
        </form>
        <ul className="factors">
          {factors.map((f) => (
            <li key={f.id}>
              <button
                type="button"
                className={factor?.id === f.id ? "factor selected" : "factor"}
                onClick={() => choose(f)}
              >
                {f.name}
                <small>
                  {String(f.kg_co2e_per_unit)} kg CO₂e per {f.unit}
                  {f.sub_geography ? ` · ${f.sub_geography}` : ""} · {f.status ?? "no status"} · {f.source_version}
                </small>
              </button>
            </li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h3>2. Describe the activity</h3>
        <div className="form">
          <label>
            Book it as
            <select value={optionIndex} onChange={(e) => setOptionIndex(Number(e.target.value))}>
              {OPTIONS.map((o, i) => (
                <option key={o.label} value={i}>{o.label}</option>
              ))}
            </select>
          </label>
          <label>
            Quantity
            <input value={quantity} onChange={(e) => setQuantity(e.target.value)} size={10} />
          </label>
          <label>
            Unit
            <input value={unit} onChange={(e) => setUnit(e.target.value)} size={10} />
          </label>
          <label>
            Month
            <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
              {MONTHS.map((m, i) => (
                <option key={m} value={i + 1}>{m}</option>
              ))}
            </select>
          </label>
          <label>
            Year
            <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
              {[2022, 2023, 2024, 2025].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </label>
          <button
            className="primary"
            type="button"
            disabled={busy || !factor}
            onClick={() => factor && void calculate(factor, OPTIONS[optionIndex], quantity, unit, year, month)}
          >
            {busy ? "Calculating…" : "Calculate"}
          </button>
        </div>
        {!factor && <p className="muted">Choose a factor first.</p>}
      </div>

      {error && <p className="error">{error}</p>}
      {result && <ResultView result={result} />}
    </section>
  );
}
