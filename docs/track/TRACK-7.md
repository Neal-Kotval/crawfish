# TRACK-7 — CI verification

## Overview
The automated-verification stage between a drafted PR and the human merge gate: the customer's existing CI runs against the craw's draft PR, the orchestrator reads failures and attempts bounded self-fixes, enforces a required-jobs list and a regression guard, and can augment verification with installable test-generator / visual-auditor craws. Primary personas: IC (sees CI run, fix attempts), EM (configures required jobs, halt-after-N), PLAT (regression guard), QA (agent-authored test labeling). Sits after execution (TRACK-5) and before PR submission (TRACK-8).
Source: ORCHESTRATOR-USER-STORIES.md §7.

---

## User stories

7.1 **[IC]** When a craw drafts a PR, the customer's existing CI runs against it automatically (GitHub Actions). *AC: PR draft state until CI completes; orchestrator polls CI status.*

7.2 **[EM]** Configure which CI jobs are required (test suite, lint, type-check, security scan); only listed jobs gate the human checkpoint. *AC: required job list editable per repo; missing required job = block.*

7.3 **[IC]** When CI fails, the orchestrator reads the failure log and attempts to fix it (up to N revisions, default 3). *AC: each fix attempt logs as an additional commit; counter visible on the PR.*

7.4 **[EM]** After N failed fix attempts, the task halts and a human is notified with the full failure log + the craw's last attempted fix. *AC: PR stays as draft; ticket labeled `craw-stuck`; notification per §13.*

7.5 **[PLAT]** Configure a regression guard: if CI test count drops on the craw's branch vs. the base, fail the gate. *AC: prevents tests-deleted-to-make-CI-pass class of failure; default on; toggleable per repo.*

7.6 **[PLAT]** Surface the existing test-generator + visual-auditor agents (GRAND_PLAN §3.9) as installable craws that augment any task's CI verification. *AC: optional, off by default; when on, runs as a parallel craw and posts as an additional CI check.*

7.7 **[QA]** When the test-generator craw adds tests, they're marked as agent-authored in the PR description and labeled in the test file's frontmatter. *AC: human reviewer can filter "show me only agent-authored tests."*

---

## Coding tasks (from ROADMAP.md)

- **O1.7** — CI gate (GitHub Actions) (`cloud/server/src/orchestrator/ci.ts`) — implements §7.1 (poll CI, draft until complete), §7.2 (required-jobs list, missing = block), §7.3 (read failure log, fix up to N), §7.4 (halt + notify after N), §7.5 (regression guard on test count).
- **O3 test-generator + visual-auditor craws** (accelerated from LATER² weeks 19–20; ship as orchestrator craws in stage O3 per ROADMAP §3.9) — implements §7.6 (installable, off by default, parallel craw posting as an extra CI check) and §7.7 (agent-authored test labeling).
  - Reuses: existing GitHub-state reads in `cli/orgctl/src/inbound/github-issues.ts` — the CI status read builds on this (USER-STORIES §17, §7).

Gap / flag: §7.6's test-generator + visual-auditor craws are referenced in ROADMAP only as a narrative acceleration ("Test-gen + visual-auditor ship as additional orchestrator craws in stage O3") and as GRAND_PLAN §3.9 / row "3.9 Agent CI/CD". **There is no numbered O3.N deliverable** for them in the O3 table (O3.1–O3.8 are collab/SSE/team-view/replay/failure-handling). The work is committed but unnumbered — lead should assign O3.x numbers or confirm they ship under the craw-library deliverables (O2.x) instead.

Note: §7.4 notification delivery is **O6.4** (TRACK-13); §7.4 AC explicitly says "notification per §13." The `craw-stuck` label and PR-stays-draft behavior are O1.7; the channel is O6.4.

---

## Tech stack considerations

- §7.1/§7.3 are a poll-read-fix loop against GitHub Actions; the fix loop (default 3 revisions, §7.3) shares its bounded-retry shape with the PR-comment loop (TRACK-9, O4.3 — also default-bounded). Consider one revision-cap primitive rather than two, since both cap attempts and both surface a counter.
- §7.5 regression guard compares CI test count on branch vs. base to block the tests-deleted-to-pass failure class; this needs a reliable per-run test-count extraction from CI output, which is provider- and framework-specific. Default-on, per-repo toggle. Open question: how is "test count" parsed across Jest/pytest/go test? Brittle unless normalized.
- §7.2 required-jobs list gates the human checkpoint (TRACK-8 gate 2) — only listed jobs block. This is a per-repo config that the merge checkpoint (O1.4) reads; keep the required-jobs definition single-sourced so CI and the merge gate agree on what "green" means.
- §7.6 test-gen / visual-auditor run as parallel craws posting an *additional* CI check — they augment, not replace, customer CI, and are off by default. They use the multi-craw collab primitive (O3.1, TRACK-6) since "parallel craw" is the same execution shape as the team view.
- §7.7 agent-authored test marking lives in two places (PR description + test-file frontmatter) so a reviewer can filter agent-authored tests; the frontmatter convention must be stable and machine-filterable. This is a labeling contract, not just copy — overlaps the PR description template (TRACK-8, O8/8.1).
- The fix loop's per-attempt commit (§7.3) and the halt-with-full-log (§7.4) both must respect the per-task budget cap (TRACK-5 §5.6) — three fix attempts can each burn tokens. A budget breach mid-fix-loop should halt before attempt N, not after.
