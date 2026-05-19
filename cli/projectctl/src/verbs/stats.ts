import { getStats, type DevStats, type ProductStats, type StatsView } from "../stats.js";

export function stats(repoRoot: string, view: "dev"): DevStats;
export function stats(repoRoot: string, view: "product"): ProductStats;
export function stats(repoRoot: string, view: StatsView): DevStats | ProductStats {
  if (view === "dev") return getStats(repoRoot, "dev");
  return getStats(repoRoot, "product");
}
