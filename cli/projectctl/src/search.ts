/**
 * FTS5-backed task search + structured-query parser.
 *
 * Index lives at `~/.crawfish/<repo-hash>/search.db` where `<repo-hash>` is
 * the first 12 hex chars of `sha1(repoRoot)`. Rebuilds on first use or via
 * `rebuildIndex`. Incremental updates re-index a single task.
 *
 * Uses Node's built-in `node:sqlite` (Node ≥22). If unavailable, falls back
 * to an in-memory token index that supports the same API but no FTS5 ranking.
 * The fallback is logged via the returned `searchTasks` `engine` field so
 * callers can surface "search index unavailable" UX.
 */
import { readdirSync, readFileSync, existsSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";

const nodeRequire = createRequire(import.meta.url);

import { parseFrontmatter, type Criterion, type Frontmatter } from "./frontmatter.js";
import { listCycles, type Cycle } from "./cycles.js";

const SEARCH_KEYS = ["assignee", "label", "priority", "status", "cycle", "epic"] as const;
type SearchKey = (typeof SEARCH_KEYS)[number];

const COMPARABLE_KEYS = new Set<SearchKey>(["priority"]);

const PRIORITY_ORDER: Record<string, number> = { low: 0, med: 1, high: 2, critical: 3 };

export type QueryOp = ":" | ">=" | "<=" | ">" | "<";

export interface QueryConstraintOp {
  key: SearchKey;
  op: QueryOp;
  value: string;
}

export interface ParsedQuery {
  keyVals: Partial<Record<SearchKey, string>>;
  ops: QueryConstraintOp[];
  freeText: string;
}

/** Pure parser. Recognized keys: assignee, label, priority, status, cycle, epic. */
export function parseQuery(input: string): ParsedQuery {
  const keyVals: Partial<Record<SearchKey, string>> = {};
  const ops: QueryConstraintOp[] = [];
  const freeTextParts: string[] = [];
  // Match each token as either key<op>value or a free-text token.
  const tokenRe = /\S+/g;
  let m: RegExpExecArray | null;
  const keyOpRe = /^([a-z]+)(>=|<=|>|<|:)(.+)$/i;
  while ((m = tokenRe.exec(input)) !== null) {
    const tok = m[0];
    const km = tok.match(keyOpRe);
    if (km) {
      const rawKey = km[1].toLowerCase();
      const op = km[2] as QueryOp;
      const value = km[3];
      if ((SEARCH_KEYS as readonly string[]).includes(rawKey)) {
        const key = rawKey as SearchKey;
        if (op !== ":" && !COMPARABLE_KEYS.has(key)) {
          throw new Error(`invalid_operator: ${key}${op}${value}`);
        }
        if (op === ":") keyVals[key] = value;
        else ops.push({ key, op, value });
        continue;
      }
    }
    freeTextParts.push(tok);
  }
  return { keyVals, ops, freeText: freeTextParts.join(" ").trim() };
}

export interface TaskHit {
  slug: string;
  title: string;
  status?: string;
  assignee?: string;
  labels: string[];
  priority?: string;
  cycle?: string;
  epic?: string;
  rank?: number;
  updated_at?: string;
}

export interface SearchResult {
  results: TaskHit[];
  count: number;
  warnings: string[];
  engine: "fts5" | "memory";
}

interface IndexedTask {
  slug: string;
  title: string;
  description: string;
  criteria_statements: string;
  labels: string[];
  priority: string;
  status: string;
  cycle_id: string;
  epic_id: string;
  assignee: string;
  updated_at: string;
}

function repoHash(repoRoot: string): string {
  return createHash("sha1").update(repoRoot).digest("hex").slice(0, 12);
}

function dbPath(repoRoot: string): string {
  return join(homedir(), ".crawfish", repoHash(repoRoot), "search.db");
}

function tasksDirOf(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "tasks");
}

function frontmatterToIndexed(slug: string, fm: Frontmatter, body: string, mtimeIso: string): IndexedTask {
  const labelsRaw = fm.labels;
  const labels = Array.isArray(labelsRaw) ? (labelsRaw as string[]).filter((l) => typeof l === "string") : [];
  const criteria = Array.isArray(fm.criteria) ? (fm.criteria as Criterion[]) : [];
  const criteriaStatements = criteria.map((c) => c.statement ?? "").join(" \n ");
  return {
    slug,
    title: typeof fm.title === "string" ? fm.title : slug,
    description: body,
    criteria_statements: criteriaStatements,
    labels,
    priority: typeof fm.priority === "string" ? (fm.priority as string) : "",
    status: typeof fm.status === "string" ? (fm.status as string) : "",
    cycle_id: typeof fm.cycle === "string" ? (fm.cycle as string) : "",
    epic_id: typeof fm.epic === "string" ? (fm.epic as string) : "",
    assignee: typeof fm.assignee === "string" ? (fm.assignee as string) : "",
    updated_at: mtimeIso,
  };
}

