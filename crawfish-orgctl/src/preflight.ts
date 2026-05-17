/**
 * MCP tool group: preflight_attest tool.
 *
 * Exported as PREFLIGHT_TOOL_DEFS + dispatchPreflight so the lead can wire
 * them into crawfish-orgctl/src/index.ts at finalization without touching
 * this file.
 *
 * All responses conform to optimizer contract v1.0: `tokens_used: 0` on every
 * response (attestation is metadata, not an LLM call).
 * Error envelope: `{ tokens_used: 0, error: { code, message } }`.
 *
 * Per preflight-contract.md §4: the wrapper does NOT call the LLM, does NOT
 * cache, does NOT retry on a 409.
 */

// ---------- Types ----------

export interface PreflightArgs {
  org_id: string;
  task_id: string;
  criterion_id: string;
  by: string;
  statement: string;
  payload?: Record<string, unknown>;
}

export type PreflightResult =
  | { tokens_used: 0; event_id: string }
  | { tokens_used: 0; error: { code: string; message: string } };

interface DispatchOptions {
  fetch?: typeof fetch;
  lensBase?: string;
}

// ---------- Tool definitions (schema for MCP ListTools) ----------

export const PREFLIGHT_TOOL_DEFS = [
  {
    name: "preflight_attest",
    description:
      "Use `preflight_attest` to record that you have read the relevant spec, verified the test fixture, or otherwise completed the preparatory work for a criterion BEFORE you take the action that would satisfy it. Pass `criterion_id` from the task's `criteria` list. Statements must describe what you actually checked, in ≥16 characters. Do NOT preflight without doing the work — the activity log is auditable.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string", description: "ULID of the org." },
        task_id: { type: "string", description: "ULID of the task." },
        criterion_id: {
          type: "string",
          description: "ID of the criterion being preflighted — must match task.criteria[*].id.",
        },
        by: {
          type: "string",
          description: "Member id of the attesting agent. Must be an agent (not a human).",
        },
        statement: {
          type: "string",
          description: "Description of what you checked (≥16 characters). Be specific.",
        },
        payload: {
          type: "object",
          description:
            "Optional kind-specific evidence detail (kind, sources, tool_calls, note, etc.).",
        },
      },
      required: ["org_id", "task_id", "criterion_id", "by", "statement"],
    },
  },
] as const;

// ---------- Dispatcher ----------

export async function dispatchPreflight(
  args: PreflightArgs,
  opts: DispatchOptions = {},
): Promise<PreflightResult> {
  const fetchFn = opts.fetch ?? fetch;
  const lensBase = opts.lensBase ?? "http://127.0.0.1:7880";

  const url = `${lensBase}/api/orgs/${args.org_id}/preflight`;
  const bodyObj: Record<string, unknown> = {
    task_id: args.task_id,
    criterion_id: args.criterion_id,
    by: args.by,
    statement: args.statement,
  };
  if (args.payload !== undefined) {
    bodyObj.payload = args.payload;
  }

  try {
    const res = await fetchFn(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bodyObj),
    });

    let json: unknown;
    try {
      json = await res.json();
    } catch {
      json = {};
    }

    if (!res.ok) {
      const errBody = json as { error?: { code?: string; message?: string } };
      const code = errBody?.error?.code ?? String(res.status);
      const message = errBody?.error?.message ?? `HTTP ${res.status}`;
      return { tokens_used: 0, error: { code, message } };
    }

    const ok = json as { event_id?: string };
    return { tokens_used: 0, event_id: ok.event_id ?? "" };
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
