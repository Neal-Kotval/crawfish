import { existsSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { writeManifest, DEFAULT_MANIFEST } from "../manifest.js";

export type InitResult = "created" | "existed";

export function init(repoRoot: string): InitResult {
  const dir = join(repoRoot, ".crawfish");
  if (existsSync(dir)) return "existed";
  mkdirSync(dir, { recursive: true });
  writeManifest(repoRoot, DEFAULT_MANIFEST);
  for (const [filename, entry] of Object.entries(DEFAULT_MANIFEST.files)) {
    if (!entry.enabled) continue;
    writeFileSync(
      join(dir, filename),
      `# ${filename.replace(".md", "")}\n\n_Pending first refresh._\n`,
    );
  }
  return "created";
}
