/**
 * MCP tool group: task_budget_report — agent reports observed spend on a
 * task; the server decides whether to fire a `budget_breach` activity event
 * and flip the task's status to `escalated`.
 *
 * Design choice: ship ONE MCP tool (`task_budget_report`) backed by the pure
 * function `onBudgetBreach(task, signal)`. The tool is a thin remote-call
 * wrapper that posts the signal to the lens; the lens applies
 * `onBudgetBreach` server-side. Unit tests target `onBudgetBreach` directly
 * because it is the entire decision logic.
 *
 * Spec anchors:
 *   - ROADMAP W2.5: "Auto-escalate at 100%."
 *   - org-contract.md §3 `ActivityKind` includes `budget_breach` and
 *     `escalated`; §3.3 mentions per-task `token_budget` / `token_spent`.
 *
 * NOTE — TaskStatus widening. org-contract.md §3 currently declares
 *   type TaskStatus = "backlog" | "in_progress" | "review" | "done";
 * Auto-escalation introduces a new status `"escalated"`. This file widens
 * the contract LOCALLY (see `EscalatedTaskStatus` below). The shared
 * `TaskStatus` in board.ts is intentionally NOT touched here; the lead
 * lands that widening in a coordinated registry edit.
 *
 * Error envelope and `tokens_used: 0` follow preflight.ts conventions.
 */

import type { TaskStatus, ActivityEntry } from "./board.js";

// ---------- Types ----------

/** Widened task status that includes the escalated terminal-ish state. */
export type EscalatedTaskStatus = TaskStatus | "escalated";

/**
 * Minimal task shape this module cares about. The lens-side task object is
 * richer; we only need the fields involved in the budget decision. We avoid
 * importing `FoldedTask` because that type doesn't yet carry budget fields
 * (those are W2-scope additions per ROADMAP).
 */
export interface BudgetTask {
  id: string;
  assignee: string | null;
  status: EscalatedTaskStatus;
  token_budget: number;        // 0 = uncapped
  token_spent: number;
  escalated_at?: string;
  escalated_reason?: string;
}

export interface BudgetSignal {
  task_id: string;
  spent_cents: number;
  budget_cents: number;
  /** Optional override for "now"; tests inject a fixed timestamp. */
  now?: string;
}

export interface BudgetBreachEvent {
  type: "budget_breach";
  ts: string;
  task_id: string;
  payload: {
    spent_cents: number;
    budget_cents: number;
    ratio: number;
    scope: "task";
    /** Stub for Week 5 — actual delivery is not in this slice. */
    notify?: { to: string | null };
  };
}

export interface TaskPatch {
  status?: EscalatedTaskStatus;
  escalated_at?: string;
  escalated_reason?: string;
  activity_log_append?: ActivityEntry[];
}

export type OnBreachOutcome =
  | { breached: false }
  | { breached: true; event: BudgetBreachEvent; patch: TaskPatch };

// ---------- Pure decision function ----------

/**
 * Decide whether a budget signal triggers an escalation.
 *
 * Rules:
 *   - `budget_cents <= 0` is treated as "uncapped" → never escalates.
 *   - ratio = spent_cents / budget_cents; ratio ≥ 1.0 triggers a breach.
 *   - If the task is already `"escalated"`, NO new event is emitted
 *     (dedupe — matches the spec's "fires once per breach episode" rule).
 *   - On breach: emit a `budget_breach` event AND a patch flipping status
 *     to `"escalated"`, stamping `escalated_at` + `escalated_reason`.
 *   - Notification target = primary assignee (null if unassigned). Actual
 *     delivery is Week 5; we only emit the `notify` field.
 */
export function onBudgetBreach(
  task: BudgetTask,
  signal: BudgetSignal,
): OnBreachOutcome {
  if (!Number.isFinite(signal.budget_cents) || signal.budget_cents <= 0) {
    return { breached: false };
  }
  if (!Number.isFinite(signal.spent_cents) || signal.spent_cents < 0) {
    return { breached: false };
  }

  const ratio = signal.spent_cents / signal.budget_cents;
  if (ratio < 1.0) {
    return { breached: false };
  }
  if (task.status === "escalated") {
    return { breached: false };
  }

  const ts = signal.now ?? new Date().toISOString();
  const activityEntry: ActivityEntry = {
    by: "system",
    at: ts,
    kind: "budget_breach",
    payload: {
      scope: "task",
      id: task.id,
      spent_cents: signal.spent_cents,
      budget_cents: signal.budget_cents,
      ratio,
    },
  };

  const event: BudgetBreachEvent = {
    type: "budget_breach",
    ts,
    task_id: task.id,
    payload: {
      spent_cents: signal.spent_cents,
      budget_cents: signal.budget_cents,
      ratio,
      scope: "task",
      notify: { to: task.assignee },
    },
  };

  const patch: TaskPatch = {
    status: "escalated",
    escalated_at: ts,
    escalated_reason: "budget_breach",
    activity_log_append: [activityEntry],
  };

  return { breached: true, event, patch };
}

