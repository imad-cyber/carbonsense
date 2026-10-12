import type { Scope } from "./api";

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const nf = new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 });
export const num = (v: number): string => nf.format(v);
export const tonnes = (v: number): string => `${nf.format(v)} t CO₂e`;

export const SCOPE_NAME: Record<Scope, string> = { scope_1: "Scope 1", scope_2: "Scope 2", scope_3: "Scope 3" };
export const SCOPE_COLOR: Record<Scope, string> = { scope_1: "#c8553d", scope_2: "#e6a23c", scope_3: "#2a7f8f" };

const CATEGORY_NAME: Record<string, string> = {
  stationary_combustion: "Stationary combustion",
  mobile_combustion: "Mobile combustion",
  purchased_electricity: "Purchased electricity",
  purchased_heat: "Purchased heat",
  fuel_energy_related: "Fuel- and energy-related (upstream)",
  supply_chain: "Supply chain",
  business_travel: "Business travel",
  employee_commuting: "Employee commuting",
  waste: "Waste",
};
export const categoryName = (c: string): string => CATEGORY_NAME[c] ?? c;
