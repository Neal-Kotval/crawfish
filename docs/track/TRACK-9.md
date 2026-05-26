# TRACK-9 — PR-comment loop (auto-respond with budget)

**Components:** `PLAT` (primary) · `DASH` (the per-repo mode toggle, §9.2)
**Source:** ORCHESTRATOR-USER-STORIES.md §9 · ROADMAP O-stages O4.1–O4.8

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the post-submission revision loop. After a PR is opened (TRACK-8), a reviewer leaves
feedback. When they `@`-mention `@crawfish-bot`, the craw re-engages, reads the comment,
revises the PR, and posts a reply — then waits for the next mention. It is the **only** surface
where a craw acts on free-form human language rather than a structured ticket, which is exactly
why the safety envelope around it is the point of the track.

That envelope has three parts. First, a **bounded loop**: the craw will make at most N revisions
*or* spend at most $M of tokens per PR, whichever comes first (defaults: 5 revisions, $10), then
it halts and notifies. Second, a **conflict detector**: if two reviewers ask for opposite things,
the craw must halt and ping a human rather than guess which reviewer to follow. Third, an
**honest fallback**: when a comment is out-of-scope, needs an architecture decision, or is
genuinely ambiguous, the craw replies "I can't address this without X" and stops — it never
silently gives up. Every revision is audited.

The loop's spend is not free money. The token cap reads the same `budget.ts` model the
originating task used (TRACK-5), so comment churn cannot be used to bypass the per-org daily cap
(TRACK-12). And the `@crawfish-bot halt` veto must stop the craw mid-loop within 30 seconds —
the same fast-cancel guarantee as the gate-2 reject (TRACK-8 §8.7), sharing one halt-state
machine.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Mention re-engage + halt veto (§9.1, §9.8) | `PLAT` | `cloud/server/src/orchestrator/pr-bot/listener.ts` (O4.1) |
| Comment-resolution state machine (§9.3) | `PLAT` | `cloud/server/src/orchestrator/pr-bot/state-machine.ts` (O4.2) |
| Per-PR revision + token cap (§9.4) | `PLAT` | `state-machine.ts` (O4.3, shared with O4.2) |
| Conflict-with-reviewer detector (§9.5) | `PLAT` | `cloud/server/src/orchestrator/pr-bot/conflict-detector.ts` (O4.4) |
| Out-of-scope detector (§9.6) | `PLAT` | `cloud/server/src/orchestrator/pr-bot/scope-detector.ts` (O4.5) |
| Auto-respond mode toggle (§9.2) | `PLAT` + `DASH` | mode persisted in `cloud/server`; toggle UI in dashboard (O4.6) |
| Bot reply templates (§9.3, §9.6) | `PLAT` | `cloud/server/src/orchestrator/pr-bot/templates.ts` (O4.7) |
| Audit trail per revision (§9.7) | `PLAT` | reuses JSONL audit substrate (O4.8) |

---

## User stories

Tags are now **components** (where it gets built), not personas.

9.1 **[PLAT]** When I @-mention `@crawfish-bot` in a PR comment, the craw re-engages to address my feedback. *AC: mention-only is the default mode; bot doesn't react to unmentioned comments.*

9.2 **[PLAT, DASH]** Configure auto-respond mode per repo: `mention-only`, `respond-to-all`, or `off`. *AC: mode is per repo, not per workspace; defaults to mention-only.*

9.3 **[PLAT]** When the bot re-engages, it posts a "working on it" reply with an estimated cost and ETA. *AC: estimated cost is based on the craw's historical revision cost.*

9.4 **[PLAT]** Cap the auto-respond loop per PR: max N revisions OR max $M tokens, whichever first; on cap, the bot halts and notifies. *AC: caps editable per repo; defaults: 5 revisions, $10; halt notification uses §13 channels.*

9.5 **[PLAT]** When the bot detects conflicting feedback across two reviewers, it halts and pings a human instead of guessing which to follow. *AC: detection is a heuristic (semantic similarity check + reviewer count); false negatives are OK; false positives waste tokens.*

9.6 **[PLAT]** When the bot can't address a comment (out-of-scope, requires architecture decision, ambiguous), it replies with an honest "I can't address this without X" and stops. *AC: explicit fallback path; the bot does not silently give up.*

9.7 **[PLAT]** Audit log entry for every bot revision: who asked for it, what was changed, tokens spent. *AC: same audit surface as §14.*

9.8 **[PLAT]** I can "veto" the bot mid-loop with a comment like `@crawfish-bot halt` and the bot stops within 30s. *AC: keyword commands documented and stable.*

---

## Coding tasks, by component

### PLAT — `cloud/server`

- **O4.1** — Bot identity + mention listener (`cloud/server/src/orchestrator/pr-bot/listener.ts`). Implements §9.1 (re-engage on `@crawfish-bot` mention) and §9.8 (`@crawfish-bot halt` veto, stop <30s). The listener filters incoming comment webhooks on bot identity; in `mention-only` mode it ignores any comment that doesn't `@`-mention the bot. It also watches for the stable keyword commands so a `halt` is recognized even mid-revision.

  ```ts
  // cloud/server/src/orchestrator/pr-bot/listener.ts
  function onComment(c: PrComment, mode: RepoMode) {
    if (parseHaltCommand(c.body)) return signalHalt(c.prId);   // §9.8 — fast path, always honored
    if (mode === "off") return;
    if (mode === "mention-only" && !mentionsBot(c.body)) return; // §9.1 default
    enqueueRevision(c);
  }
  ```

- **O4.2** — Comment-resolution state machine (`cloud/server/src/orchestrator/pr-bot/state-machine.ts`). Drives the `re-engage → revise → post` cycle and the §9.3 "working on it" reply. Critically, it checks the halt signal **between revision steps**, not only at cycle boundaries, so a veto lands within 30s even if a revision is in flight.