function scanAllTasks(repoRoot: string): IndexedTask[] {
  const dir = tasksDirOf(repoRoot);
  if (!existsSync(dir)) return [];
  const out: IndexedTask[] = [];
  for (const name of readdirSync(dir)) {
    if (!name.endsWith(".md")) continue;
    const slug = name.slice(0, -3);
    try {
      const raw = readFileSync(join(dir, name), "utf8");
      const { fm, body } = parseFrontmatter(raw);
      out.push(frontmatterToIndexed(slug, fm, body, new Date().toISOString()));
    } catch {
      /* skip corrupted file */
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// SQLite FTS5 path
// ---------------------------------------------------------------------------

interface SqliteDB {
  exec(sql: string): void;
  prepare(sql: string): SqliteStmt;
  close(): void;
}

interface SqliteStmt {
  run(...params: unknown[]): { changes?: number; lastInsertRowid?: number | bigint };
  all(...params: unknown[]): Record<string, unknown>[];
  get(...params: unknown[]): Record<string, unknown> | undefined;
}

let cachedSqliteCtor: (new (path: string) => SqliteDB) | null | undefined;

function loadSqliteCtor(): (new (path: string) => SqliteDB) | null {
  if (cachedSqliteCtor !== undefined) return cachedSqliteCtor;
  try {
    const mod = nodeRequire("node:sqlite") as { DatabaseSync: new (path: string) => SqliteDB };
    cachedSqliteCtor = mod.DatabaseSync;
  } catch {
    cachedSqliteCtor = null;
  }
  return cachedSqliteCtor;
}

function openDb(repoRoot: string): SqliteDB | null {
  const Ctor = loadSqliteCtor();
  if (!Ctor) return null;
  const path = dbPath(repoRoot);
  mkdirSync(join(homedir(), ".crawfish", repoHash(repoRoot)), { recursive: true });
  const db = new Ctor(path);
  db.exec(`
    CREATE VIRTUAL TABLE IF NOT EXISTS tasks_fts USING fts5(
      task_id UNINDEXED,
      title,
      description,
      criteria_statements,
      labels,
      priority,
      status,
      cycle_id,
      epic_id,
      assignee,
      updated_at UNINDEXED,
      tokenize = 'porter unicode61'
    );
  `);
  return db;
}

function insertRow(db: SqliteDB, t: IndexedTask): void {
  db.prepare(
    `INSERT INTO tasks_fts(task_id, title, description, criteria_statements, labels, priority, status, cycle_id, epic_id, assignee, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  ).run(
    t.slug,
    t.title,
    t.description,
    t.criteria_statements,
    t.labels.join(" "),
    t.priority,
    t.status,
    t.cycle_id,
    t.epic_id,
    t.assignee,
    t.updated_at,
  );
}

function deleteRow(db: SqliteDB, slug: string): void {
  db.prepare(`DELETE FROM tasks_fts WHERE task_id = ?`).run(slug);
}

export function rebuildIndex(repoRoot: string): { engine: "fts5" | "memory"; indexed: number } {
  const db = openDb(repoRoot);
  if (!db) {
    return { engine: "memory", indexed: scanAllTasks(repoRoot).length };
  }
  try {
    db.exec("DELETE FROM tasks_fts;");
    const tasks = scanAllTasks(repoRoot);
    for (const t of tasks) insertRow(db, t);
    return { engine: "fts5", indexed: tasks.length };
  } finally {
    db.close();
  }
}

export function incrementalUpdate(repoRoot: string, slug: string): void {
  const db = openDb(repoRoot);
  if (!db) return;
  try {
    deleteRow(db, slug);
    const path = join(tasksDirOf(repoRoot), `${slug}.md`);
    if (!existsSync(path)) return;
    try {
      const raw = readFileSync(path, "utf8");
      const { fm, body } = parseFrontmatter(raw);
      const t = frontmatterToIndexed(slug, fm, body, new Date().toISOString());
      insertRow(db, t);
    } catch {
      /* corrupted file — leave deleted */
    }
  } finally {
    db.close();
  }
}

// ---------------------------------------------------------------------------
// Query execution
// ---------------------------------------------------------------------------

function resolveCurrentCycle(repoRoot: string, today: Date): Cycle | null {
  const all = listCycles(repoRoot);
  const todayIso = today.toISOString().slice(0, 10);
  for (const c of all) {
    if (c.start <= todayIso && todayIso <= c.end) return c;
  }
  return null;
}

function passesStructuredFilters(
  t: IndexedTask,
  parsed: ParsedQuery,
  resolvedCycle: string | null,
): boolean {
  for (const [k, v] of Object.entries(parsed.keyVals) as [SearchKey, string][]) {
    if (k === "assignee" && t.assignee !== v) return false;
    if (k === "label" && !t.labels.includes(v)) return false;
    if (k === "priority" && t.priority !== v) return false;
    if (k === "status" && t.status !== v) return false;
    if (k === "epic" && t.epic_id !== v) return false;
    if (k === "cycle") {
      if (v === "current") {
        if (resolvedCycle === null) continue;
        if (t.cycle_id !== resolvedCycle) return false;
      } else if (t.cycle_id !== v) {
        return false;
      }
    }
  }
  for (const op of parsed.ops) {
    if (op.key === "priority") {
      const taskRank = PRIORITY_ORDER[t.priority] ?? -1;
      const valRank = PRIORITY_ORDER[op.value] ?? -1;
      if (valRank < 0) return false;
      if (op.op === ">=" && !(taskRank >= valRank)) return false;
      if (op.op === "<=" && !(taskRank <= valRank)) return false;
      if (op.op === ">" && !(taskRank > valRank)) return false;
      if (op.op === "<" && !(taskRank < valRank)) return false;
    }
  }
  return true;
}

function toHit(t: IndexedTask, rank?: number): TaskHit {
  return {
    slug: t.slug,
    title: t.title,
    status: t.status || undefined,
    assignee: t.assignee || undefined,
    labels: t.labels,
    priority: t.priority || undefined,
    cycle: t.cycle_id || undefined,
    epic: t.epic_id || undefined,
    updated_at: t.updated_at,
    rank,
  };
}

function ftsMatchExpr(freeText: string): string {
  // Sanitize: collapse whitespace, drop FTS5-meta chars, quote each token.
  const tokens = freeText
    .replace(/["()*]/g, " ")
    .split(/\s+/)
    .filter((t) => t.length > 0)
    .map((t) => `"${t}"`);
  return tokens.join(" ");
}

const MAX_RESULTS = 50;

export function searchTasks(repoRoot: string, query: string): SearchResult {
  const parsed = parseQuery(query);
  const warnings: string[] = [];
  let resolvedCycle: string | null = null;
  if (parsed.keyVals.cycle === "current") {
    const c = resolveCurrentCycle(repoRoot, new Date());
    if (!c) {
      warnings.push("cycle:current → no_active_cycle");
      // Drop the constraint by leaving resolvedCycle null; filter skips it.
    } else {
      resolvedCycle = c.id;
    }
  }

  // Ensure the index exists if we're using FTS5.
  const ftsCtor = loadSqliteCtor();
  if (ftsCtor && !existsSync(dbPath(repoRoot))) {
    rebuildIndex(repoRoot);
  }

  const db = openDb(repoRoot);
  if (!db) {
    // Fallback: scan + filter in memory.
    const all = scanAllTasks(repoRoot);
    const free = parsed.freeText.toLowerCase();
    let filtered = all.filter((t) => passesStructuredFilters(t, parsed, resolvedCycle));
    if (free) {
      filtered = filtered.filter((t) => {
        const hay = [t.title, t.description, t.criteria_statements, t.labels.join(" "), t.assignee]
          .join(" ")
          .toLowerCase();
        return hay.includes(free);
      });
    }
    filtered.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return {
      results: filtered.slice(0, MAX_RESULTS).map((t) => toHit(t)),
      count: filtered.length,
      warnings,
      engine: "memory",
    };
  }
  try {
    let rows: Record<string, unknown>[];
    if (parsed.freeText) {
      const expr = ftsMatchExpr(parsed.freeText);
      if (!expr) {
        rows = db.prepare(`SELECT * FROM tasks_fts ORDER BY updated_at DESC LIMIT 200`).all();
      } else {
        rows = db
          .prepare(
            `SELECT *, rank AS _rank FROM tasks_fts WHERE tasks_fts MATCH ? ORDER BY rank LIMIT 200`,
          )
          .all(expr);
      }
    } else {
      rows = db.prepare(`SELECT * FROM tasks_fts ORDER BY updated_at DESC LIMIT 200`).all();
    }
    const out: TaskHit[] = [];
    for (const row of rows) {
      const t: IndexedTask = {
        slug: String(row.task_id ?? ""),
        title: String(row.title ?? ""),
        description: String(row.description ?? ""),
        criteria_statements: String(row.criteria_statements ?? ""),
        labels: String(row.labels ?? "").split(" ").filter((s) => s.length > 0),
        priority: String(row.priority ?? ""),
        status: String(row.status ?? ""),
        cycle_id: String(row.cycle_id ?? ""),
        epic_id: String(row.epic_id ?? ""),
        assignee: String(row.assignee ?? ""),
        updated_at: String(row.updated_at ?? ""),
      };
      if (!passesStructuredFilters(t, parsed, resolvedCycle)) continue;
      const rank = typeof row._rank === "number" ? row._rank : undefined;
      out.push(toHit(t, rank));
      if (out.length >= MAX_RESULTS) break;
    }
    return { results: out, count: out.length, warnings, engine: "fts5" };
  } finally {
    db.close();
  }
}
