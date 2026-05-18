import { existsSync, writeFileSync, mkdirSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { writeManifest, DEFAULT_MANIFEST } from "../manifest.js";

export type InitResult = "created" | "existed";

const DASH_URL = (process.env.CRAWFISH_DASH_URL ?? "http://127.0.0.1:7880").replace(
  /\/+$/,
  "",
);
const PENDING_FILE = join(homedir(), ".crawfish", "pending-projects.json");

interface PendingEntry {
  localPath: string;
  queuedAt: string;
}

export async function init(repoRoot: string): Promise<InitResult> {
  const dir = join(repoRoot, ".crawfish");
  const wasNew = !existsSync(dir);
  if (wasNew) {
    mkdirSync(dir, { recursive: true });
    writeManifest(repoRoot, DEFAULT_MANIFEST);
    for (const [filename, entry] of Object.entries(DEFAULT_MANIFEST.files)) {
      if (!entry.enabled) continue;
      writeFileSync(
        join(dir, filename),
        `# ${filename.replace(".md", "")}\n\n_Pending first refresh._\n`,
      );
    }
  }
  if (process.env.CRAWFISH_SKIP_DASH_REGISTER !== "1") {
    await registerWithDash(repoRoot);
  }
  return wasNew ? "created" : "existed";
}

async function registerWithDash(localPath: string): Promise<void> {
  const orgId = await pickDashOrg();
  if (!orgId) {
    queuePending(localPath);
    return;
  }
  try {
    const r = await fetch(
      `${DASH_URL}/api/projects/adopt-local?orgId=${encodeURIComponent(orgId)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ localPath }),
      },
    );
    if (r.ok) return;
    // 409 org_not_linked → queue; everything else we also queue rather than
    // surface a hard failure on `craw init`.
    queuePending(localPath);
  } catch {
    queuePending(localPath);
  }
}

async function pickDashOrg(): Promise<string | null> {
  try {
    const r = await fetch(`${DASH_URL}/api/orgs`, {
      signal: AbortSignal.timeout(1500),
    });
    if (!r.ok) return null;
    const body = (await r.json()) as unknown;
    const orgs = Array.isArray(body)
      ? body
      : Array.isArray((body as { orgs?: unknown[] })?.orgs)
        ? (body as { orgs: unknown[] }).orgs
        : [];
    const first = orgs[0] as { id?: string } | undefined;
    return first?.id ?? null;
  } catch {
    return null;
  }
}

function queuePending(localPath: string): void {
  try {
    mkdirSync(join(homedir(), ".crawfish"), { recursive: true });
    let entries: PendingEntry[] = [];
    if (existsSync(PENDING_FILE)) {
      try {
        const parsed = JSON.parse(readFileSync(PENDING_FILE, "utf8")) as unknown;
        if (Array.isArray(parsed)) entries = parsed as PendingEntry[];
      } catch {
        /* corrupt file → overwrite */
      }
    }
    if (entries.some((e) => e.localPath === localPath)) return;
    entries.push({ localPath, queuedAt: new Date().toISOString() });
    writeFileSync(PENDING_FILE, JSON.stringify(entries, null, 2));
  } catch {
    /* best-effort */
  }
}
