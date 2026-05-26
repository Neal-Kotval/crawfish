# TRACK-8 — PR submission & merge checkpoint (gate 2)

**Components:** `PLAT` (primary) · `CLI` (the shipped GitHub-issues mirror it reuses)
**Source:** ORCHESTRATOR-USER-STORIES.md §8 · ROADMAP O-stage O1.4

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the second human gate. A craw has already planned the work (gate 1, TRACK-4),
executed it, and pushed a draft PR that CI then verified (TRACK-7). Gate 2 is the moment
that draft becomes a real, reviewable PR and — once a human approves it under policy — gets
merged, with the originating ticket closed automatically. A merge here is the terminal success
state of the entire loop: ticket in, PR out, ticket closed.

The hard design constraint is **zero Crawfish-specific review UI**. The craw's PR is reviewed
in GitHub exactly as a human's would be — same diff view, same approve button, same branch
protection. The orchestrator's job is to make the PR *structurally normal* (a clean,
templated description) and to layer one extra rule on top of GitHub's: an N-approver policy
for craw-authored PRs. Nothing about the review experience should be new to the reviewer.

The reject path matters as much as the merge path. When an IC rejects the PR, the craw must
**stop re-engaging** — it does not argue, it does not retry. The ticket returns to the backlog
and the craw halts. That halt is the same state machine the PR-comment loop (TRACK-9) uses for
its `@crawfish-bot halt` veto; the two must be single-sourced so a craw can never be "halted in
gate 2 but still listening in the comment loop."

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Draft→ready + structured description (§8.1) | `PLAT` | `cloud/server/src/orchestrator/checkpoints/merge.ts` (O1.4) |
| CODEOWNERS reviewer assignment (§8.2) | `PLAT` | `cloud/server/src/orchestrator/checkpoints/merge.ts` (O1.4) |
| Reviewed in GitHub, no custom UI (§8.3) | — | *constraint, no code — see Concepts* |
| Single-approval merge (§8.4) | `PLAT` | reuses GitHub auto-merge API |
| N-approver policy (§8.5) | `PLAT` | `cloud/server/src/orchestrator/checkpoints/merge.ts` (O1.4) |
| Ticket auto-close + Linear comment (§8.6) | `PLAT` | reuses `cli/orgctl/src/inbound/github-issues.ts` mirror |
| Reject → halt → backlog (§8.7) | `PLAT` | `merge.ts` halt path, shared with TRACK-9 |

---

## User stories

Tags are now **components** (where it gets built), not personas.

8.1 **[PLAT]** When CI passes, the PR is converted from draft to ready-for-review with a structured PR description: what changed, what tests verify it, what was deferred, and the craw's confidence. *AC: description follows a template; review-friendly format; no walls of text.*

8.2 **[PLAT]** Configure who gets auto-assigned as the reviewer (default: the ticket assignee or owner of the touched files via CODEOWNERS). *AC: respects existing CODEOWNERS; falls back to a configured default reviewer.*

8.3 **[PLAT]** Review the PR in GitHub exactly as I would a human-authored PR, with no Crawfish-specific UI required. *AC: zero learning curve; the PR is structurally normal.*

8.4 **[PLAT]** A single GitHub approval merges the PR (when policy permits); the orchestrator does the merge and links the merge commit back to the ticket. *AC: respects branch protection rules; no force-merge.*

8.5 **[PLAT]** Require N approvers for craw-authored PRs (configurable per repo; default 1 for boring & bounded labels, 2 for risky). *AC: enforced at the orchestrator level on top of GitHub's own rules.*

8.6 **[PLAT]** Auto-close the original ticket when the PR merges; post the merge commit + PR link as a Linear comment. *AC: respects existing Linear status-transition rules; uses the GitHub mirror already shipped in `cli/orgctl/src/inbound/github-issues.ts`.*

