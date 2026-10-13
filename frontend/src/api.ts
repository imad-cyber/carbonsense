const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
const DEMO_EMAIL = (import.meta.env.VITE_DEMO_EMAIL as string | undefined) || "demo@carbonsense.fr";
const DEMO_PASSWORD = (import.meta.env.VITE_DEMO_PASSWORD as string | undefined) || "Demo-Auditor-2026";
const TOKEN_KEY = "carbonsense-demo-token";

export type Scope = "scope_1" | "scope_2" | "scope_3";

export interface Company { id: number; name: string }
export interface Summary {
  scope_1_total: number; scope_2_total: number; scope_3_total: number;
  grand_total: number; record_count: number;
}
export interface EmissionRow {
  scope: Scope; category: string; co2_tonnes: number;
  reporting_year: number; reporting_month: number | null;
}
export interface Factor {
  id: number; source_id: string; source_version: string; name: string; unit: string;
  kg_co2e_per_unit: number; uncertainty_pct: number | null; geography: string | null;
  sub_geography: string | null; status: string | null; valid_until: string | null;
}
export interface Slice {
  scope: Scope; category: string; post_type: string; kg_co2e_per_unit: number;
  co2_tonnes: number; co2_tonnes_low: number | null; co2_tonnes_high: number | null;
}
export interface Breakdown {
  formula: string; co2_tonnes_total: number; slices: Slice[]; note: string; warnings: string[];
}
export interface FindingRecord {
  record_id: number; scope: Scope; category: string; co2_tonnes: number; is_anomaly: boolean;
}
export interface Finding {
  activity_group_id: string | null; reporting_year: number; reporting_month: number;
  severity: "high" | "medium" | "low"; times_same_month: number | null;
  times_series_median: number; total_co2_tonnes: number; records: FindingRecord[];
}
export interface AnomalyResponse { total_records: number; anomaly_count: number; findings: Finding[] }
export interface ForecastResult {
  model_used: string; models_disagree: boolean; predicted_co2_tonnes: number;
  baseline: { same_month_last_year: number; trend_factor: number; forecast: number };
  challenger: { forecast: number };
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function errorMessage(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) {
      return body.detail.map((d) => (d as { msg?: string }).msg ?? "invalid input").join("; ");
    }
  } catch {
    /* response was not JSON */
  }
  return `Request failed (${res.status})`;
}

async function login(): Promise<string> {
  const res = await fetch(`${BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD }),
  });
  if (!res.ok) {
    throw new ApiError(
      res.status,
      res.status === 429 ? "Too many sign-in attempts. Wait a minute and reload." : "Demo sign-in failed.",
    );
  }
  const data = (await res.json()) as { access_token: string };
  sessionStorage.setItem(TOKEN_KEY, data.access_token);
  return data.access_token;
}

let pending: Promise<string> | null = null;

async function token(): Promise<string> {
  const saved = sessionStorage.getItem(TOKEN_KEY);
  if (saved) return saved;
  pending ??= login().finally(() => {
    pending = null;
  });
  return pending;
}

export async function api<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const res = await fetch(`${BASE}/api/v1${path}`, {
      method: init?.method ?? "GET",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${await token()}` },
      body: init?.body === undefined ? undefined : JSON.stringify(init.body),
    });
    if (res.status === 401 && attempt === 0) {
      sessionStorage.removeItem(TOKEN_KEY);
      continue;
    }
    if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
    return (await res.json()) as T;
  }
  throw new ApiError(401, "Not signed in.");
}
