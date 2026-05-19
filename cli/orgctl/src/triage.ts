/**
 * MCP tool group: triage_normalize.
 *
 * Pure structural shaper for inbound items. The real triage intelligence
 * lives in the agent persona prompt (templates/_agents/triage/member.md);
 * this module provides the deterministic skeleton: it canonicalises the
 * inbound payload into the org-contract task-input shape and emits a
 * confidence score the agent can override.
 *
 * Sibling of criteria.ts — same DispatchOptions shape, same `tokens_used: 0`
 * envelope, same error code vocabulary. No LLM call.
 */

export type Priority = "low" | "med" | "high";

export interface InboundRaw {
  title: string;
  body?: string;
  source?: string;
  external_ref?: {
    kind: string;
    id: string | number;
    url?: string;
  };
}

export interface TriageNormalized {
  title: string;
  labels: string[];
  priority: Priority;
  criteria: never[];
  triage_confidence: number;
}

interface DispatchOptions {
  fetch?: typeof fetch;
  lensBase?: string;
}

export type TriageResult =
  | { tokens_used: 0; ok: true; result: TriageNormalized }
  | { tokens_used: 0; error: { code: string; message: string } };

// ---------- Heuristics ----------

const HIGH_KEYWORDS = ["crash", "broken", "regression"];
const LOW_KEYWORDS = ["feature", "would be nice"];

/**
 * Canonicalise a raw inbound item.
 *
 * Heuristics are intentionally minimal — the agent persona is expected to
 * override priority/labels/criteria once the LLM call runs. This function
 * also serves the no-LLM path used by tests and dry-runs.
 */
export function normalizeInbound(raw: InboundRaw): TriageNormalized {
  if (!raw || typeof raw !== "object") {
    return {
      title: "",
      labels: ["task"],
      priority: "med",
      criteria: [],
      triage_confidence: 0,
    };
  }

  const title = typeof raw.title === "string" ? raw.title.trim() : "";
  const body = typeof raw.body === "string" ? raw.body : "";
  const haystack = `${title}\n${body}`.toLowerCase();

  let priority: Priority = "med";
  let label = "task";
  let strongHit = false;

  for (const kw of HIGH_KEYWORDS) {
    if (haystack.includes(kw)) {
      priority = "high";
      label = "bug";
      strongHit = true;
      break;
    }
  }

  if (!strongHit) {
    for (const kw of LOW_KEYWORDS) {
      if (haystack.includes(kw)) {
        priority = "low";
        label = "feature";
        strongHit = true;
        break;
      }
    }
  }

  let triage_confidence: number;
  if (body.trim().length === 0) {
    triage_confidence = 0.3;
  } else if (strongHit) {
    triage_confidence = 0.8;
  } else {
    triage_confidence = 0.5;
  }

  return {
    title,
    labels: [label],
    priority,
    criteria: [],
    triage_confidence,
  };
}

// ---------- Tool definition ----------

export const TRIAGE_TOOL_DEFS = [
  {
    name: "triage_normalize",
    description:
      "Use `triage_normalize` to convert a raw inbound item (issue text, email body, slack handoff) into a canonical task shape: `{ title, labels[], priority: low|med|high, criteria: [], triage_confidence }`. Heuristic-only — the calling agent should use the result as a starting point and override `priority`, `labels`, and `criteria` based on its own judgement. `triage_confidence` ∈ [0,1] indicates how strongly the heuristics matched (0.3 = empty body, 0.5 = no strong keyword, 0.8 = strong keyword hit). Criteria is always returned empty; the agent fills it via `criteria_set`.",
    inputSchema: {
      type: "object",
      properties: {
        title: { type: "string", description: "Inbound title — required." },
        body: { type: "string", description: "Inbound body, optional." },
        source: {
          type: "string",
          description: "Free-form source tag (e.g. `github`, `email`, `slack`).",
        },
        external_ref: {
          type: "object",
          description: "Optional pointer back to the source item.",
          properties: {
            kind: { type: "string" },
            id: { type: ["string", "number"] },
            url: { type: "string" },
          },
          required: ["kind", "id"],
        },
      },
      required: ["title"],
    },
  },
] as const;

// ---------- Dispatcher ----------

export async function dispatchTriage(
  name: string,
  args: unknown,
  _opts: DispatchOptions = {},
): Promise<TriageResult> {
  if (name !== "triage_normalize") {
    return {
      tokens_used: 0,
      error: { code: "unknown_tool", message: `triage.ts cannot dispatch ${name}` },
    };
  }
  const raw = args as InboundRaw;
  if (!raw || typeof raw !== "object") {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "args must be an object" },
    };
  }
  if (typeof raw.title !== "string" || raw.title.trim().length === 0) {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "title is required and must be non-empty" },
    };
  }
  return { tokens_used: 0, ok: true, result: normalizeInbound(raw) };
}
