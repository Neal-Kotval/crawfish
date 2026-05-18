import { glob } from "glob";
import { statSync } from "node:fs";
import { basename } from "node:path";

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
  return `${(n / 1024 / 1024).toFixed(1)} MiB`;
}

export async function renderContext(_repoRoot: string, sources: string[]): Promise<string> {
  const matched = new Set<string>();
  for (const pattern of sources) {
    const files = await glob(pattern, { nodir: true, absolute: true });
    for (const f of files) matched.add(f);
  }
  if (matched.size === 0) {
    return "# Context\n\n_No sessions found yet._\n";
  }
  const stats = [...matched].map((abs) => ({ abs, size: statSync(abs).size }));
  const total = stats.reduce((a, s) => a + s.size, 0);
  const top = stats.sort((a, b) => b.size - a.size).slice(0, 10);
  const lines = [
    "# Context",
    "",
    `**${stats.length} sessions** · **${fmtBytes(total)}** total`,
    "",
    "## Largest sessions",
    "",
    ...top.map((s) => `- \`${basename(s.abs)}\` — ${fmtBytes(s.size)}`),
    "",
  ];
  return lines.join("\n");
}