- **O4.3** — Per-PR revision + token cap (defaults: 5 revisions, $10), shared with O4.2. Implements §9.4. See Concepts for the exact "whichever first" check.

- **O4.4** — Conflict-with-reviewer detector (`cloud/server/src/orchestrator/pr-bot/conflict-detector.ts`). Implements §9.5: a semantic-similarity-plus-reviewer-count heuristic that halts and pings a human. Tune toward **under-flagging** — false negatives are acceptable, false positives waste tokens (Concepts).

- **O4.5** — Out-of-scope detector (`cloud/server/src/orchestrator/pr-bot/scope-detector.ts`). Implements §9.6: classifies a comment as out-of-scope / needs-architecture-decision / ambiguous and triggers the honest "I can't address this without X" reply rather than a silent stop.

- **O4.7** — Bot reply templates (`cloud/server/src/orchestrator/pr-bot/templates.ts`). Backs the §9.3 and §9.6 reply shapes. Must include a **no-data variant** of the "working on it" reply: a brand-new craw has no historical revision cost, so the cost/ETA estimate is unavailable and the template must degrade gracefully rather than print `$NaN`.

- **O4.8** — Audit trail per revision (reuses the existing JSONL audit substrate). Implements §9.7 (who asked, what changed, tokens spent). This trail and the §8 merge events must share one log so a PR's full lifecycle — plan → execute → CI → merge → comment-revisions — is reconstructable from a single source.

  **Reuses (already shipped — do not rebuild):**
  - JSONL audit substrate — the §9.7 record format; write to the same trail TRACK-14 (§14, O5.3) reads.
  - `budget.ts` token model (TRACK-5 §5.6) — the §9.4 token cap reads this; comment-loop spend counts against the originating task's envelope.
  - `stats.ts` per-craw stats engine (TRACK-10) — the §9.3 historical revision cost reads from here.

### DASH — `desktop/dash`

- **O4.6** — Auto-respond mode toggle (`mention-only` / `respond-to-all` / `off`). Implements §9.2. The setting is **per repo, not per workspace**, and defaults to `mention-only`. The toggle UI lives in the dashboard; the value is persisted server-side in `cloud/server` and read by the O4.1 listener. `respond-to-all` materially raises token spend, so the §9.4 cap is the backstop that makes it safe to offer.

  Cross-references: §9.4's halt notification uses §13 channels (O6.4, TRACK-13); §9.7's audit shares the §14 surface (O5.3, TRACK-14). Both are cross-surface dependencies, owned elsewhere — not re-implemented here.

---

## Key technical concepts, explained

**The bounded revision/token cap (§9.4) — "5 revisions OR $10, whichever first."** The loop has
two independent ceilings and trips on the first one reached. This prevents both runaway iteration
count *and* runaway spend (a single revision on a huge diff can be expensive). The token cost is
charged against the **same** `budget.ts` envelope the originating task used, so a reviewer can't
drain the per-org daily cap (TRACK-12) by re-mentioning the bot a hundred times:

```ts
function capTripped(loop: LoopState, repo: RepoCaps): boolean {
  return loop.revisions >= repo.maxRevisions      // default 5
      || loop.tokensSpentUsd >= repo.maxTokenUsd;  // default $10 — whichever first
}
// on trip: halt, then notify via §13 channels (O6.4 / TRACK-13)
```

**The conflict detector's asymmetric error budget (§9.5).** Most classifiers optimize precision and
recall together. This one deliberately does not. A **false negative** (missing a real conflict and
revising anyway) is acceptable — the worst case is a wasted revision the next reviewer corrects. A
**false positive** (halting on feedback that wasn't actually conflicting) burns the loop and pings a
human for nothing. So the threshold is tuned to *under-flag*: only halt when the signal is strong.
Encode that bias in the default threshold, not just in a comment:

```ts
// high threshold => only flags clear, strong conflicts (favor false negatives over false positives)
const CONFLICT_SIMILARITY_FLOOR = 0.85;
function isConflict(a: string, b: string, reviewerCount: number): boolean {
  if (reviewerCount < 2) return false;                  // can't conflict with yourself
  return semanticOpposition(a, b) >= CONFLICT_SIMILARITY_FLOOR;
}
```

**The veto must stop within 30s, checked between steps (§9.8).** A halt signal that is only read at
cycle boundaries could leave the craw running for the length of a whole revision. The state machine
must poll the halt flag **between** revision steps, so a `@crawfish-bot halt` typed mid-revision is
honored within the 30s budget. This is the same fast-cancel guarantee as TRACK-5 §5.3 and shares the
halt-state machine with TRACK-8 §8.7. Because reviewers type the keyword commands by hand, the
command syntax must be documented and stable — no renaming `halt` to `stop` in a later release.

---

## Gaps — work with no O-stage assigned

The §9 stories all map to O4.1–O4.8; the gaps here are unresolved decisions, not missing deliverables.

- **§9.4 budget continuation vs. fresh budget.** The cap reads `budget.ts`, but the spec doesn't say whether comment-loop spend is a *fresh* per-PR budget or a *continuation* of the originating task's budget. *What's needed:* a single answer, because it decides whether the per-org daily cap (TRACK-12) can be bypassed by comment churn. Continuation is the safer default.

---

## Open questions

- **§9.4 spend accounting:** is comment-loop spend a fresh budget or a continuation of the task budget? This is the one decision that governs whether the loop is a daily-cap bypass.
- **§9.3 no-history estimate:** confirm the no-data reply variant's exact copy — does it omit cost/ETA entirely, or show a coarse default? A wrong-looking `$0.00` estimate is worse than none.
