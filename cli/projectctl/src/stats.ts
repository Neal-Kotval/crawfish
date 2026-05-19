/**
 * Project-wide rollup stats for the dev and product surfaces.
 *
 * Source of truth: `.crawfish/board.jsonl` plus current task frontmatter.
 * Window: 30 days back from `now` (injectable for tests). Events outside the
 * window are ignored for all rate calculations.
 *
 * Two views:
 *   - `dev`: tokens_by_agent (sum of estimate per current assignee, in
 *     window), tokens_by_tool (sum from any board event whose payload
 *     carries a `tool` field), and a global success_rate
 *     (done / (done + escalated)) inside the window.
 *   - `product`: completion_rate (tasks closed / tasks opened in window),
 *     escalation_rate (tasks that hit `escalated` / total created in window),
 *     and a current snapshot of tasks_by_status.
 *
 * "Closed" means a status transition to either `done` or `escalated`.
 * `escalated` is a forward-compatible terminal status: the live `TaskStatus`
 * union doesn't include it today, but the board event stream is a string-
 * typed payload so we recognise it when it arrives without a schema change.
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { readEvents, type ProjectBoardEvent } from "./project-board.js";
import { parseFrontmatter } from "./frontmatter.js";
import { TASK_STATUSES, type TaskStatus } from "./tasks.js";

const WINDOW_MS = 30 * 24 * 60 * 60 * 1000;

/** Terminal statuses that count as "closed" for completion math. */
const CLOSED_STATUSES: ReadonlySet<string> = new Set(["done", "escalated"]);

export interface DevStats {
  /** Sum of task.estimate per current assignee, last 30 days. */
  tokens_by_agent: Record<string, number>;
  /** Sum from board events that carry a `tool` field in payload, last 30 days. */
  tokens_by_tool: Record<string, number>;
  /** done / (done + escalated) over status transitions in window. 0..1. */
  success_rate: number;
}

export interface ProductStats {
  /** Tasks closed in window / tasks opened in window. 0..1. */
  completion_rate: number;
  /** Tasks that hit `escalated` / tasks created in window. 0..1. */
  escalation_rate: number;
  /** Snapshot count of tasks per status across the current task tree. */
  tasks_by_status: Record<TaskStatus, number>;
}

export type StatsView = "dev" | "product";
export type Stats = DevStats | ProductStats;

interface TaskMeta {
  estimate: number;
  status: TaskStatus | string;
}

function tasksDir(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "tasks");
}

function readTaskMeta(repoRoot: string): Map<string, TaskMeta> {
  const out = new Map<string, TaskMeta>();
  const dir = tasksDir(repoRoot);
  if (!existsSync(dir)) return out;
  for (const name of readdirSync(dir)) {
    if (!name.endsWith(".md")) continue;
    try {
      const { fm } = parseFrontmatter(readFileSync(join(dir, name), "utf8"));
      const slug = typeof fm.id === "string" ? fm.id : name.replace(/\.md$/, "");
      const estimate = typeof fm.estimate === "number" ? fm.estimate : 0;
      const status = typeof fm.status === "string" ? fm.status : "todo";
      out.set(slug, { estimate, status });
    } catch {
      /* skip unreadable */
    }
  }
  return out;
}

function eventInWindow(ev: ProjectBoardEvent, cutoff: number): boolean {
  const ts = Date.parse(ev.ts);
  return Number.isFinite(ts) && ts >= cutoff;
}

/**
 * Walk the event log forward, tracking the current assignee per task, and
 * return the assignee at the moment each task's last in-window assignment
 * landed. Tasks never assigned in-window are absent from the map.
 */
