import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

export function activityRecord(repoRoot: string, summary: string, keep = 50): void {
  const path = join(repoRoot, ".crawfish", "activity.md");
  const existing = existsSync(path) ? readFileSync(path, "utf8") : "# Activity\n\n";
  const ts = new Date().toISOString();
  const newEntry = `\n### ${ts}\n\n${summary}\n`;
  const combined = existing + newEntry;
  // Trim oldest entries beyond `keep`
  const parts = combined.split(/(?=^### )/m);
  const header = parts.shift() ?? "# Activity\n\n";
  const trimmed = parts.slice(-keep);
  writeFileSync(path, header + trimmed.join(""));
}