8.7 **[PLAT]** Reject the PR with a comment and the craw stops re-engaging; the ticket returns to the backlog. *AC: opposite of auto-respond loop; explicit "halt this craw" path.*

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O1.4** — Pre-merge checkpoint workflow (gate 2) (`cloud/server/src/orchestrator/checkpoints/merge.ts`). One file owns the whole gate: it promotes the draft to ready with a templated description (§8.1), assigns the reviewer from CODEOWNERS or the ticket assignee with a configured fallback (§8.2), enforces the N-approver count on top of branch protection (§8.5), performs the merge when policy permits (§8.4), closes the ticket and posts the Linear comment (§8.6), and runs the reject→halt→backlog path (§8.7). The approval-count check and the merge must resolve **inside the durable workflow**, not in a webhook handler — so a crash between "approved" and "merged" resumes and completes the merge instead of dropping it.

  ```ts
  // cloud/server/src/orchestrator/checkpoints/merge.ts — promote draft → ready
  async function promoteToReady(pr: PullRequest, plan: PlanResult) {
    const body = renderPrDescription({
      changed: plan.summary,            // what changed
      tests: plan.agentAuthoredTests,   // what verifies it (frontmatter from TRACK-7 §7.7)
      deferred: plan.deferred,          // what was punted
      confidence: plan.confidence,      // craw's self-rated confidence
    });
    assertWithinLength(body);           // §8.1 "no walls of text" is a hard check, not a prompt hope
    await github.pulls.update({ ...pr.ref, draft: false, body });
    const reviewer = await resolveReviewer(pr);  // §8.2
    await github.pulls.requestReviewers({ ...pr.ref, reviewers: [reviewer] });
  }
  ```

  **Reuses (already shipped — do not rebuild):**
  - `cli/orgctl/src/inbound/github-issues.ts` GitHub mirror — for §8.6 ticket close + Linear comment. The §8.6 AC names this file directly; do not write a second issue client.
  - GitHub auto-merge API — §8.4 is "net-new but trivial" per USER-STORIES §17. Call `github.pulls.merge` only after the §8.5 count check passes and branch protection is satisfied; never `--force`.

  Cross-references: §8.3 carries **no O-stage** — it is a constraint (see Concepts), not a deliverable. The §8.7 halt path shares its state machine with TRACK-9's §9.8 veto; the §8.1 test section must agree with TRACK-7 §7.7's "which tests are agent-authored" labeling (single source). The §8.5 "risky" signal must be the same verdict as the plan checkpoint's §4.6 self-flag (TRACK-4), or the two gates classify the same PR inconsistently.

---

## Key technical concepts, explained

**The structured PR description template (§8.1).** "Structured" means a fixed four-section
shape — *changed / tests / deferred / confidence* — rendered the same way every time, not
free-form prose the craw improvises. A human scanning the PR knows exactly where to look. The
"no walls of text" AC is enforceable: run a length/format check on the generated body and
reject (or re-prompt) if it overflows. Treat it as a lint, not as a hope:

```ts
function assertWithinLength(body: string) {
  const MAX_LINES = 60;
  if (body.split("\n").length > MAX_LINES) {
    throw new DescriptionTooLong(body);  // re-generate with a tighter summary
  }
}
```

**N-approver policy layered ON TOP of GitHub branch protection (§8.5), not instead of it.**
GitHub already enforces its own required-reviews count via branch protection. The orchestrator
does **not** replace that — it adds a second, independent gate above it. The merge can be blocked
by *either* layer. So the orchestrator must read GitHub's protection state first and never attempt
a merge GitHub would reject (that would surface as a confusing API error). The two checks are
ANDed:

```ts
// §8.4 + §8.5: both layers must say yes
const ghOk = await github.protectionSatisfied(pr.ref);      // GitHub's own required reviews
const policyOk = approvals.length >= requiredApprovers(pr); // 1 for boring&bounded, 2 for risky
if (ghOk && policyOk) await github.pulls.merge(pr.ref);     // never force
```

`requiredApprovers` reads the same risk verdict the plan checkpoint produced (§4.6), so "risky"
means the same thing at both gates.

**Idempotent ticket auto-close (§8.6).** The merge → close-ticket → post-comment sequence is a
side effect that runs inside a retryable workflow (TRACK-5 §5.1). A merge-then-crash that
re-runs the step must **not** double-close the ticket or post the Linear comment twice. Key the
side effect on the merge commit SHA and check before acting:

```ts
// safe under workflow retry — second run is a no-op
if (!(await ticketAlreadyClosedFor(mergeSha))) {
  await githubIssuesMirror.closeTicket(ticketId, { respectStatusRules: true });
  await githubIssuesMirror.postComment(ticketId, linkTo(mergeSha, pr));
}
```

---

## Gaps — work with no O-stage assigned

These have acceptance criteria but no dedicated deliverable beyond O1.4. Flag for the lead.

- **§8.3 zero Crawfish-specific review UI** is correctly a **constraint, not a deliverable** — no code implements it. It shapes the §8.1 template (the description must read like a human's) and forbids building any custom review surface. Listed here so the lead does not accidentally scope a "review screen."
- **§8.2 CODEOWNERS-vs-assignee precedence.** The AC lists both the ticket assignee and the CODEOWNERS owner as the default reviewer without saying which wins when they disagree. *What's needed:* a single tie-break rule (e.g., CODEOWNERS owner of touched files wins; ticket assignee is the fallback) before O1.4 can resolve `reviewer` deterministically.

---

## Open questions

- **§8.2 reviewer precedence:** if CODEOWNERS and the ticket assignee disagree, which is assigned? The AC names both as "default" with no order. Resolve before implementing `resolveReviewer`.
- **§8.5 / §4.6 risk signal:** confirm the plan-checkpoint self-flag is durably persisted on the run record so gate 2 can read it post-CI, rather than recomputing risk (which could diverge from gate 1's verdict).
