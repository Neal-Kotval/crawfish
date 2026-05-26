# TRACK-7 — CI verification

**Components:** `PLAT` (the CI gate) · `CLI` (the test-generator + visual-auditor craws — UNNUMBERED, see Gaps)
**Source:** ORCHESTRATOR-USER-STORIES.md §7 · ROADMAP.md O-stage O1.7 (test-gen / visual-auditor craws are unnumbered, GRAND_PLAN §3.9)

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).

---

## What this surface is

This is the automated-verification stage between a drafted PR and the human merge gate. When a craw
drafts a PR, the customer's *own* existing CI (GitHub Actions) runs against it. The orchestrator reads
the result: on green it advances to the human checkpoint (TRACK-8); on red it reads the failure log
and attempts a bounded self-fix (default 3 revisions). It enforces a per-repo required-jobs list and a
regression guard (block if test count drops vs. base), and can optionally augment verification with
installable test-generator / visual-auditor craws that run as a parallel craw posting an additional
CI check.

In the lifecycle this sits after execution (TRACK-5) and before PR submission (TRACK-8). The customer
brings their own CI — the product does not replace it, it reads it, reacts to it, and optionally adds
checks alongside it.

The split is sharp. The **CI gate itself is O1.7**, a `PLAT` deliverable in `cloud/server`. The
**test-generator and visual-auditor craws are `CLI`** (they live with the other craws in `cli/orgctl`)
and are referenced in ROADMAP only as a narrative acceleration and GRAND_PLAN §3.9 — they have **no
numbered O3.N deliverable**. That unnumbered work is the headline gap on this track. The reusable piece
per USER-STORIES §17 is the existing GitHub-state reads in `cli/orgctl/src/inbound/github-issues.ts` —
the CI status poll builds on that.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| CI runs on draft PR (§7.1) | `PLAT` | `cloud/server/src/orchestrator/ci.ts` (O1.7), polls CI status |
| Required-jobs config (§7.2) | `PLAT` | `cloud/server/src/orchestrator/ci.ts` (O1.7), per-repo list |
| Read-log + bounded self-fix (§7.3) | `PLAT` | `cloud/server/src/orchestrator/ci.ts` (O1.7), N-revision loop |
| Halt + notify after N (§7.4) | `PLAT` | label + draft-hold is O1.7; the channel is O6.4 (TRACK-13) |
| Regression guard (§7.5) | `PLAT` | `cloud/server/src/orchestrator/ci.ts` (O1.7), test-count compare |
| Test-gen / visual-auditor craws (§7.6) | `CLI` | `cli/orgctl/src/craws/{test-generator,visual-auditor}/` — **UNNUMBERED** |
| Agent-authored test labeling (§7.7) | `CLI` | test-generator craw output + PR description template (TRACK-8) |

---

## User stories

Tags are now **components** (where it gets built), not personas.

7.1 **[PLAT]** When a craw drafts a PR, the customer's existing CI runs against it automatically (GitHub Actions). *AC: PR draft state until CI completes; orchestrator polls CI status.*

7.2 **[PLAT]** Configure which CI jobs are required (test suite, lint, type-check, security scan); only listed jobs gate the human checkpoint. *AC: required job list editable per repo; missing required job = block.*

7.3 **[PLAT]** When CI fails, the orchestrator reads the failure log and attempts to fix it (up to N revisions, default 3). *AC: each fix attempt logs as an additional commit; counter visible on the PR.*

7.4 **[PLAT]** After N failed fix attempts, the task halts and a human is notified with the full failure log + the craw's last attempted fix. *AC: PR stays as draft; ticket labeled `craw-stuck`; notification per §13.*

7.5 **[PLAT]** Configure a regression guard: if CI test count drops on the craw's branch vs. the base, fail the gate. *AC: prevents tests-deleted-to-make-CI-pass class of failure; default on; toggleable per repo.*

7.6 **[CLI]** Surface the existing test-generator + visual-auditor agents (GRAND_PLAN §3.9) as installable craws that augment any task's CI verification. *AC: optional, off by default; when on, runs as a parallel craw and posts as an additional CI check.*

7.7 **[CLI]** When the test-generator craw adds tests, they're marked as agent-authored in the PR description and labeled in the test file's frontmatter. *AC: human reviewer can filter "show me only agent-authored tests."*

