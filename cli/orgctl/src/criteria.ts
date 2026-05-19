/**
 * MCP tool group: criteria_set + criteria_attest.
 *
 * Exported as CRITERIA_TOOL_DEFS + dispatchCriteria so the lead can wire them
 * into crawfish-orgctl/src/index.ts at finalization without touching this
 * file.
 *
 * All responses conform to optimizer contract v1.0: `tokens_used: 0` on every
 * response (criteria writes are metadata; no LLM call).
 * Error envelope: `{ tokens_used: 0, error: { code, message } }` with codes
 * drawn from org-contract.md §6:
 *   not_found | invalid_member | acl_denied | criteria_unmet |
 *   unknown_criterion | stale
 *
 * Sibling of preflight.ts — same DispatchOptions shape, same fetch-injection
 * idiom, same error envelope.
 *
 * Upstream wire format: PATCH on the task's criteria sub-resource (lens
 * lead-only edit registers the route). The lens server is responsible for
 * appending the corresponding `task_updated` BoardEvent.
 */

// ---------- Types ----------

/** Criterion kinds — mirrors `CriterionKind` in org-contract.md §3. */
export type CriterionKind =
  | "behavioral"
  | "test"
  | "metric"
  | "preflight"
  | "manual";

/** Evidence on a met criterion — mirrors `CriterionEvidence` in §3. */
export interface CriterionEvidence {
  kind: CriterionKind;
  payload: Record<string, unknown>;
}

/** A single acceptance criterion — mirrors `Criterion` in §3. */
export interface Criterion {
  id: string;
  statement: string;
  kind: CriterionKind;
  evidence?: CriterionEvidence;
}

export interface CriteriaSetArgs {
  org_id: string;
  task_id: string;
  by: string;
  criteria: Criterion[];
}

export interface CriteriaAttestArgs {
  org_id: string;
  task_id: string;
  criterion_id: string;
  by: string;
  evidence: CriterionEvidence;
}

export type CriteriaResult =
  | { tokens_used: 0; ok: true }
  | { tokens_used: 0; error: { code: string; message: string } };

interface DispatchOptions {
  fetch?: typeof fetch;
  lensBase?: string;
}

// ---------- Validation ----------

const CRITERION_ID_RE = /^[a-z0-9_-]{1,32}$/;
const MIN_STATEMENT_LEN = 8;
const VALID_KINDS: ReadonlySet<CriterionKind> = new Set([
  "behavioral",
  "test",
  "metric",
  "preflight",
  "manual",
]);

function validateCriterion(c: Criterion): string | null {
  if (typeof c.id !== "string" || !CRITERION_ID_RE.test(c.id)) {
    return `criterion id must match /^[a-z0-9_-]{1,32}$/ (got ${JSON.stringify(c.id)})`;
  }
  if (typeof c.statement !== "string" || c.statement.trim().length < MIN_STATEMENT_LEN) {
    return `criterion statement must be ≥${MIN_STATEMENT_LEN} chars`;
  }
  if (!VALID_KINDS.has(c.kind)) {
    return `criterion kind must be one of ${[...VALID_KINDS].join("|")}`;
  }
  if (c.evidence !== undefined) {
    const evErr = validateEvidence(c.evidence);
    if (evErr) return evErr;
    if (c.evidence.kind !== c.kind) {
      return `evidence.kind (${c.evidence.kind}) must match criterion.kind (${c.kind})`;
    }
  }
  return null;
}

function validateEvidence(e: CriterionEvidence): string | null {
  if (!e || typeof e !== "object") return "evidence must be an object";
  if (!VALID_KINDS.has(e.kind)) {
    return `evidence kind must be one of ${[...VALID_KINDS].join("|")}`;
  }
  if (!e.payload || typeof e.payload !== "object") {
    return "evidence payload must be an object";
  }
  return null;
}

// ---------- Tool definitions (schema for MCP ListTools) ----------

