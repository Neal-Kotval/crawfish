# craw code — one-shot build prompt

Paste everything in the fenced block below into Claude Code, run from the root of the
`crawfish` repo. Run with enough tool permission to use git, `gh`, `uv`, and `claude -p`
(e.g. an allowlist or `--dangerously-skip-permissions` in a throwaway clone). The live
demo step shells out to `claude -p`, which uses your logged-in Claude.

---

````text
You are the ORCHESTRATOR for building "craw code" end-to-end in this repository, in one
session, to a perfectly-architected, fully-tested, merged state. Optimize for maximum
correctness and maximum safe parallelism. Do not hand back a partial result.

═══════════════════════════════════════════════════════════════════════════════
0. READ BEFORE DOING ANYTHING (these are the source of truth — do not re-derive)
═══════════════════════════════════════════════════════════════════════════════
- docs/specs/craw-code/00-README.md   ← index, dependency graph, full issue inventory,
                                         the 14 unfiled gaps, the 3 ADRs to write
- docs/specs/craw-code/01-foundations-and-cli.md     (M0, M1)
- docs/specs/craw-code/02-scaffolding-plugin-authoring.md  (M2, M3, M3a)
- docs/specs/craw-code/03-dashboard-operate-hitl.md  (M4, M4.5, M6)
- docs/rfcs/0001-craw-code.md  (the why + §12 hardening)
- docs/architecture/SECURITY.md, ARCHITECTURE.md, API-STABILITY.md
- docs/reference/definition.md, docs/guide/cli.md, docs/guide/project-structure.md
- CLAUDE.md  (architecture rules + Definition of Done)
Every issue (CRA-243…279 and the UNFILED-* gaps) is already specced with Context, Design,
Interface, Acceptance criteria, Test plan, and Security notes. BUILD TO THOSE SPECS. If a
spec is wrong or underspecified, fix the spec first (with a one-line rationale), then build.

═══════════════════════════════════════════════════════════════════════════════
1. NON-NEGOTIABLES (apply to every line of code; a milestone is not done until all hold)
═══════════════════════════════════════════════════════════════════════════════
- DEFINITION OF DONE per CLAUDE.md: `uv run ruff check .` + `uv run ruff format --check .`
  + `uv run mypy packages/crawfish/src` + `uv run pytest -q` all GREEN and DETERMINISTIC
  (no live model calls in tests — fixtures / cassettes / MockRuntime only).
- SECURITY SPINE (SECURITY.md): Flow.FLUID is untrusted data, never instructions;
  consequential sink targets + idempotency keys are static-only; secrets by reference,
  never logged/in-prompt. THE craw code TWIST: agent-authored code is no longer
  authoring-time-trusted — it must be provenance-stamped (CRA-266), jailed at compile
  (CRA-267), and gated before --live (UNFILED-GATE). Each new fluid surface adds a
  red-team payload to packages/crawfish/tests/test_redteam_security.py.
- ARCHITECTURE RULES (CLAUDE.md): product model imports the Store/AgentRuntime/
  ArtifactStore PROTOCOLS, never a concrete backend; no raw SQL outside a Store impl;
  structural typing via crawfish.typesystem, never string equality.
- ONE OWNER PER FILE: no two parallel agents edit the same module. Partition by file up
  front; if two milestones need the same file, serialize them or split the file.
- ADRs: on any architectural/security fork, write an ADR under
  docs/architecture/decisions/ (create the dir) with rationale + rejected alternatives.

═══════════════════════════════════════════════════════════════════════════════
2. AGENT TOPOLOGY (spawn as subagents; run as many in parallel per step as deps allow)
═══════════════════════════════════════════════════════════════════════════════
STANDING SPECIALISTS (re-spawn them at each gate; give them the diff to review):
- security-agent     — audits every PR against the security spine + the trust-collapse
                       mitigations; owns the red-team suite; can BLOCK a merge.
- architecture-agent — audits seam discipline (protocols-not-backends, structural typing,
                       ADR coverage, --json schema versioning); can BLOCK a merge.
- build-agent        — owns CI/determinism: ensures ruff+mypy+pytest green, no live calls,
                       fixtures/cassettes wired; owns cross-cutting conventions (the
                       craw.error.v1 envelope, the provenance record format, exit codes)
                       so all milestone agents share one contract.
- qa-agent           — runs the FULL suite + the demo end-to-end, reads the rendered diff,
                       checks acceptance criteria per issue; can BLOCK a merge.
PER-MILESTONE IMPLEMENTATION AGENTS (one per milestone, each in its OWN git worktree):
  m0, m1, m2, m3, m3a, m4, m4.5, m6, m5 — each builds its milestone's issues to spec.

When you launch independent agents, launch them IN A SINGLE STEP (multiple tool calls at
once) so they run concurrently. Never serialize work that has no dependency between it.