function currentAssignees(
  events: ProjectBoardEvent[],
  cutoff: number,
): Map<string, string> {
  const out = new Map<string, string>();
  for (const ev of events) {
    if (ev.type !== "task_assigned") continue;
    if (!ev.task_id) continue;
    if (!eventInWindow(ev, cutoff)) continue;
    const p = (ev.payload ?? {}) as { to?: string | null };
    if (typeof p.to === "string" && p.to.length > 0) {
      out.set(ev.task_id, p.to);
    } else {
      out.delete(ev.task_id);
    }
  }
  return out;
}

function computeDevStats(
  events: ProjectBoardEvent[],
  meta: Map<string, TaskMeta>,
  now: number,
): DevStats {
  const cutoff = now - WINDOW_MS;

  const tokens_by_agent: Record<string, number> = {};
  const assignees = currentAssignees(events, cutoff);
  for (const [taskId, agent] of assignees) {
    const m = meta.get(taskId);
    if (!m) continue;
    tokens_by_agent[agent] = (tokens_by_agent[agent] ?? 0) + m.estimate;
  }

  const tokens_by_tool: Record<string, number> = {};
  let done = 0;
  let escalated = 0;

  for (const ev of events) {
    if (!eventInWindow(ev, cutoff)) continue;
    const payload = (ev.payload ?? {}) as Record<string, unknown>;

    const tool = payload.tool;
    if (typeof tool === "string" && tool.length > 0) {
      const tokens =
        typeof payload.tokens === "number"
          ? payload.tokens
          : typeof payload.estimate === "number"
            ? payload.estimate
            : 0;
      tokens_by_tool[tool] = (tokens_by_tool[tool] ?? 0) + tokens;
    }

    if (ev.type === "task_status_changed") {
      const to = payload.to;
      if (to === "done") done += 1;
      else if (to === "escalated") escalated += 1;
    }
  }

  const denom = done + escalated;
  const success_rate = denom === 0 ? 0 : done / denom;

  return { tokens_by_agent, tokens_by_tool, success_rate };
}

function computeProductStats(
  events: ProjectBoardEvent[],
  meta: Map<string, TaskMeta>,
  now: number,
): ProductStats {
  const cutoff = now - WINDOW_MS;

  let opened = 0;
  let closed = 0;
  const escalatedTasks = new Set<string>();

  for (const ev of events) {
    if (!eventInWindow(ev, cutoff)) continue;
    if (ev.type === "task_created") {
      opened += 1;
      continue;
    }
    if (ev.type === "task_status_changed") {
      const payload = (ev.payload ?? {}) as { to?: string };
      const to = payload.to;
      if (typeof to !== "string") continue;
      if (CLOSED_STATUSES.has(to)) closed += 1;
      if (to === "escalated" && ev.task_id) escalatedTasks.add(ev.task_id);
    }
  }

  const completion_rate = opened === 0 ? 0 : closed / opened;
  const escalation_rate = opened === 0 ? 0 : escalatedTasks.size / opened;

  const tasks_by_status: Record<TaskStatus, number> = {
    todo: 0,
    doing: 0,
    done: 0,
    blocked: 0,
  };
  for (const m of meta.values()) {
    if ((TASK_STATUSES as readonly string[]).includes(m.status)) {
      tasks_by_status[m.status as TaskStatus] += 1;
    }
  }

  return { completion_rate, escalation_rate, tasks_by_status };
}

/**
 * Compute project-wide stats for one view. Pure: deterministic given
 * `repoRoot`, `view`, and the injectable clock.
 */
export function getStats(
  repoRoot: string,
  view: "dev",
  opts?: { now?: number },
): DevStats;
export function getStats(
  repoRoot: string,
  view: "product",
  opts?: { now?: number },
): ProductStats;
export function getStats(
  repoRoot: string,
  view: StatsView,
  opts: { now?: number } = {},
): Stats {
  const now = opts.now ?? Date.now();
  const events = readEvents(repoRoot);
  const meta = readTaskMeta(repoRoot);
  if (view === "dev") return computeDevStats(events, meta, now);
  return computeProductStats(events, meta, now);
}
