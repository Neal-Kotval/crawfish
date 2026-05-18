/**
 * Project-level cycles — Week 1.1 of the NOW phase.
 *
 * A cycle is a time-boxed bucket of tasks with a token budget. Cycles live
 * as JSON files at `<repoRoot>/.crawfish/cycles/<id>.json`. The board.jsonl
 * journal carries `cycle_created` / `cycle_updated` / `cycle_closed` events
 * for the activity feed.
 *
 * Token-budget rollup: for a given cycle, sum the `estimate` frontmatter of
 * every task whose `cycle` field points at this cycle. Compare to the
 * cycle's `token_budget` to surface allocation pressure in the Plan tab.
 */
import {
  readFileSync,
  writeFileSync,
  existsSync,
  readdirSync,
  mkdirSync,
} from "node:fs";
import { join } from "node:path";

import { appendEvent, makeEvent } from "./project-board.js";
import { parseFrontmatter } from "./frontmatter.js";

export interface Cycle {
  /** ULID, prefixed `cyc_`. */
  id: string;
  /** Human-readable name. */
  name: string;
  /** ISO date (YYYY-MM-DD). */
  start: string;
  /** ISO date (YYYY-MM-DD). */
  end: string;
  /** Total tokens allocated to this cycle. */
  token_budget: number;
  /** "open" while in-flight; "closed" once the cycle's end date passes or the user closes it. */
  status: "open" | "closed";
  /** ISO 8601 timestamp. */
  created_at: string;
}

export interface CycleRollup {
  cycle: Cycle;
  task_count: number;
  estimate_used: number;
  estimate_remaining: number;
  pct_used: number;
  by_status: { todo: number; doing: number; done: number; blocked: number };
  overspent: boolean;
}

function cyclesDir(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "cycles");
}

function cyclePath(repoRoot: string, id: string): string {
  return join(cyclesDir(repoRoot), `${id}.json`);
}

function tasksDir(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "tasks");
}

const ID_RE = /^cyc_[A-Z0-9]{1,32}$/;

function assertValidId(id: string): void {
  if (!ID_RE.test(id)) throw new Error(`invalid_cycle_id: ${id}`);
}

export interface CreateCycleInput {
  id: string;
  name: string;
  start: string;
  end: string;
  token_budget: number;
  actor?: string;
}

export function createCycle(repoRoot: string, input: CreateCycleInput): Cycle {
  assertValidId(input.id);
  const path = cyclePath(repoRoot, input.id);
  if (existsSync(path)) throw new Error(`cycle_already_exists: ${input.id}`);
  mkdirSync(cyclesDir(repoRoot), { recursive: true });

  const cycle: Cycle = {
    id: input.id,
    name: input.name,
    start: input.start,
    end: input.end,
    token_budget: input.token_budget,
    status: "open",
    created_at: new Date().toISOString(),
  };
  writeFileSync(path, JSON.stringify(cycle, null, 2) + "\n", "utf8");

  const prevActor = process.env.CRAWFISH_ACTOR;
  if (input.actor) process.env.CRAWFISH_ACTOR = input.actor;
  try {
    appendEvent(
      repoRoot,
      makeEvent("cycle_created", {
        cycle_id: input.id,
        payload: {
          name: input.name,
          start: input.start,
          end: input.end,
          token_budget: input.token_budget,
        },
      }),
    );
  } finally {
    if (input.actor) {
      if (prevActor === undefined) delete process.env.CRAWFISH_ACTOR;
      else process.env.CRAWFISH_ACTOR = prevActor;
    }
  }

  return cycle;
}

export function readCycle(repoRoot: string, id: string): Cycle | null {
  assertValidId(id);
  const path = cyclePath(repoRoot, id);
  if (!existsSync(path)) return null;
  return JSON.parse(readFileSync(path, "utf8")) as Cycle;
}

export function listCycles(repoRoot: string): Cycle[] {
  const dir = cyclesDir(repoRoot);
  if (!existsSync(dir)) return [];
  const cycles: Cycle[] = [];
  for (const name of readdirSync(dir)) {
    if (!name.endsWith(".json")) continue;
    try {
      cycles.push(JSON.parse(readFileSync(join(dir, name), "utf8")) as Cycle);
    } catch {
      /* skip unreadable */
    }
  }
  return cycles.sort((a, b) => a.start.localeCompare(b.start));
}

/**
 * Compute token-budget rollup for a cycle by scanning `.crawfish/tasks/*.md`
 * and summing `estimate` for tasks whose `cycle` field matches `id`.
 *
 * Stage-1 cost is acceptable (linear in #tasks). When task counts grow large
 * we'll back this with an index derived from the journal.
 */
export function computeRollup(repoRoot: string, id: string): CycleRollup | null {
  const cycle = readCycle(repoRoot, id);
  if (!cycle) return null;
  const dir = tasksDir(repoRoot);
  const by_status = { todo: 0, doing: 0, done: 0, blocked: 0 };
  let task_count = 0;
  let estimate_used = 0;
  if (existsSync(dir)) {
    for (const name of readdirSync(dir)) {
      if (!name.endsWith(".md")) continue;
      try {
        const raw = readFileSync(join(dir, name), "utf8");
        const { fm } = parseFrontmatter(raw);
        if (fm.cycle !== id) continue;
        task_count++;
        const est = typeof fm.estimate === "number" ? fm.estimate : 0;
        estimate_used += est;
        const status = (fm.status as string) ?? "todo";
        if (status === "todo" || status === "doing" || status === "done" || status === "blocked") {
          by_status[status as keyof typeof by_status]++;
        }
      } catch {
        /* skip unreadable */
      }
    }
  }
  const estimate_remaining = cycle.token_budget - estimate_used;
  const pct_used = cycle.token_budget > 0
    ? Math.round((estimate_used / cycle.token_budget) * 1000) / 10
    : 0;
  return {
    cycle,
    task_count,
    estimate_used,
    estimate_remaining,
    pct_used,
    by_status,
    overspent: estimate_used > cycle.token_budget,
  };
}