═══════════════════════════════════════════════════════════════════════════════
3. WORKTREE + PR WORKFLOW
═══════════════════════════════════════════════════════════════════════════════
- Create an integration branch: `git checkout -b craw-code/integration`.
- For each milestone agent, create an isolated worktree + branch:
  `git worktree add ../cc-<milestone> -b craw-code/<milestone> craw-code/integration`
  The agent works ONLY inside its worktree. This is what makes parallel safe.
- When a milestone's issues are spec-complete AND its local DoD is green, the agent opens
  a PR: `gh pr create --base craw-code/integration --title "craw code: <Mn> …" --body …`
  The PR body lists the issues closed, the acceptance criteria checked, the ADRs added,
  and the red-team payloads added.
- GATE before merge: spawn security-agent + architecture-agent + qa-agent on the PR diff.
  Merge to craw-code/integration ONLY when all three sign off. If blocked, the milestone
  agent fixes and re-requests review. Rebase later worktrees on integration after a merge.
- After ALL milestones merge: open the final PR craw-code/integration → main with a
  summary, full green CI, and the demo transcript attached.
- LINEAR (track progress on the board): this work is the "craw code" project, team CRA:
  https://linear.app/crawfish/project/craw-code-7d0986a663db
  Use the Linear MCP if available. When a milestone agent STARTS, move its CRA issues to
  "In Progress"; when its PR merges to integration, move them to "Done" and add the PR URL
  as a comment/link on each issue. Issue→milestone mapping is in docs/specs/craw-code/
  00-README.md. The 14 UNFILED-* gaps have NO Linear issue (free-tier cap) — if the cap is
  lifted, create them from their specs under the right milestone; otherwise just note them
  as closed in the PR body. Never block the build on Linear being writable.

═══════════════════════════════════════════════════════════════════════════════
4. DEPENDENCY-ORDERED WAVES (the schedule — respect the graph in 00-README.md)
═══════════════════════════════════════════════════════════════════════════════
WAVE 1 (parallel): 
  • build-agent + architecture-agent FIRST establish the shared contracts and ADRs:
    the craw.error.v1 envelope (CRA-270), the --json schema-version negotiation
    (CRA-269), the --json/exit-code audit (CRA-243), the provenance record format
    (CRA-266), and the 3 ADRs (jailed-compile, ObserverSurface seam, export relationship).
  • m0 agent: CRA-266 provenance (KEYSTONE) → CRA-267 jailed compile; CRA-268 harness.
WAVE 2 (parallel, after M0 keystone lands on integration):
  • m1 agent: CRA-244 describe (uses jailed compile) → CRA-271 redaction, CRA-274 cache/
    standalone; CRA-272 assembly-gate-in-run; CRA-273 estimate + [budget]; CRA-275 org_id.
  • m2 agent: CRA-245 init → CRA-246 new → CRA-247 sync.
WAVE 3 (parallel):
  • m2 agent: CRA-276 templates, CRA-277 MCP consent, CRA-278 tree-lock, CRA-279 idempotent
    init, UNFILED-MAP, UNFILED-ADOPT(+explain).
  • m3 agent: CRA-248/249/250 skills, CRA-251 commands, UNFILED-PIN plugin integrity.
  • m3a agent: CRA-256 authoring spec, CRA-257 golden example.
WAVE 4 (parallel):
  • m3a agent: CRA-258…264 per-file authoring skills (these are independent — parallelize
    internally if you spawn sub-agents), CRA-265 validation eval (needs harness + golden).
  • m4 agent: UNFILED-SEAM (ObserverSurface) → CRA-252 data layer → CRA-253/254 views,
    UNFILED-XSS, UNFILED-COST.
WAVE 5 (parallel):
  • m4.5 agent: UNFILED-OPTIMIZE, UNFILED-DEPLOY(+fleet), UNFILED-CONTROL.
  • m6 agent: UNFILED-GATE (PreToolUse hook + propose/apply), UNFILED-REVIEW, UNFILED-DIAGNOSE.
WAVE 6 (serial, final):
  • m5 agent: optional thin MCP veneer (only the 4 fixed meta-tools over the CLI).
  • Full-system integration QA + the live demo (section 5).

═══════════════════════════════════════════════════════════════════════════════
5. DEMO — PROVE IT WORKS FOR REAL (not just unit tests)
═══════════════════════════════════════════════════════════════════════════════
- Extend demo/triage-bot/ and add demo/craw-code-tour/ that exercises the whole loop:
  `craw code init` → `craw code new definition …` → author contents → `craw code describe`
  → `craw code estimate` → `craw code run` (mock) → read ledger → `craw code eval` →
  `craw code optimize` → `craw code deploy` → `craw code dashboard` (screenshot/serialized
  state) → propose/apply gate.
