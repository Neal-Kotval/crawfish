/**
 * Capability-based router. Picks an assignee for each unassigned task using
 * the rolling stats produced by `agent-stats.ts`.
 *
 * Algorithm (per ROADMAP NOW-W3 § 3.2):
 *   1. Look up the task's primary label in each candidate's stats.
 *   2. Filter to agents with `success_rate > 0.7`.
 *   3. Pick the lowest `avg_tokens_per_task`. Ties broken by lowest current
 *      in-progress load, then by sorted agent id.
 *   4. If no candidate qualifies, return null — leave the task for a human.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { parseFrontmatter } from "./frontmatter.js";
import { updateTask } from "./tasks.js";
import {
  getAllAgentStats,
  listKnownAgents,
  type AgentStats,
} from "./agent-stats.js";

export interface RoutableTask {
  id: string;
  labels: string[];
  status: string;
  assignee?: string | null;
}

export interface PickContext {
  /** Map agent id → number of in-progress (todo|doing) tasks already on them. */
  load?: Map<string, number>;
}

const SUCCESS_THRESHOLD = 0.7;

export function pickAssignee(
  task: RoutableTask,
  stats: Map<string, AgentStats>,
  agents: string[],
  ctx: PickContext = {},
): string | null {
  if (!task.labels || task.labels.length === 0) return null;
  const label = task.labels[0];

  interface Candidate {
    agent: string;
    avg: number;
    load: number;
  }
  const qualified: Candidate[] = [];

  for (const agent of agents) {
    const s = stats.get(agent);
    if (!s) continue;
    const ls = s.byLabel[label];
    if (!ls) continue;
    if (ls.success_rate <= SUCCESS_THRESHOLD) continue;
    qualified.push({
      agent,
      avg: ls.avg_tokens_per_task,
      load: ctx.load?.get(agent) ?? 0,
    });
  }

  if (qualified.length === 0) return null;

  qualified.sort((a, b) => {
    if (a.avg !== b.avg) return a.avg - b.avg;
    if (a.load !== b.load) return a.load - b.load;
    return a.agent.localeCompare(b.agent);
  });
  return qualified[0].agent;
}

interface Skipped {
  taskId: string;
  reason: "no_label" | "no_qualified_candidate" | "already_assigned";
}

export interface RouterPassResult {
  scanned: number;
  assigned: number;
  skipped: Skipped[];
}

interface RouterPassOptions {
  /** Override candidate pool. Defaults to all agents seen in the event log. */
  agents?: string[];
  /** Inject "now" for tests. */
  now?: number;
  /** When true, do not write — return what would happen. */
  dryRun?: boolean;
}

function tasksDir(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "tasks");
}

interface LoadedTask {
  slug: string;
  labels: string[];
  status: string;
  assignee?: string;
}

function loadAllTasks(repoRoot: string): LoadedTask[] {
  const dir = tasksDir(repoRoot);
  if (!existsSync(dir)) return [];
  const out: LoadedTask[] = [];
  for (const name of readdirSync(dir)) {
    if (!name.endsWith(".md")) continue;
    try {
      const { fm } = parseFrontmatter(readFileSync(join(dir, name), "utf8"));
      const slug = typeof fm.id === "string" ? fm.id : name.replace(/\.md$/, "");
      const status = typeof fm.status === "string" ? fm.status : "todo";
      const labels = Array.isArray(fm.labels)
        ? (fm.labels as string[]).filter((s) => typeof s === "string")
        : [];
      const assignee = typeof fm.assignee === "string" ? fm.assignee : undefined;
      out.push({ slug, labels, status, assignee });
    } catch {
      /* skip */
    }
  }
  return out;
}

function buildLoadMap(tasks: LoadedTask[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const t of tasks) {
    if (!t.assignee) continue;
    if (t.status !== "todo" && t.status !== "doing") continue;
    m.set(t.assignee, (m.get(t.assignee) ?? 0) + 1);
  }
  return m;
}

/**
 * Walk unassigned tasks (`status in {todo, triage}` and no `assignee`) and
 * try to pick an assignee for each. On success, writes via `updateTask`
 * with `assignedBy: "router"` so the resulting `task_assigned` event is
 * attributable.
 */
export function runRouterPass(
  repoRoot: string,
  opts: RouterPassOptions = {},
): RouterPassResult {
  const tasks = loadAllTasks(repoRoot);
  const agents = opts.agents ?? listKnownAgents(repoRoot);
  const stats = getAllAgentStats(repoRoot, { now: opts.now });
  const load = buildLoadMap(tasks);

  const result: RouterPassResult = { scanned: 0, assigned: 0, skipped: [] };

  for (const t of tasks) {
    if (t.status !== "todo" && t.status !== "triage") continue;
    result.scanned += 1;
    if (t.assignee) {
      result.skipped.push({ taskId: t.slug, reason: "already_assigned" });
      continue;
    }
    if (t.labels.length === 0) {
      result.skipped.push({ taskId: t.slug, reason: "no_label" });
      continue;
    }
    const pick = pickAssignee(
      { id: t.slug, labels: t.labels, status: t.status, assignee: t.assignee ?? null },
      stats,
      agents,
      { load },
    );
    if (!pick) {
      result.skipped.push({ taskId: t.slug, reason: "no_qualified_candidate" });
      continue;
    }
    if (!opts.dryRun) {
      updateTask(repoRoot, t.slug, { assignee: pick, assignedBy: "router" });
    }
    load.set(pick, (load.get(pick) ?? 0) + 1);
    result.assigned += 1;
  }

  return result;
}
