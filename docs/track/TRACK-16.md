# TRACK-16 — Integrations & edge cases

**Components:** `OPS` (the only deliverables the canonical map assigns) · `PLAT` (where the real engineering lives, mostly unmapped)
**Source:** ORCHESTRATOR-USER-STORIES.md §16 · ROADMAP.md O-stages O5.7, O6.5, O6.6, O6.7, O6.8 (operational) — engineering O-stages O0.1/O0.2, O3.8, O5.1 referenced but not assigned to §16

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).
> - **OPS** — operational/docs work (runbooks, status page, on-call, published reference docs). Not a code submodule; the deliverable is a written artifact or a process, not a build target.

---

## What this surface is

This is the resilience-and-lifecycle edge of the product: the failure-mode contracts a paying customer
needs to trust an autonomous system. Six stories — emergency GitHub-App bypass, direct-push conflict
detection, GitHub-outage backoff-and-resume, LLM-provider-outage halt-and-resume, cross-tracker
migration without losing history, and subscription cancellation with a 90-day export-then-delete
contract. Most are *contracts* ("the system degrades gracefully") rather than features.

**This file has the weakest 1:1 O-stage mapping in the whole track set, and the mismatch is
structural — read this section before the task tables below.** The canonical ROADMAP map assigns §16
exactly five deliverables: O5.7 (invite polish) and O6.5–O6.8 (runbooks, status page, on-call,
feedback channel). **Every one of those is operational/support work — tagged `OPS` — not the
engineering that satisfies the stories.** The actual engineering behind §16.1–§16.6 either lives in
other O-stages owned by other tracks (O3.8 in TRACK-11; the durable engine O0.1/O0.2 in TRACK-5) or
**is not mapped to any O-stage at all** (§16.1, §16.5, §16.6).

So the component picture is: `OPS` owns the deliverables the map names; `PLAT` owns the real
engineering, two pieces of it borrowed from other tracks and three pieces unbuilt. The Gaps section
below is the headline of this file, not a footnote — do not read the OPS deliverables as covering the
stories.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| GitHub-App emergency disable (§16.1) | `PLAT` | **unmapped — see Gaps** (connection-state flag, config-preserving) |
| Direct-push conflict halt (§16.2) | `PLAT` | O3.8 push-watcher, conflict variant (owned by TRACK-11) |
| GitHub outage backoff + resume (§16.3) | `PLAT` | durable workflow engine (O0.1 ADR-002 / O0.2, TRACK-5) |
| LLM-provider outage halt + resume (§16.4) | `PLAT` | durable workflow engine (O0.1 / O0.2, TRACK-5) |
| Cross-tracker migration (§16.5) | `PLAT` | **unmapped — see Gaps** (needs tracker-agnostic ticket identity) |
| Cancellation + 90-day export/delete (§16.6) | `PLAT` | **unmapped — see Gaps** (O5.1 billing handles cancel only) |
| Support runbooks / status / on-call / feedback | `OPS` | O6.5–O6.8 (docs + process) |
| Invite flow polish | `PLAT` | O5.7 (the multi-user lifecycle these admin actions sit in) |

---

## User stories

Tags are now **components** (where it gets built), not personas.

16.1 **[PLAT]** Bypass the orchestrator for emergency: temporarily disable the GitHub App on a repo without losing config. *AC: re-enable restores config; no data loss.*

16.2 **[PLAT]** If I push directly to a craw's branch while it's working, the orchestrator detects the conflict and halts. *AC: halt posts a comment explaining; ticket returns to backlog with a "human-took-over" label.*

16.3 **[PLAT]** If GitHub goes down or rate-limits us, queued tasks pause and resume automatically when GitHub recovers. *AC: orchestrator backs off exponentially; no false failures attributed to the craw.*

16.4 **[PLAT]** If a connected LLM provider has an outage, the task halts gracefully (saves state) and resumes when the provider recovers. *AC: durable workflow engine handles this natively (rationale for the §1.2 ADR in the stages doc).*

16.5 **[PLAT]** Migrate from GitHub Issues to Linear (or vice versa) without losing historical craw activity. *AC: cross-tracker links preserved; reports stitch across both.*

