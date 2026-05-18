import { glob } from "glob";
import { readFileSync } from "node:fs";
import { relative } from "node:path";

function firstHeading(text: string): string {
  for (const line of text.split("\n")) {
    if (line.startsWith("# ")) return line.slice(2).trim();
  }
  return "(no heading)";
}

export async function renderRoadmap(repoRoot: string, sources: string[]): Promise<string> {
  const matched = new Set<string>();
  for (const pattern of sources) {
    const files = await glob(pattern, { cwd: repoRoot, nodir: true, absolute: true });
    for (const f of files) matched.add(f);
  }
  if (matched.size === 0) {
    return "# Roadmap\n\n_No roadmap sources found. Configure them in `.crawfish/index.json`._\n";
  }
  const sorted = [...matched].sort();
  const lines = ["# Roadmap", ""];
  for (const abs of sorted) {
    const rel = relative(repoRoot, abs);
    const content = readFileSync(abs, "utf8");
    const heading = firstHeading(content);
    lines.push(`## ${heading}`);
    lines.push(`Source: \`${rel}\``);
    lines.push("");
    if (sorted.length === 1) {
      // Single-source: include full file body so consumers see the actual content
      const body = content.replace(/^#[^\n]*\n/, "").trimStart();
      if (body) {
        lines.push(body.trimEnd());
        lines.push("");
      }
    }
  }
  return lines.join("\n");
}