export const CRITERIA_TOOL_DEFS = [
  {
    name: "criteria_set",
    description:
      "Use `criteria_set` to declare the acceptance criteria for a task before work begins. Each criterion has an `id` (slug, /^[a-z0-9_-]{1,32}$/), a human-readable `statement` (≥8 chars), and a `kind` of `behavioral` | `test` | `metric` | `preflight` | `manual`. Setting criteria REPLACES the existing array on the task. A task with non-empty criteria cannot transition to `done` until every criterion has `evidence` attached (use `criteria_attest`).",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string", description: "ULID of the org." },
        task_id: { type: "string", description: "ULID of the task." },
        by: {
          type: "string",
          description: "Member id of the actor setting the criteria.",
        },
        criteria: {
          type: "array",
          description: "Replacement criteria array. Empty array clears.",
          items: {
            type: "object",
            properties: {
              id: { type: "string", description: "Slug, /^[a-z0-9_-]{1,32}$/, unique within task." },
              statement: { type: "string", description: "Human-readable acceptance statement (≥8 chars)." },
              kind: {
                type: "string",
                enum: ["behavioral", "test", "metric", "preflight", "manual"],
                description: "Criterion kind.",
              },
              evidence: {
                type: "object",
                description:
                  "Optional evidence (present iff already met). kind must match the criterion's kind; payload is kind-specific.",
              },
            },
            required: ["id", "statement", "kind"],
          },
        },
      },
      required: ["org_id", "task_id", "by", "criteria"],
    },
  },
  {
    name: "criteria_attest",
    description:
      "Use `criteria_attest` to attach evidence to a single criterion, marking it met. Evidence shape depends on the criterion's `kind`: `test` → `{ path, case }`; `metric` → `{ metric, observed, threshold, source }`; `preflight` → `{ event_id, by, at }` (set automatically by `preflight_attest`); `behavioral` → `{ url?, screenshot?, note? }`; `manual` → `{ by, at, note? }`. The evidence's `kind` MUST match the criterion's declared `kind`. Once all criteria on a task have evidence, the task may transition to `done`.",
    inputSchema: {
      type: "object",
      properties: {
        org_id: { type: "string", description: "ULID of the org." },
        task_id: { type: "string", description: "ULID of the task." },
        criterion_id: {
          type: "string",
          description: "ID of the criterion to attest — must match an existing task.criteria[*].id.",
        },
        by: {
          type: "string",
          description: "Member id of the attesting actor.",
        },
        evidence: {
          type: "object",
          properties: {
            kind: {
              type: "string",
              enum: ["behavioral", "test", "metric", "preflight", "manual"],
              description: "Must equal the criterion's declared kind.",
            },
            payload: {
              type: "object",
              description: "Kind-specific evidence payload (see tool description).",
            },
          },
          required: ["kind", "payload"],
        },
      },
      required: ["org_id", "task_id", "criterion_id", "by", "evidence"],
    },
  },
] as const;

// ---------- Dispatcher ----------

export async function dispatchCriteria(
  name: string,
  args: unknown,
  opts: DispatchOptions = {},
): Promise<CriteriaResult> {
  if (name === "criteria_set") {
    return dispatchCriteriaSet(args as CriteriaSetArgs, opts);
  }
  if (name === "criteria_attest") {
    return dispatchCriteriaAttest(args as CriteriaAttestArgs, opts);
  }
  return {
    tokens_used: 0,
    error: { code: "unknown_tool", message: `criteria.ts cannot dispatch ${name}` },
  };
}

export async function dispatchCriteriaSet(
  args: CriteriaSetArgs,
  opts: DispatchOptions = {},
): Promise<CriteriaResult> {
  if (!Array.isArray(args.criteria)) {
    return {
      tokens_used: 0,
      error: { code: "invalid_argument", message: "criteria must be an array" },
    };
  }
  const seen = new Set<string>();
  for (const c of args.criteria) {
    const err = validateCriterion(c);
    if (err) {
      return { tokens_used: 0, error: { code: "invalid_argument", message: err } };
    }
    if (seen.has(c.id)) {
      return {
        tokens_used: 0,
        error: { code: "invalid_argument", message: `duplicate criterion id: ${c.id}` },
      };
    }
    seen.add(c.id);
  }

  const fetchFn = opts.fetch ?? fetch;
  const lensBase = opts.lensBase ?? "http://127.0.0.1:7880";
  const url = `${lensBase}/api/orgs/${args.org_id}/board/tasks/${args.task_id}/criteria`;

  return await sendPatch(fetchFn, url, { by: args.by, criteria: args.criteria });
}

export async function dispatchCriteriaAttest(
  args: CriteriaAttestArgs,
  opts: DispatchOptions = {},
): Promise<CriteriaResult> {
  if (typeof args.criterion_id !== "string" || !CRITERION_ID_RE.test(args.criterion_id)) {
    return {
      tokens_used: 0,
      error: {
        code: "invalid_argument",
        message: "criterion_id must match /^[a-z0-9_-]{1,32}$/",
      },
    };
  }
  const evErr = validateEvidence(args.evidence);
  if (evErr) {
    return { tokens_used: 0, error: { code: "invalid_argument", message: evErr } };
  }

  const fetchFn = opts.fetch ?? fetch;
  const lensBase = opts.lensBase ?? "http://127.0.0.1:7880";
  const url = `${lensBase}/api/orgs/${args.org_id}/board/tasks/${args.task_id}/criteria/${args.criterion_id}`;

  return await sendPatch(fetchFn, url, { by: args.by, evidence: args.evidence });
}

async function sendPatch(
  fetchFn: typeof fetch,
  url: string,
  body: Record<string, unknown>,
): Promise<CriteriaResult> {
  try {
    const res = await fetchFn(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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

    return { tokens_used: 0, ok: true };
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
