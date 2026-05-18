import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { SCHEMA_VERSION } from "../manifest.js";

export function doctor(repoRoot: string): { errors: string[]; warnings: string[] } {
  const errors: string[] = [];
  const warnings: string[] = [];
  const idxPath = join(repoRoot, ".crawfish", "index.json");
  if (!existsSync(idxPath)) {
    errors.push(".crawfish/index.json is missing — run `crawfish-projectctl init` first");
    return { errors, warnings };
  }
  try {
    const raw = JSON.parse(readFileSync(idxPath, "utf8"));
    if (raw.schema !== SCHEMA_VERSION) {
      errors.push(`unknown schema "${raw.schema}", expected "${SCHEMA_VERSION}"`);
    }
  } catch (e) {
    errors.push(`index.json is not valid JSON: ${(e as Error).message}`);
  }
  return { errors, warnings };
}
