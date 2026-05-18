import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

export function decisionAdd(repoRoot: string, title: string, body: string): void {
  const path = join(repoRoot, ".crawfish", "decisions.md");
  const existing = existsSync(path) ? readFileSync(path, "utf8") : "# Decisions\n\n";
  const date = new Date().toISOString().slice(0, 10);
  const entry = `\n## ${title}\n\n_${date}_\n\n${body}\n`;
  writeFileSync(path, existing + entry);
}
