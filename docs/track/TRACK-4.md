# TRACK-4 — Plan checkpoint (gate 1)

**Components:** `PLAT` (primary — the checkpoint workflow) · `PLAT` + `DASH` (the escalation policy + SLA UI)
**Source:** ORCHESTRATOR-USER-STORIES.md §4 · ROADMAP.md O-stages O1.3, O6.2

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the first human gate. Before a craw writes a single line of code, it posts its **proposed plan** as a comment on the ticket — what files it will change, which tests it will run, the expected diff size, the estimated token cost — and then *waits*. A human approves, rejects with a reason, or edits the plan and re-approves. The workspace can auto-approve certain labels (a `dep-bump` plan is mechanical enough to skip the gate) and a workspace-wide policy backstops everything, with the craw able to flag its own plan as risky to force human review regardless.

In the request lifecycle it sits between classification (TRACK-3) and execution (TRACK-5): nothing executes until this gate clears. The §3.4 "Craw will attempt this" comment with its decline button is the front edge of this same gate — TRACK-3 surfaces the eligibility decision, but the decline-before-any-code guarantee is implemented here.

The work is almost entirely **PLAT**. The checkpoint itself is a durable workflow in `cloud/server`. The one **PLAT + DASH** piece is the escalation policy and SLA configuration UI (O6.2), which renders in both `cloud/platform` and `desktop/dash`.

This is the canonical case for a durable workflow engine: the gate must survive a worker crash without re-posting the plan comment or re-prompting for approval. A naive polling loop would double-fire side-effects on restart and corrupt the gate.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Post plan, await approval (§4.1) | `PLAT` | `cloud/server/src/orchestrator/checkpoints/plan.ts` (O1.3) |
| Approve via reaction or button (§4.2) | `PLAT` | O1.3 — two event sources, one workflow signal |
| Reject with reason (§4.3) | `PLAT` | O1.3 |
| Edit-and-re-approve (§4.4) | `PLAT` | O1.3 — plan versioning, original archived |
| Per-label auto-approval (§4.5) | `PLAT` | O1.3 |
| Workspace policy + risky override (§4.6) | `PLAT` + `DASH` | O6.2 escalation policy + UI |
| SLA notification + escalation (§4.7) | `PLAT` + `DASH` | O6.2 (timer + chain); delivery is **O6.4**, TRACK-13 |

---

## User stories

Tags are now **components** (where it gets built), not personas.

4.1 **[PLAT]** Before any code is written, the orchestrator posts the craw's proposed plan as a comment on the ticket and waits for human approval. *AC: plan is a markdown comment with: what files will change, which tests will run, expected diff size, estimated token cost; status changes to "awaiting plan approval."*

4.2 **[PLAT]** Approve the plan with a single emoji/reaction or a click in the dashboard. *AC: 👍 reaction in Linear or the "approve" button in the dashboard both work; logged with actor.*

4.3 **[PLAT]** Reject the plan with a one-line reason; the craw halts and the ticket returns to the backlog. *AC: rejection reason posted as a comment; ticket re-classifiable on next pass.*

4.4 **[PLAT]** Edit the plan inline (e.g., "also touch `src/billing.ts`") and re-approve. *AC: craw re-runs against the edited plan; original plan archived.*

4.5 **[PLAT]** Configure auto-approval for specific labels (e.g., `dep-bump` auto-approves the plan because the action is mechanical). *AC: auto-approval logs an "auto-approved" event; reviewer still has the merge gate.*

4.6 **[PLAT, DASH]** Set a workspace-wide policy: "all plans require human approval" OR "plans auto-approve unless flagged risky." *AC: a craw can flag its own plan as risky (large diff, sensitive file path); risky always requires human review regardless of policy.*

4.7 **[PLAT, DASH]** Receive an in-app + email notification when a plan is awaiting my approval for more than the SLA window (default 4h). *AC: SLA configurable per workspace; escalation to backup reviewer after a second timeout.*

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O1.3** — Plan checkpoint workflow, gate 1 (`cloud/server/src/orchestrator/checkpoints/plan.ts`). Implements §4.1–§4.5: post the plan comment, set status to "awaiting plan approval," durably await a resolution, and handle approve / reject / edit-and-re-approve plus per-label auto-approval. The checkpoint is a **durable wait**, not a polling loop — it suspends until a signal arrives and resumes exactly where it left off after a restart.

  ```ts
  // checkpoints/plan.ts — durable wait, idempotent side-effect, dual signal source
  await postPlanComment(ticket, plan);          // idempotency-keyed (see concepts)
  await setStatus(ticket, "awaiting plan approval");

  if (autoApprovedByLabel(ticket, workspace) && !plan.risk.isRisky) {
    await logEvent(ticket, { type: "auto-approved" }); // §4.5 — still leaves merge gate
    return { approved: true };
  }
  const signal = await workflow.waitForSignal("plan-resolution"); // survives crash
  // signal arrives from Linear 👍 OR dashboard button — first one wins (§4.2)
  ```

- **O6.2** — Escalation policy + UI, fallback reviewer chain (dashboard). Implements §4.6's workspace-wide policy ("all plans require approval" vs. "auto-approve unless risky," with risky always forcing human review) and §4.7's SLA timer that escalates to a backup reviewer after a second timeout. **PLAT + DASH**: the policy store and the durable SLA timer are server-side; the configuration UI renders in both `cloud/platform` and `desktop/dash`.