16.6 **[PLAT]** Cancel my subscription; data exports for 90 days post-cancel; then deletion. *AC: standard SaaS deletion contract; exportable formats; explicit deletion confirmation.*

---

## Coding tasks, by component

### Operational / docs — `OPS`

These are the only deliverables the canonical map assigns to §16. They make the failure-mode contracts
*credible* to a paying customer during closed beta, but they do not *implement* the stories.

- **O6.5** — Support runbooks (`docs/orchestrator/support/{onboarding,common-failures,billing-questions}.md`). Written procedures for the edge cases below — what on-call does when a craw halts, when GitHub rate-limits, when a customer asks to cancel. Documentation, not code.
- **O6.6** — Status page (hosted, statuspage.io or equivalent). Surfaces the GitHub/LLM-provider outages of §16.3/§16.4 to customers so an outage reads as "GitHub is down" rather than "the craw broke." A hosted page + integration, not a build target in this repo.
- **O6.7** — First-line on-call rotation (internal — 1 engineer/week for a 10–20-customer fleet). The human side of outage and edge-case handling. A process and a schedule, not code.
- **O6.8** — Customer feedback channel (shared Linear/Slack per design partner). Where edge-case reports land during beta. A channel setup, not code.

### PLAT — `cloud/server` + `cloud/platform`

Engineering that actually satisfies the stories. Two pieces are owned by other tracks; three are
unmapped (see Gaps).

- **O5.7** — Invite flow polish (existing `cloud/server` Invite model + new UI). Supports the multi-user lifecycle the admin actions in this surface sit within. The map's one PLAT engineering deliverable for §16, and it is tangential to §16.1–§16.6.
- **O3.8 (borrowed from TRACK-11)** — Push-watcher, conflict variant. Implements §16.2. The same watcher that powers deliberate manual-takeover (TRACK-11 §11.3) detects the *unexpected* direct push and halts: posts an explanatory comment, returns the ticket to backlog, applies the `human-took-over` label. One watcher, two outcomes keyed on run state.
- **O0.1 / O0.2 durable workflow engine (from TRACK-5)** — Implements §16.3 and §16.4. A task pauses on an external outage (GitHub down/rate-limited; LLM provider down), saves state, and resumes on recovery with no false failure and no duplicate side-effect. §16.4's AC names this as the rationale for ADR-002. Exponential backoff (§16.3) is engine-level retry policy, not per-craw code (see concepts below).

**Reuses (already shipped — do not rebuild):**
- `Invite` model (`PLAT`) — O5.7 polishes the existing model, does not introduce a new one.
- The Linear adapter (`CLI`, O1.1) and the GitHub mirror (`github-issues.ts`) — both exist; §16.5 migration needs link-stitching *on top of* them, which is the unbuilt part.
- Billing subscription cancel (`PLAT`, O5.1) — handles the cancel itself; the 90-day export + deletion contract on top is unbuilt (§16.6).

---

## Key technical concepts, explained

**Durable engine: pause-on-outage, resume-on-recovery — the strongest argument for ADR-002 (§16.3,
§16.4).** A non-durable worker that loses GitHub mid-task has two bad options: fail the task (a false
failure attributed to the craw) or retry blindly (a duplicate PR). A durable engine persists task
state at each step, so an outage suspends the task and recovery resumes it from the last completed
step. §16.4's AC says this explicitly: "durable workflow engine handles this natively (rationale for
the §1.2 ADR)." Exponential backoff is the engine's retry policy, applied uniformly — not something
each craw reimplements:

```ts
// Engine-level retry: back off exponentially, resume rather than restart.
async function withBackoff<T>(step: () => Promise<T>, max = 6): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try { return await step(); }
    catch (e) {
      if (!isTransient(e) || attempt >= max) throw e;   // real error → fail honestly
      const delay = Math.min(1000 * 2 ** attempt, 60_000); // 1s,2s,4s,...capped at 60s
      await sleep(delay + jitter());                       // jitter avoids thundering herd
      // on resume, the engine replays from the last persisted step — no duplicate side-effect
    }
  }
}
```

