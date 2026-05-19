/**
 * Project-level board event log — the derived journal that sits alongside
 * `.crawfish/tasks/*.md`. Per ADR-001 (Option C), the `.md` files are
 * canonical and this jsonl is the rebuildable index used for activity feed,
 * SSE streaming, and aggregations.
 *
 * Event schema borrows from `cli/orgctl/src/board.ts` where overlap exists,
 * so the org-level and project-level vocabularies stay aligned.
 *
 * All writes append to `<repoRoot>/.crawfish/board.jsonl`. The file is
 * created on first append; readers tolerate its absence.
 */
import { appendFileSync, readFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";

export type ProjectBoardEventType =
  | "task_created"
  | "task_updated"
  | "task_renamed"
  | "task_deleted"
  | "task_status_changed"
  | "task_assigned"
  | "task_added_to_cycle"
  | "task_removed_from_cycle"
  | "task_added_to_epic"
  | "task_removed_from_epic"
  | "task_linked"
  | "task_unlinked"
  | "cycle_created"
  | "cycle_updated"
  | "cycle_closed"
  | "epic_created"
  | "epic_updated"
  | "epic_closed"
  | "criterion_set"
  | "criterion_met"
  | "criterion_cleared";

export interface ProjectBoardEvent {
  /** ISO 8601 timestamp. */
  ts: string;
  /** Identity of writer. Stage 1: always "local". Stage 2: real user. */
  actor: string;
  /** Event type. See `ProjectBoardEventType`. */
  type: ProjectBoardEventType;
  /** Task slug, if the event scopes to a task. */
  task_id?: string;
  /** Cycle ULID, if the event scopes to a cycle. */
  cycle_id?: string;
  /** Epic ULID, if the event scopes to an epic. */
  epic_id?: string;
  /** Type-specific payload (status before/after, fields changed, etc.). */
  payload?: Record<string, unknown>;
}

export function boardPath(repoRoot: string): string {
  return join(repoRoot, ".crawfish", "board.jsonl");
}

/**
 * Append a single event. Creates `.crawfish/` if missing. Synchronous to
 * keep the single-writer module simple — projectctl is a short-lived CLI,
 * not a long-running server.
 */
export function appendEvent(repoRoot: string, ev: ProjectBoardEvent): void {
  const path = boardPath(repoRoot);
  mkdirSync(dirname(path), { recursive: true });
  appendFileSync(path, JSON.stringify(ev) + "\n", "utf8");
}

export function readEvents(repoRoot: string): ProjectBoardEvent[] {
  const path = boardPath(repoRoot);
  if (!existsSync(path)) return [];
  const raw = readFileSync(path, "utf8");
  const out: ProjectBoardEvent[] = [];
  for (const line of raw.split("\n")) {
    if (line.trim() === "") continue;
    try {
      out.push(JSON.parse(line) as ProjectBoardEvent);
    } catch {
      // Corrupt line — skip rather than abort. `craw board rebuild` is the recovery path.
    }
  }
  return out;
}

export function makeEvent(
  type: ProjectBoardEventType,
  fields: Omit<ProjectBoardEvent, "ts" | "actor" | "type"> = {},
): ProjectBoardEvent {
  return {
    ts: new Date().toISOString(),
    actor: process.env.CRAWFISH_ACTOR ?? "local",
    type,
    ...fields,
  };
}
