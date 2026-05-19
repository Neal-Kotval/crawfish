/**
 * MCP tool group: planner_decompose.
 *
 * Pure heuristic decomposition of an epic into a subtask DAG. As with
 * triage.ts, the real decomposition reasoning lives in the planner agent
 * persona prompt; this module provides the deterministic skeleton + the
 * no-LLM path.
 *
 * The returned DAG uses string ids (`s1`, `s2`, ...) and a `depends_on`
 * array per subtask. The caller (lens / projectctl) is responsible for
 * minting real ULIDs when the proposal is materialised onto the board.
 */

export interface EpicInput {
  id: string;
  title: string;
  body?: string;
  labels?: string[];
}

export interface PlannerContext {
  /** Optional path to an org-level templates file that informs decomposition. */
  templateOrgFile?: string;
}

export interface SubtaskProposal {
  id: string;
  title: string;
  estimate?: string;
  labels?: string[];
  depends_on?: string[];
}

export interface DecompositionProposal {
  subtasks: SubtaskProposal[];
  rationale?: string;
}

interface DispatchOptions {
  fetch?: typeof fetch;
  lensBase?: string;
}

export type PlannerResult =
  | { tokens_used: 0; ok: true; result: DecompositionProposal }
  | { tokens_used: 0; error: { code: string; message: string } };

// ---------- Heuristic decomposition ----------

function noun(title: string, prefix: string): string {
  const t = title.trim();
  const lower = t.toLowerCase();
  if (lower.startsWith(prefix.toLowerCase() + " ")) {
    return t.slice(prefix.length + 1).trim() || "feature";
  }
  return t || "feature";
}

export function decomposeEpic(
  epic: EpicInput,
  _context: PlannerContext = {},
): DecompositionProposal {
  const title = (epic?.title ?? "").trim();
  const lower = title.toLowerCase();

  if (lower.startsWith("add ")) {
    const x = noun(title, "Add");
    return {
      subtasks: [
        { id: "s1", title: `Design ${x}` },
        { id: "s2", title: `Implement ${x}`, depends_on: ["s1"] },
        { id: "s3", title: `Test ${x}`, depends_on: ["s2"] },
        { id: "s4", title: `Document ${x}`, depends_on: ["s2"] },
      ],
      rationale: `Heuristic: epic title starts with "Add" — design → implement → (test ∥ document).`,
    };
  }

  if (lower.startsWith("refactor ")) {
    const x = noun(title, "Refactor");
    return {
      subtasks: [
        { id: "s1", title: `Identify call sites of ${x}` },
        { id: "s2", title: `Refactor ${x}`, depends_on: ["s1"] },
        { id: "s3", title: `Update tests for ${x}`, depends_on: ["s2"] },
      ],
      rationale: `Heuristic: epic title starts with "Refactor" — call-site survey → refactor → tests.`,
    };
  }

  const x = title || "epic";
  return {
    subtasks: [
      { id: "s1", title: `Design ${x}` },
      { id: "s2", title: `Implement ${x}`, depends_on: ["s1"] },
      { id: "s3", title: `Verify ${x}`, depends_on: ["s2"] },
    ],
    rationale: "Heuristic fallback: generic design → implement → verify DAG.",
  };
}

// ---------- Tool definition ----------

export const PLANNER_TOOL_DEFS = [
  {
    name: "planner_decompose",
    description:
      "Use `planner_decompose` to break an epic-sized task into a DAG of subtasks. Returns `{ subtasks: [{ id, title, estimate?, labels?, depends_on?[] }], rationale? }`. The shape is a proposal — the planner agent is expected to revise it (rename, reorder, add/remove subtasks) before any of them is materialised on the board. Subtask `id` values are local strings (`s1`, `s2`, ...); real task ULIDs are minted by the lens when the proposal is committed. `depends_on` may only reference earlier `id`s within the proposal.",
    inputSchema: {
      type: "object",
      properties: {
        epic: {
          type: "object",
          properties: {
            id: { type: "string" },
            title: { type: "string" },
            body: { type: "string" },
            labels: { type: "array", items: { type: "string" } },
          },
          required: ["id", "title"],
        },
        context: {
          type: "object",
          description: "Optional planner context (e.g. path to an org template file).",
          properties: {
            templateOrgFile: { type: "string" },
          },
        },
      },
      required: ["epic"],
    },
  },
] as const;

// ---------- Dispatcher ----------

export async function dispatchPlanner(
  name: string,
  args: unknown,
  _opts: DispatchOptions = {},
): Promise<PlannerResult> {
  if (name !== "planner_decompose") {
    return {
      tokens_used: 0,
      error: { code: "unknown_tool", message: `planner.ts cannot dispatch ${name}` },
    };
  }
  const a = (args ?? {}) as { epic?: EpicInput; context?: PlannerContext };
  if (!a.epic || typeof a.epic !== "object") {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "epic is required" },
    };
  }
  if (typeof a.epic.id !== "string" || a.epic.id.length === 0) {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "epic.id is required" },
    };
  }
  if (typeof a.epic.title !== "string" || a.epic.title.trim().length === 0) {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "epic.title is required" },
    };
  }
  return {
    tokens_used: 0,
    ok: true,
    result: decomposeEpic(a.epic, a.context ?? {}),
  };
}
