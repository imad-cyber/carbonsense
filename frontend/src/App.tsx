import { useEffect, useState } from "react";
import { api, type Company } from "./api";
import Calculator from "./pages/Calculator";
import Findings from "./pages/Findings";
import Forecast from "./pages/Forecast";
import Overview from "./pages/Overview";
import Validation from "./pages/Validation";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "calculator", label: "Calculator" },
  { id: "findings", label: "Findings" },
  { id: "forecast", label: "Forecast" },
  { id: "validation", label: "Validation" },
] as const;
type TabId = (typeof TABS)[number]["id"];

export default function App() {
  const [tab, setTab] = useState<TabId>("overview");
  const [company, setCompany] = useState<Company | null>(null);
  const [error, setError] = useState<string | null>(null);
  const repo = import.meta.env.VITE_REPO_URL as string | undefined;

  useEffect(() => {
    api<{ items: Company[] }>("/companies/?page_size=100")
      .then((r) => setCompany(r.items.find((c) => c.name.startsWith("Démo")) ?? r.items[0] ?? null))
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="app">
      <header>
        <div>
          <h1>CarbonSense</h1>
          <p className="tagline">
            Activity data × official ADEME emission factors, allocated to scopes and monitored for anomalies
          </p>
        </div>
        <span className="badge">Read-only demo</span>
      </header>
      <div className="notice">
        Synthetic activity data for a fictional company, calculated with <strong>real</strong> ADEME Base
        Carbone V23.6 factors. A portfolio project, not a compliance tool.
      </div>
      <nav>
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      <main>
        {error && <p className="error">{error}</p>}
        {!error && !company && <p className="muted">Connecting to the API…</p>}
        {company && tab === "overview" && <Overview company={company} />}
        {company && tab === "calculator" && <Calculator company={company} />}
        {company && tab === "findings" && <Findings company={company} />}
        {company && tab === "forecast" && <Forecast company={company} />}
        {tab === "validation" && <Validation />}
      </main>
      <footer>
        Emission factors: ADEME Base Carbone, Licence Ouverte 2.0.{" "}
        {repo && <a href={repo}>Source code, method and model card</a>}
      </footer>
    </div>
  );
}