- LIVE smoke test using the logged-in Claude: drive the actual authoring loop headless,
  e.g. `claude -p "using the craw code skills, author a triage definition that …"
  --allowedTools "Read,Write,Edit,Bash"` in the demo dir, then assert the result passes
  `craw code sync` / `load_definition` cleanly. Capture the transcript to
  demo/craw-code-tour/TRANSCRIPT.md. Keep this OUT of the deterministic pytest suite (it's
  a live smoke test, run once); the CI tests stay mock-only.
- The demo must run green end-to-end before the final PR.

═══════════════════════════════════════════════════════════════════════════════
6. COORDINATION + CONVERGENCE LOOP
═══════════════════════════════════════════════════════════════════════════════
- Maintain a live task list mirroring the issues; mark in_progress/done as you go.
- After each wave: rebase open worktrees on integration; run the FULL suite at integration
  level (not just per-worktree) to catch cross-milestone breakage; have qa-agent triage.
- ITERATE UNTIL GREEN. A milestone is done only when: all its issues' acceptance criteria
  pass, DoD is green at integration, security+architecture+qa signed off, docs + demo
  updated. Do not mark done otherwise.
- Linear: update issue status per section 3 (project board, team CRA). Do NOT block on
  Linear being writable; the specs in docs/specs/craw-code/ are the source of truth.

═══════════════════════════════════════════════════════════════════════════════
7. DOCS — FOLD INTO THE EXISTING DOCS SET, MATCH THE HOUSE STYLE
═══════════════════════════════════════════════════════════════════════════════
Docs are part of Definition of Done — a milestone is not complete until its docs land.
- STUDY THE HOUSE STYLE before writing: read docs/guide/getting-started.md, tutorial.md,
  optimize-from-the-cli.md, project-structure.md, and docs/reference/definition.md. Match
  it exactly: warm narrative PROSE (not bullet dumps), a short "You will learn:" list near
  the top of guide pages, runnable fenced examples, tables for option/flag matrices, and
  admonitions (`!!! warning`) for security boundaries. No marketing tone.
- ADD A "craw code" SECTION to the docs and register every new page in mkdocs.yml `nav:`
  (it will not appear otherwise). Suggested nav group placed after "Operate":
    - craw code:
        - Overview & quickstart:        guide/craw-code/index.md
        - Author a project with craw code: guide/craw-code/authoring.md
        - The craw code CLI:            guide/craw-code/cli.md
        - The dashboard:                guide/craw-code/dashboard.md
        - Operate & optimize:           guide/craw-code/operate.md
        - Review & approve (HITL):      guide/craw-code/review-and-approve.md
        - Security model:               guide/craw-code/security.md
  Plus reference pages where craw code adds typed surfaces (under "Reference"):
        - craw code provenance & jailed compile: reference/craw-code-provenance.md
        - craw.error.v1 & --json contracts:      reference/craw-code-json-contracts.md
- WRITE A "how to write docs" GUIDE for contributors so future craw code work stays
  consistent: docs/guide/craw-code/writing-docs.md — codify the house style above (page
  skeleton, the "You will learn" pattern, when to use guide vs reference, how to register
  in nav, the security-admonition convention, the deterministic-example rule). Each
  milestone agent follows it.
- UPDATE EXISTING PAGES that craw code changes, don't duplicate them:
    • guide/cli.md — add the `craw code` verb family to the CLI map.
    • guide/project-structure.md — note the craw code plugin assets + provenance in
      .crawfish/ (authored vs generated separation still holds).
    • guide/claude-code-export.md — cross-link the resolved O-4 relationship (adopt
      subsumes export; disjoint .claude/ namespaces).
    • docs/reference/definition.md — note the agent-authored / jailed-compile path.
    • ROADMAP.md and docs/rfcs/0001-craw-code.md §10 — flip resolved open questions.
- Each guide page must have at least one example a reader can actually run against the
  demo (section 5). Build the docs with mkdocs locally if available to confirm nav + links
  resolve before the milestone PR.

═══════════════════════════════════════════════════════════════════════════════
8. FINAL DELIVERABLE
═══════════════════════════════════════════════════════════════════════════════
- All milestones merged to craw-code/integration, each via a reviewed PR.
- One final PR craw-code/integration → main: full green CI (ruff+mypy+pytest), the 3 ADRs,
  updated docs, the demo + live TRANSCRIPT.md, and a top-level summary mapping every CRA/
  UNFILED issue to the commit(s) that closed it and the acceptance criteria that passed.
- End with a concise report: what shipped, every gate that passed, any spec corrections you
  made, and anything you could NOT complete (with the reason) — be honest, don't paper over.

Begin by reading section 0, printing the wave plan with the file-ownership partition, then
launching Wave 1.
````