**One push-watcher, two outcomes: graceful takeover vs. conflict halt (§16.2).** The watcher that
detects a human pushing to a craw's branch serves both TRACK-11 §11.3 (a *deliberate* handoff: the
orchestrator exits cleanly and links the human's PR) and §16.2 (an *unexpected* mid-run conflict: halt,
post a comment, return the ticket to backlog with a `human-took-over` label). The distinction is intent,
inferred from run state — was the craw idle/handed-off, or actively working when the push arrived. Build
one watcher and branch on state; do not build two.

**Tracker-agnostic ticket identity: store both GitHub and Linear refs (§16.5).** If the run record keys
historical craw activity on a single tracker's ticket id, then migrating GitHub Issues ↔ Linear orphans
that history — the new tracker's ids do not match the old ones. The fix is a data-model decision that
must land *before* O1 inbound adapters lock their schema, not be retrofitted: every run record carries a
tracker-agnostic identity holding both references.

```ts
// Run record stores both tracker refs so migration stitches, not orphans.
type TicketIdentity = {
  canonicalId: string;                 // internal, stable across migrations
  github?: { repo: string; number: number };
  linear?: { teamId: string; issueId: string };
};
// On migration, attach the new tracker's ref to the same canonicalId; reports
// query by canonicalId and stitch across both source systems.
```

---

## Gaps — work with no O-stage assigned

**This is the headline section of TRACK-16.** The canonical map assigns only the `OPS` deliverables
(O5.7, O6.5–O6.8). The engineering behind the stories is partly borrowed from other tracks (§16.2 →
O3.8; §16.3/§16.4 → durable engine O0.1/O0.2) and partly **unmapped to any O-stage**. The three
unmapped pieces below need engineering O-stages assigned by the lead.

- **§16.1 GitHub-App emergency disable (config-preserving).** No numbered deliverable. The closest
  existing thing is the kill switch (O5.9, TRACK-14), but that pauses *craw activity* — it does not
  disable the *GitHub App connection*, which is what stops webhooks entirely. *What's needed:* a
  connection-state **flag** on the integration record (disabled vs. enabled) that suspends webhooks
  without tearing down the integration, so re-enable restores config with no data loss. It is a flag,
  not a teardown — the config must survive the disable. Assign an O-stage.

- **§16.5 cross-tracker migration (GitHub Issues ↔ Linear, history-preserving).** No numbered
  deliverable. The Linear adapter (O1.1) and the GitHub mirror (`github-issues.ts`) exist, but
  bidirectional migration that preserves cross-tracker links and stitches reports across both systems
  is unbuilt. *What's needed:* the tracker-agnostic `TicketIdentity` above (a schema decision due
  before O1 locks), plus a migration job that re-attaches the new tracker's refs to existing
  `canonicalId`s. Assign an O-stage and decide the schema *now*, not after O1.

- **§16.6 cancellation + 90-day export-then-delete.** No numbered deliverable. Billing (O5.1) handles
  the subscription cancel, but the data-export-then-deletion contract is unbuilt. *What's needed:* an
  export pipeline (exportable formats, intersecting TRACK-10 §10.6 CSV), a 90-day post-cancel hold,
  then a deletion step gated on explicit confirmation. The 90-day window here is a *different clock*
  from the §14.2 audit-retention 90-day default (TRACK-14) — they coincide numerically; keep them
  decoupled. Assign an O-stage.

---

## Open questions

- **§16.1 disable scope:** is the GitHub-App disable per-repo or per-workspace? The story says "on a
  repo," but the App is installed per-repo *and* per-org — confirm the flag granularity before
  building, since a per-repo flag and a per-org flag are different records.
- **§16.5 migration directionality:** does migration need to be reversible (Linear → GitHub *and*
  back), or one-shot? Reversibility raises the bar on the identity model — both refs must stay live,
  not just the destination's.
- **§16.6 vs §14.2 clocks:** confirm the post-cancel 90-day export window and the audit-retention
  90-day default are implemented as independent timers. Coupling them would let a retention purge
  delete data a cancelled customer is still entitled to export.
- **§16.3/§16.4 scope ownership:** the durable engine is owned by TRACK-5 (O0.1/O0.2). Confirm whether
  §16.3/§16.4 are considered *delivered* once the engine ships, or whether they need §16-specific
  acceptance tests (outage injection, resume verification) owned here.