---

## Coding tasks, by component

### PLAT — `cloud/server`

- **O1.7** — CI gate, GitHub Actions (`cloud/server/src/orchestrator/ci.ts`). The single backend deliverable covering §7.1–§7.5:
  - §7.1 — hold the PR in **draft** state and poll CI status until the run completes.
  - §7.2 — a per-repo **required-jobs list** (test, lint, type-check, security scan); only listed jobs gate the human checkpoint, a missing required job blocks. Keep this list **single-sourced** — the merge gate (O1.4, TRACK-8) reads the same definition so CI and the gate agree on what "green" means.
  - §7.3 — on failure, read the failure log and run a **bounded self-fix loop** (default 3 revisions); each attempt is an additional commit and the counter shows on the PR.
  - §7.4 — after N failures, **halt**, keep the PR as draft, label the ticket `craw-stuck`. The label and draft-hold are O1.7; the notification *channel* is O6.4 (see note).
  - §7.5 — **regression guard**: compare CI test count on the branch vs. base and fail if it dropped (blocks the tests-deleted-to-pass failure class). Default on, per-repo toggle.

  ```ts
  // cloud/server/src/orchestrator/ci.ts — poll-read-fix with a revision cap (§7.1, §7.3, §7.4)
  for (let attempt = 1; attempt <= repo.maxRevisions ?? 3; attempt++) {
    const run = await pollCiUntilComplete(pr);          // §7.1 — draft until CI completes
    if (run.conclusion === "success") return advanceToHumanGate(pr);
    if (await budgetBreached(task)) return halt(pr, "budget_cap"); // §5.6 — halt before next attempt
    const fix = await craw.fixFromLog(run.failureLog);  // §7.3 — read log, attempt fix
    await commitFix(pr, fix, { attempt });              // additional commit, counter visible
  }
  await halt(pr, "craw-stuck"); // §7.4 — draft stays, label set; notify via O6.4 (TRACK-13)
  ```

  ```ts
  // §7.5 regression guard — block if test count drops vs. base
  const base = await parseTestCount(baseRun);   // provider/framework-specific extraction
  const head = await parseTestCount(headRun);
  if (repo.regressionGuard !== false && head < base) {
    return failGate(pr, `test count dropped ${base} → ${head}`); // tests-deleted-to-pass guard
  }
  ```

**Reuses (already shipped — do not rebuild):**
- Existing GitHub-state reads in `cli/orgctl/src/inbound/github-issues.ts` — the CI status read builds on this GitHub API plumbing (USER-STORIES §17, §7).

### CLI — `cli/orgctl` (test-gen + visual-auditor craws — UNNUMBERED, see Gaps)