// ---------- MCP tool surface ----------

export interface BudgetReportArgs {
  org_id: string;
  task_id: string;
  by: string;
  spent_cents: number;
  budget_cents: number;
}

export type BudgetReportResult =
  | { tokens_used: 0; ok: true; escalated: boolean; ratio: number }
  | { tokens_used: 0; error: { code: string; message: string } };

interface DispatchOptions {
  fetch?: typeof fetch;
  lensBase?: string;
}

export const BUDGET_TOOL_DEFS = [
  {
    name: "task_budget_report",
    description:
      "Use `task_budget_report` to report observed token spend (in cents) against a task's budget. When `spent_cents` ≥ `budget_cents` the lens server will fire a `budget_breach` activity entry, flip the task's status to `escalated`, and stamp `escalated_at` / `escalated_reason: \"budget_breach\"`. Notification of the primary assignee is queued for delivery (Week 5). Repeated reports on an already-escalated task are NO-OPs (no duplicate events).",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string", description: "ULID of the org." },
        task_id: { type: "string", description: "ULID of the task." },
        by: {
          type: "string",
          description: "Member id of the reporting actor (usually the assignee agent).",
        },
        spent_cents: {
          type: "number",
          description: "Observed spend in cents (integer, ≥0).",
        },
        budget_cents: {
          type: "number",
          description: "Configured budget cap in cents. 0 or negative = uncapped (no breach).",
        },
      },
      required: ["org_id", "task_id", "by", "spent_cents", "budget_cents"],
    },
  },
] as const;

export async function dispatchBudget(
  name: string,
  args: unknown,
  opts: DispatchOptions = {},
): Promise<BudgetReportResult> {
  if (name !== "task_budget_report") {
    return {
      tokens_used: 0,
      error: { code: "unknown_tool", message: `budget.ts cannot dispatch ${name}` },
    };
  }
  return dispatchBudgetReport(args as BudgetReportArgs, opts);
}

export async function dispatchBudgetReport(
  args: BudgetReportArgs,
  opts: DispatchOptions = {},
): Promise<BudgetReportResult> {
  if (!Number.isFinite(args.spent_cents) || args.spent_cents < 0) {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "spent_cents must be a non-negative number" },
    };
  }
  if (!Number.isFinite(args.budget_cents)) {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "budget_cents must be a finite number" },
    };
  }

  const fetchFn = opts.fetch ?? fetch;
  const lensBase = opts.lensBase ?? "http://127.0.0.1:7880";
  const url = `${lensBase}/api/orgs/${args.org_id}/board/tasks/${args.task_id}/budget`;

  try {
    const res = await fetchFn(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        by: args.by,
        spent_cents: args.spent_cents,
        budget_cents: args.budget_cents,
      }),
    });

    let json: unknown;
    try {
      json = await res.json();
    } catch {
      json = {};
    }

    if (!res.ok) {
      const errBody = json as { error?: { code?: string; message?: string } };
      const code = errBody?.error?.code ?? "upstream_error";
      const message =
        errBody?.error?.message ?? `HTTP ${res.status}${res.statusText ? ` ${res.statusText}` : ""}`;
      return { tokens_used: 0, error: { code, message } };
    }

    const ok = json as { escalated?: boolean; ratio?: number };
    const ratio =
      args.budget_cents > 0 ? args.spent_cents / args.budget_cents : 0;
    return {
      tokens_used: 0,
      ok: true,
      escalated: Boolean(ok.escalated),
      ratio: typeof ok.ratio === "number" ? ok.ratio : ratio,
    };
  } catch (err) {
    return {
      tokens_used: 0,
      error: {
        code: "internal",
        message: err instanceof Error ? err.message : String(err),
      },
    };
  }
}