**Cross-references / scope notes:**
- §4.7 notification *delivery* (in-app + email) is **O6.4** (TRACK-13). O6.2 owns the escalation chain and the SLA timer; O6.4 owns the channel. Both are required for §4.7. The canonical map lists only O1.3 + O6.2 for this surface — flagging that §4.7 depends on TRACK-13's O6.4.
- §4.4 "original plan archived" implies plan versioning inside `plan.ts`; **not separately numbered**. The archived plan must be reachable from the audit log (TRACK-14) so an edited-then-approved plan has a continuous trail. See Gaps.

---

## Key technical concepts, explained

**Durable workflow wait (§4.1, ADR-002 pending).** The gate can stay open for hours. If the worker process restarts mid-wait, two things must not happen: the plan comment must not re-post, and the approval prompt must not re-fire. A durable workflow engine persists the workflow's position and any completed side-effects, so on restart it resumes *after* the comment was posted rather than re-running it. The checkpoint suspends on a signal; it does not busy-poll.

```ts
// Naive (WRONG): a loop re-posts the comment after every restart.
while (!approved) { await postPlanComment(...); await sleep(60_000); } // double-fires

// Durable (RIGHT): post once (recorded as completed), then suspend until signalled.
await step.run("post-plan", () => postPlanComment(ticket, plan)); // replay-safe
const res = await step.waitForSignal("plan-resolution", { timeout: "4h" });
```

**Idempotency key on a comment side-effect (§4.1, §4.2).** Posting the plan comment and recording the approval both touch external systems (Linear / GitHub). On retry or on the §4.2 race (a Linear 👍 and a dashboard click arriving near-simultaneously), the effect must apply once. Key the comment on `(ticketId, planVersion)` and resolve the gate on first-resolution-wins, recording the actor either way.

```ts
// One plan comment per plan version; one gate resolution, first writer wins.
await db.planComment.upsert({
  where: { ticketId_planVersion: { ticketId, planVersion } },
  create: { ticketId, planVersion, externalId: await postComment() },
  update: {}, // retry → no duplicate comment
});

const won = await db.planResolution.create({          // unique on ticketId+planVersion
  data: { ticketId, planVersion, actor, decision },
}).catch(() => null);                                 // second signal loses the race
if (!won) return;                                     // already resolved → ignore
```

**Structured risk verdict (§4.6).** The craw self-flagging a plan as "risky" must override the auto-approve policy — but the policy engine cannot read prose. The plan output carries a structured verdict (a field, not free text) so the engine evaluates it deterministically. Sensitive-path detection here overlaps the file-path allow/deny lists (TRACK-14, O2.8), and the §4.1 estimated token cost should come from the same cost model (`budget.ts`, CLI) that the §5.6 per-task budget cap enforces — so a plan can't promise a cost the cap will then breach mid-run (TRACK-5).

```ts
// Plan carries a structured risk verdict the policy engine reads as a field.
type RiskVerdict = {
  isRisky: boolean;
  reasons: ("large-diff" | "sensitive-path" | "egress")[];
  estimatedTokens: number; // same budget.ts cost model the §5.6 cap enforces
};
// §4.6: risky always requires human review, regardless of the auto-approve policy.
const requiresHuman = policy === "all" || plan.risk.isRisky;
```

Note also that §4.5 auto-approving the *plan* must not auto-approve the *merge* (TRACK-8 gate 2). The two gates are independent — keep their states orthogonal in the workflow so an auto-approved plan still stops at the merge gate.

---

## Gaps — work with no O-stage assigned

These stories have acceptance criteria but **no numbered O0–O7 deliverable.** Flag for the lead.

- **§4.4 plan versioning / archive.** Not separately numbered; it rides inside O1.3's `plan.ts`. The AC requires the original plan to be archived when edited, and the archive must be reachable from the audit log (TRACK-14) so an edited-then-approved plan has a continuous trail. *What's needed:* confirm `plan.ts` stores plan versions and that the archive is wired to the audit substrate, or number it separately for test coverage.
- **§4.7 notification delivery.** O6.2 owns the SLA timer and escalation chain but **not** the channel — in-app + email delivery is O6.4 (TRACK-13). The canonical map lists only O1.3 + O6.2 for this surface, so §4.7's delivery dependency on O6.4 is implicit. *What's needed:* make the O6.4 dependency explicit in the phase plan so §4.7 isn't marked done when only the timer ships.

---

## Open questions

- **§4.7 SLA wall-clock vs. business hours:** does the 4h SLA pause overnight / off-hours, or run wall-clock? Not specified. Affects escalation noise — a wall-clock timer fires at 2am and escalates to a backup who is also asleep.
- **§4.7 timer durability + clean cancel:** the SLA timer must be durable (survives restart) *and* cancel cleanly on approval, or a late approve still triggers a phantom escalation. Confirm the timer is part of the durable workflow (O1.3 / ADR-002), not an in-memory `setTimeout`.
- **§4.6 sensitive-path source of truth:** the risk verdict's sensitive-path detection overlaps TRACK-14's file-path allow/deny (O2.8). Confirm both read one path-policy definition rather than each maintaining its own list.
