/**
 * Rolling 30-day capability stats per (agent, label) pair.
 *
 * Source of truth: `.crawfish/board.jsonl` (event log) plus the current task
 * frontmatter for label and estimate. We reconstruct, per task, the final
 * assignee at the moment its status transitioned to `done`, then attribute
 * the task's labels and estimate to that agent.
 *
 * Window: 30 days back from `now` (or an injected clock for tests). Events
 * older than that are ignored. Tasks whose `done` transition falls inside
 * the window count as samples.
 *
 * `actual_tokens` isn't tracked yet — we use `estimate` as a proxy and
 * surface that in the field name (`avg_tokens_per_task` documents the
 * intent; the value is `mean(estimate)`).
 */
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

import { readEvents, type ProjectBoardEvent } from "./project-board.js";
import { parseFrontmatter } from "./frontmatter.js";

export interface LabelStats {
  /** Fraction of attributed tasks that ended in `status: done`. */
  success_rate: number;
  /** Mean `estimate` across attributed tasks in the window. */
  avg_tokens_per_task: number;
  /** Sample size — number of attributed tasks. */
  n: number;
}

export interface AgentStats {
  /** Stats keyed by label string. Labels with `n === 0` are omitted. */
  byLabel: Record<string, LabelStats>;
}

const WINDOW_MS = 30 * 24 * 60 * 60 * 1000;

interface TaskMeta {
  labels: string[];
  estimate: number;
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
      const labels = Array.isArray(fm.labels)
        ? (fm.labels as string[]).filter((s) => typeof s === "string")
        : [];
      const estimate = typeof fm.estimate === "number" ? fm.estimate : 0;
      out.set(slug, { labels, estimate });
    } catch {
      /* skip unreadable */
    }
  }
  return out;
}

/**
 * Walk events and reconstruct, per task, the assignee at the moment status
 * transitioned to a terminal state inside the window. Returns one entry per
 * task that reached a terminal state in the window.
 */
interface DoneAttribution {
  task_id: string;
  assignee: string;
  done: boolean;
}

function attributeDoneTasks(
  events: ProjectBoardEvent[],
  now: number,
): DoneAttribution[] {
  const cutoff = now - WINDOW_MS;
  const currentAssignee = new Map<string, string | null>();
  const out: DoneAttribution[] = [];

  for (const ev of events) {
    if (ev.type === "task_assigned") {
      const p = (ev.payload ?? {}) as { to?: string | null };
      const to = p.to ?? null;
      if (ev.task_id) currentAssignee.set(ev.task_id, to);
      continue;
    }
    if (ev.type === "task_status_changed") {
      const p = (ev.payload ?? {}) as { to?: string };
      const status = p.to;
      if (status !== "done") continue;
      if (!ev.task_id) continue;
      const ts = Date.parse(ev.ts);
      if (!Number.isFinite(ts) || ts < cutoff) continue;
      const assignee = currentAssignee.get(ev.task_id);
      if (!assignee) continue;
      out.push({ task_id: ev.task_id, assignee, done: true });
    }
  }
  return out;
}

/**
 * Compute capability stats for a single agent across all labels.
 *
 * Stage-1 semantics: success_rate = (done attributions to this agent) /
 * (all attributions to this agent for that label). Since we only record
 * done attributions today, success_rate is effectively 1.0 for any sampled
 * agent+label. When `escalated` or `failed` terminal states land, the
 * algorithm picks them up automatically through the same path.
 */
export function getAgentStats(
  repoRoot: string,
  agentId: string,
  opts: { now?: number } = {},
): AgentStats {
  const now = opts.now ?? Date.now();
  const events = readEvents(repoRoot);
  const meta = readTaskMeta(repoRoot);
  const attributions = attributeDoneTasks(events, now);

  const buckets = new Map<string, { done: number; total: number; sumEstimate: number }>();

  for (const a of attributions) {
    if (a.assignee !== agentId) continue;
    const m = meta.get(a.task_id);
    if (!m) continue;
    for (const label of m.labels) {
      let b = buckets.get(label);
      if (!b) {
        b = { done: 0, total: 0, sumEstimate: 0 };
        buckets.set(label, b);
      }
      b.total += 1;
      if (a.done) b.done += 1;
      b.sumEstimate += m.estimate;
    }
  }

  const byLabel: Record<string, LabelStats> = {};
  for (const [label, b] of buckets) {
    if (b.total === 0) continue;
    byLabel[label] = {
      success_rate: b.done / b.total,
      avg_tokens_per_task: b.sumEstimate / b.total,
      n: b.total,
    };
  }
  return { byLabel };
}

/**
 * Stats for many agents in one pass. Cheaper than calling `getAgentStats`
 * per agent because we only walk the event log once.
 */
export function getAllAgentStats(
  repoRoot: string,
  opts: { now?: number } = {},
): Map<string, AgentStats> {
  const now = opts.now ?? Date.now();
  const events = readEvents(repoRoot);
  const meta = readTaskMeta(repoRoot);
  const attributions = attributeDoneTasks(events, now);

  const perAgent = new Map<
    string,
    Map<string, { done: number; total: number; sumEstimate: number }>
  >();

  for (const a of attributions) {
    const m = meta.get(a.task_id);
    if (!m) continue;
    let bucket = perAgent.get(a.assignee);
    if (!bucket) {
      bucket = new Map();
      perAgent.set(a.assignee, bucket);
    }
    for (const label of m.labels) {
      let b = bucket.get(label);
      if (!b) {
        b = { done: 0, total: 0, sumEstimate: 0 };
        bucket.set(label, b);
      }
      b.total += 1;
      if (a.done) b.done += 1;
      b.sumEstimate += m.estimate;
    }
  }

  const out = new Map<string, AgentStats>();
  for (const [agent, bucket] of perAgent) {
    const byLabel: Record<string, LabelStats> = {};
    for (const [label, b] of bucket) {
      if (b.total === 0) continue;
      byLabel[label] = {
        success_rate: b.done / b.total,
        avg_tokens_per_task: b.sumEstimate / b.total,
        n: b.total,
      };
    }
    out.set(agent, { byLabel });
  }
  return out;
}

/**
 * Set of agent ids that have ever been assigned a task in the log. Used by
 * the router as the default candidate pool when the caller does not pass an
 * explicit member list.
 */
export function listKnownAgents(repoRoot: string): string[] {
  const events = readEvents(repoRoot);
  const set = new Set<string>();
  for (const ev of events) {
    if (ev.type !== "task_assigned") continue;
    const p = (ev.payload ?? {}) as { to?: string | null };
    if (typeof p.to === "string" && p.to.length > 0) set.add(p.to);
  }
  return Array.from(set).sort();
}
