# TRACK-8 — PR submission & merge checkpoint (gate 2)

## Overview
The second human gate. When CI passes, the draft PR is promoted to ready-for-review with a structured description, a reviewer is auto-assigned via CODEOWNERS, and a policy-governed approval merges it — closing the originating ticket. The design constraint is zero Crawfish-specific review UI: the craw's PR is reviewed exactly like a human's. Primary personas: IC (reviews, approves, rejects), EM (reviewer assignment, ticket auto-close), VPE (N-approver policy). Sits after CI (TRACK-7); a merge here is the terminal success state, and a reject hands off to the PR-comment loop's halt path (TRACK-9).
Source: ORCHESTRATOR-USER-STORIES.md §8.

---

## User stories

8.1 **[IC]** When CI passes, the PR is converted from draft to ready-for-review with a structured PR description: what changed, what tests verify it, what was deferred, and the craw's confidence. *AC: description follows a template; review-friendly format; no walls of text.*

8.2 **[EM]** Configure who gets auto-assigned as the reviewer (default: the ticket assignee or owner of the touched files via CODEOWNERS). *AC: respects existing CODEOWNERS; falls back to a configured default reviewer.*

8.3 **[IC]** Review the PR in GitHub exactly as I would a human-authored PR, with no Crawfish-specific UI required. *AC: zero learning curve; the PR is structurally normal.*

8.4 **[IC]** A single GitHub approval merges the PR (when policy permits); the orchestrator does the merge and links the merge commit back to the ticket. *AC: respects branch protection rules; no force-merge.*

8.5 **[VPE]** Require N approvers for craw-authored PRs (configurable per repo; default 1 for boring & bounded labels, 2 for risky). *AC: enforced at the orchestrator level on top of GitHub's own rules.*

8.6 **[EM]** Auto-close the original ticket when the PR merges; post the merge commit + PR link as a Linear comment. *AC: respects existing Linear status-transition rules; uses the GitHub mirror already shipped in `cli/orgctl/src/inbound/github-issues.ts`.*

8.7 **[IC]** Reject the PR with a comment and the craw stops re-engaging; the ticket returns to the backlog. *AC: opposite of auto-respond loop; explicit "halt this craw" path.*

---

## Coding tasks (from ROADMAP.md)

- **O1.4** — Pre-merge checkpoint workflow (gate 2) (`cloud/server/src/orchestrator/checkpoints/merge.ts`) — implements §8.1 (draft→ready, structured description), §8.2 (CODEOWNERS reviewer assignment), §8.4 (single-approval merge, branch-protection-respecting), §8.5 (N-approver policy), §8.6 (ticket auto-close + Linear comment), §8.7 (reject → halt → backlog).
  - Reuses: `cli/orgctl/src/inbound/github-issues.ts` GitHub mirror — for §8.6 ticket close + comment (cited directly in §8.6 AC).
  - Reuses: GitHub auto-merge API — §8.4 is "net-new but trivial" per USER-STORIES §17.

Note: §8.3 (zero Crawfish-specific review UI) is a *constraint*, not a deliverable — it asserts the PR is structurally normal and reviewed in GitHub. No code implements it; it shapes §8.1's description template. Correctly carries no O-stage.

Note: §8.7 reject→halt is the inverse of the auto-respond loop (TRACK-9, O4.x) and shares the "halt this craw" path with §9.8 veto. Keep the halt-state machine single-sourced across gate 2 and the PR-comment loop.

---

## Tech stack considerations

- §8.5 N-approver policy is enforced "on top of GitHub's own rules" — the orchestrator layers a count requirement above branch protection, never below or instead of it (§8.4 "no force-merge"). Two policy layers means the merge can be blocked by either; the orchestrator must read GitHub's protection state and not attempt a merge GitHub would reject.
- §8.1 structured description (changed / tests / deferred / confidence) is a template, and its agent-authored-test section must agree with TRACK-7's §7.7 frontmatter labeling — one source for "which tests are agent-authored." "No walls of text" is a generation constraint on the craw, enforceable via a length/format check, not just prompt guidance.
- §8.6 ticket auto-close respects existing Linear status-transition rules and uses the shipped GitHub mirror; the close + comment is a side-effect that must be idempotent under workflow retry (TRACK-5 §5.1) — a merge-then-crash must not double-close or double-comment.
- §8.4 merge is performed by the orchestrator on a single approval *when policy permits*; the approval event and the §8.5 approver-count check must resolve in the durable workflow, not a webhook handler, so a crash between approval and merge resumes cleanly rather than dropping the merge.
- §8.2 default reviewer is ticket assignee or CODEOWNERS owner of touched files, with a configured fallback; resolving "owner of touched files" requires the diff, which exists post-CI — assignment happens at draft→ready, not earlier. Open question: if CODEOWNERS and ticket assignee disagree, which wins? AC lists both as default without precedence.
- §8.5 default differs by label class (1 for boring & bounded, 2 for risky); "risky" must use the same risk signal as the plan checkpoint's §4.6 self-flag, or the two gates will classify the same PR inconsistently. Single risk verdict, consumed at both gates.
