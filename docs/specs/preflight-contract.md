# Preflight Contract v1.0 (NOW-W2)

Companion to [`org-contract.md`](./org-contract.md). Defines how agent members **attest** that they've done a piece of preparatory work (read the relevant spec, ran the test, checked the migration plan, etc.) **before** taking an action whose criteria depend on it.

The orgctl MCP wrapper records every preflight as a `preflight_attested` activity event on the target task and (optionally) sets `evidence` on a criterion. The dash renders preflight chips on the task drawer.

---

## 1. Why preflight, not just "did you read the doc?"

Three problems we're fixing:

1. **Hallucinated authority.** Agents claim "I checked X" without leaving a trace. Preflight forces the claim into an event log with a timestamp and the originating tool call.
2. **Untraceable transitions.** A task moves to `done` and the cycle activity feed only shows `status_changed`. With preflight, the chain is `preflight_attested → criterion_met → status_changed`.
3. **Replayable trust.** Future cycles can audit which agents reliably preflight before action (the cycle stats §6 chart). Agents that skip preflights show up as a risk.

This is **not** a runtime gate that blocks tool calls. It's an attestation primitive that **other** gates (the done-transition guard, the criteria_unmet check) consume.

---

## 2. `preflight_attest` MCP tool

Tool is exposed by `crawfish-orgctl` (see [`org-contract.md`](./org-contract.md) §6):

```jsonc
// Args
{
  "org_id":       "01hxz...",                  // ULID
  "task_id":      "01j...",                    // ULID
  "criterion_id": "spec-reviewed",             // matches task.criteria[*].id; required
  "by":           "founder",                   // member id of the attesting agent
  "statement":    "Read docs/specs/org-contract.md §3.1 and confirmed the contributor-rewrite path covers this case.",
  "payload": {                                 // OPTIONAL — kind-specific evidence detail
    "kind":   "preflight",
    "sources": ["docs/specs/org-contract.md#§3.1"],
    "tool_calls": ["org_fs_read"],
    "note": "verified the assignee_locked path is rejected, not auto-appended"
  }
}

// Returns
{
  "tokens_used": 0,                            // attestation is metadata, not an LLM call
  "event_id":    "01k..."                      // ULID of the appended preflight_attested event
}
```

**Server behaviour** (in `crawfish-lens` — `preflight_attest` is implemented in lens, NOT in orgctl; orgctl is a thin RPC):

1. Validate `by` against `org.json` (must exist, must be an agent — humans don't preflight).
2. Validate `task_id` exists and `criterion_id` is in `task.criteria[*].id`. Unknown → `404 unknown_criterion`.
3. Validate `statement.length >= 16`. Empty/short statements → `400 invalid_statement`.
4. Append a `preflight_attested` event to `board.jsonl`:

```jsonc
{
  "type":         "preflight_attested",
  "ts":           "2026-05-20T14:22:00Z",
  "event_id":     "01k...",
  "task_id":      "01j...",
  "criterion_id": "spec-reviewed",
  "by":           "founder",
  "statement":    "...",
  "payload":      { /* echoed from the request, or empty {} */ }
}
```

5. **Auto-set criterion evidence** when the criterion's `kind === "preflight"`. The fold projects `{ kind: "preflight", payload: { event_id, by, at: ts } }` into `evidence`. For non-preflight criteria the attestation is recorded but `evidence` is NOT auto-set — a human or another tool sets evidence explicitly via `criteria_attest`.

6. Project a `preflight_attested` activity entry into the task's `activity_log` (ActivityKind extended below).

---

## 3. BoardEvent + ActivityKind extensions

Append to the `BoardEvent` union in `org-contract.md` §3 (NOW-W2):

```ts
| {
    type: "preflight_attested";
    ts: string;
    event_id: string;
    task_id: string;
    criterion_id: string;
    by: string;             // agent member id
    statement: string;      // min 16 chars
    payload: Record<string, unknown>;
  }
```

Append to `ActivityKind`: `"preflight_attested"`. Projected entries carry the same `payload` as the source event plus `{ criterion_id, statement }` (the body of the statement is searchable from the activity feed).

---

## 4. Context-injection wrapper (orgctl side)

`crawfish-orgctl/src/preflight.ts` is a **thin wrapper** that:

- Exposes the `preflight_attest` MCP tool definition.
- Forwards calls to `POST /api/orgs/:org_id/preflight` on the lens server.
- Adds **context to the prompt** that the calling agent sees — the wrapper's tool description includes the current task's `criteria[*]` so the agent can pick the right `criterion_id`. The exact wording:

> *"Use `preflight_attest` to record that you have read the relevant spec, verified the test fixture, or otherwise completed the preparatory work for a criterion BEFORE you take the action that would satisfy it. Pass `criterion_id` from the task's `criteria` list. Statements must describe what you actually checked, in ≥16 characters. Do NOT preflight without doing the work — the activity log is auditable."*

The wrapper does NOT call the LLM, does NOT cache, does NOT retry on a `409`. Token-cost is the network round-trip only; `tokens_used: 0` is honest.

---

## 5. REST surface (lens)

Mounted in `crawfish-lens/src/server/index.ts` (lead-only edit):

| Method | Path | Body | Returns |
|---|---|---|---|
| `POST` | `/api/orgs/:org_id/preflight` | `{ task_id, criterion_id, by, statement, payload? }` | `200 { event_id }` / errors per §2 |

`POST` is idempotent on a `(task_id, criterion_id, by)` triple within a 5-minute window — repeated calls return the prior `event_id` instead of appending a duplicate. After 5 minutes a re-attestation is allowed (the criterion may have changed kind).

---

## 6. Dash rendering

The drawer's criteria panel renders one row per criterion. A criterion with `evidence` is shown checked; the row links to the originating preflight event (if `evidence.kind === "preflight"`) which expands to show `statement + payload + at + by`.

The activity panel (NOW-W1) already lists `preflight_attested` entries; no additional dash work is required beyond the criterion row treatment.

---

## 7. Out of scope (deferred)

- **Cross-task preflight (reading an unrelated spec for general context).** v1 ties each preflight to a specific task criterion.
- **Quality scoring of statements.** An LLM judge that flags "I read the doc" as low-effort vs "I read §3.1 and confirmed X" is deferred to LATER².
- **Multi-criterion preflight in one call.** Per-criterion calls keep the event log clean.

---

*Owners:* lead writes this file; `preflight-orgctl` teammate reads it and codes the wrapper. Changes after fanout require re-coordination via `SendMessage`.