- **Test-generator + visual-auditor craws** (`cli/orgctl/src/craws/{test-generator,visual-auditor}/{craw.yaml,SKILL.md,impl.ts}`). Implements §7.6 (installable, off by default; when on, runs as a **parallel craw** and posts as an **additional CI check**) and §7.7 (agent-authored test labeling). These are accelerated from LATER² weeks 19–20 and described in ROADMAP / GRAND_PLAN §3.9 ("Agent CI/CD") — but **no numbered O3.N deliverable exists for them.** They run as parallel craws using the multi-craw collab primitive (O3.1, TRACK-6), since "parallel craw" is the same execution shape as the team view. §7.7's labeling lives in two places — the PR description and the test-file frontmatter — so a reviewer can machine-filter agent-authored tests; the frontmatter convention must be stable (it overlaps the PR description template in TRACK-8).

  ```yaml
  # cli/orgctl/src/craws/test-generator/craw.yaml — §7.6 installable, off by default
  name: test-generator
  enabled: false            # opt-in per AC
  runs: parallel            # alongside customer CI, posts as an additional check
  posts_check: agent-tests  # appears as one more CI status, not a replacement
  ```

  ```ts
  // §7.7 — frontmatter so a reviewer can filter "only agent-authored tests"
  const header = `// @crawfish-authored: test-generator\n// @task: ${task.id}\n`;
  await fs.writeFile(testPath, header + generatedTest);
  // and a line in the PR description: "Agent-authored tests: src/foo.test.ts (test-generator)"
  ```

---

## Key technical concepts, explained

**Poll-read-fix loop with a revision cap (§7.1, §7.3).** The orchestrator does not get pushed a CI
result; it **polls** GitHub Actions until the run reaches a terminal conclusion, then branches on it.
On failure it reads the failure log, asks the craw for a fix, commits it as an *additional* commit
(the counter on the PR is just the attempt number), and loops — but only up to N (default 3). The cap
is what stops an infinite fix-fail-fix spiral. This bounded-retry shape is the same as the PR-comment
loop (TRACK-9, O4.3); consider one shared revision-cap primitive rather than two, since both cap
attempts and both surface a counter (see the O1.7 snippet). Critically, the loop must check the
per-task budget (§5.6, TRACK-5) **before** each attempt — three fix attempts each burn tokens, so a
budget breach should halt *before* attempt N, not after.

**Regression guard parsing test counts (§7.5).** The guard compares the number of tests on the craw's
branch against the base branch and fails the gate if it dropped — closing the "delete the failing test
to make CI green" hole. The fragile part is *extracting* the count: Jest, pytest, and `go test` each
report it differently, so you need a per-framework parser, normalized to one integer:

```ts
// §7.5 — provider/framework-specific test-count extraction, normalized to one number
function parseTestCount(run: CiRun): number {
  if (run.framework === "jest")   return Number(/Tests:\s+\d+ failed,\s+(\d+) passed/.exec(run.log)?.[1] ?? matchTotal(run.log));
  if (run.framework === "pytest") return Number(/(\d+) passed/.exec(run.log)?.[1] ?? 0);
  if (run.framework === "go")     return (run.log.match(/^--- (PASS|FAIL)/gm) ?? []).length;
  throw new Error(`no test-count parser for ${run.framework}`); // brittle unless normalized
}
```

This is brittle by nature — flag it. A wrong parse either blocks a legitimate PR or lets a
test-deletion through.

**"Additional CI check" via a parallel craw (§7.6).** The test-gen / visual-auditor craws do not modify
the customer's CI config. They run *alongside* it as a parallel craw (same execution shape as the
multi-craw team view, O3.1) and report their result as one more CI status check on the PR — augmenting,
never replacing, the customer's pipeline. They are off by default and opt-in per repo (see the
`craw.yaml` snippet).

---

## Gaps — work with no O-stage assigned

These have acceptance criteria but no clean numbered O0–O7 deliverable. Flag for the lead.

- **§7.6 / §7.7 test-generator + visual-auditor craws — UNNUMBERED (headline gap).** ROADMAP references
  them only as a narrative acceleration ("Test-gen + visual-auditor ship as additional orchestrator
  craws in stage O3") and as GRAND_PLAN §3.9 / row "3.9 Agent CI/CD." **There is no numbered O3.N
  deliverable** — the O3 table (O3.1–O3.8) is collab / SSE / team-view / replay / failure-handling. The
  work is committed but unnumbered. *What's needed:* the lead either assigns O3.x numbers to these two
  craws or confirms they ship under the craw-library deliverables (O2.x) instead. Until that happens,
  §7.6 and §7.7 have no owner in the O-stage map.
- **§7.4 notification channel.** O1.7 sets the `craw-stuck` label and holds the PR draft, but the
  *notification delivery* is **O6.4** (TRACK-13) — §7.4 AC explicitly says "notification per §13." *What's
  needed:* confirm O1.7 emits the event O6.4 consumes, so the halt and the notification are wired, not
  two disconnected features.

---

## Open questions

- **Test-count parsing (§7.5):** how is "test count" extracted across Jest / pytest / `go test` and beyond? The guard is brittle unless every framework's output is normalized to one reliable integer. Which frameworks ship in v1?
- **O-stage numbers for §7.6/§7.7:** do the test-gen / visual-auditor craws get O3.x numbers or fold into the craw-library (O2.x)? This decides their owner, their sequencing, and whether they ship in the same wave as O1.7.
- **Frontmatter convention (§7.7):** the agent-authored marker lives in both the PR description and the test-file frontmatter and must be machine-filterable — is the frontmatter key single-sourced with the PR description template (TRACK-8, O8/8.1), or defined twice?
