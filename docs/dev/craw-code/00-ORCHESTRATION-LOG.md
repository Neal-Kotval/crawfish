# craw code — Build Orchestration Log

This document records the **key architectural decisions and the orchestration process**
for building `craw code` end-to-end, as required by the build prompt. It is the dev-facing
companion to the user-facing specs in [`docs/specs/craw-code/`](../../specs/craw-code/00-README.md)
and RFC [`0001-craw-code`](../../rfcs/0001-craw-code.md).

## Orchestration model (decisions of the orchestrator)

The build prompt asks for one-owner-per-file parallelism across 9 milestones via git
worktrees, with PR gates reviewed by standing security/architecture/qa specialists, merged
to an integration branch, then a final PR to `main`. Concrete decisions taken to execute
that safely:

1. **A new `crawfish/code/` subpackage houses the entire `craw code` verb family.** This
   is the single most important collision-avoidance decision. Every milestone owns
   *disjoint new modules* inside `crawfish/code/`, plus *disjoint test files* (the spec's
   per-issue `test_code_*.py` names give the exact partition). No two milestone agents edit
   the same file.

2. **Subcommand registration is auto-discovered, not hand-wired.** `crawfish/code/__init__.py`
   exposes a registry that discovers `register(subparsers)` hooks in sibling modules via
   `pkgutil`. Adding a new verb is adding a new file — never editing a shared dispatcher.
   The only one-time edit to the top-level `crawfish/cli.py` (wiring the `code` group) is
   done **once** in Wave 1 and never touched again.

3. **Wave 1 is a single cohesive "foundation" agent, not parallel.** The contracts
   (`craw.error.v1` envelope CRA-270, `--json` schema negotiation CRA-269, exit-code audit
   CRA-243, provenance record format CRA-266) and the M0 keystone (provenance CRA-266,
   jailed compile CRA-267, loop harness CRA-268) all live on the *same* shared foundation
   files (`crawfish/code/__init__.py`, `provenance.py`, `jail.py`, the registry). Splitting
   them across agents would violate one-owner-per-file. They are one interlocking contract,
   so one deep agent builds them. Everything downstream keys on this, so Wave 1 fully lands
   and is gated **before** any Wave 2 worktree branches from integration.

4. **Worktree isolation + orchestrator-side integration.** Each milestone agent works in
   its own `git worktree` off `craw-code/integration`, runs its local DoD green, and reports
   its branch. The orchestrator merges each branch into integration, re-runs the *full* suite
   at integration level to catch cross-milestone breakage, and only then runs the specialist
   review gate. This keeps parallel builds safe while keeping integration correctness at the
   orchestrator (the one actor that sees all milestones at once).

5. **Standing specialists are review *passes*, not long-lived processes.** `security-agent`,
   `architecture-agent`, and `qa-agent` are re-spawned against each integrated diff with the
   authority to BLOCK. A block returns a fix-list to the milestone agent; the loop repeats
   until all three sign off.

## File-ownership partition (one owner per file)

| Milestone | Owns (source, under `crawfish/code/` unless noted) | Owns (tests) |
| --- | --- | --- |
| **Wave 1 foundation (M0+contracts)** | `code/__init__.py` (registry, `craw.error.v1`, schema negotiation, exit codes, provenance record), `code/cli.py` (`craw code` group), `code/harness.py`; extends `provenance.py`, `jail.py`; one-time edit to top-level `cli.py` | `test_file_provenance.py`, `test_jailed_compile.py`, `test_authoring_harness.py`, `test_error_envelope.py`, `test_schema_negotiation.py`, `test_cli_json_coverage.py` |
| **M1** foundations & CLI | `code/describe.py`, `code/estimate.py`; extends `build.py` assembly-gate-in-run | `test_describe.py`, `test_describe_redaction.py`, `test_describe_cache.py`, `test_code_estimate.py`, `test_run_assembly_gate.py`, `test_code_org_isolation.py` |
| **M2** scaffolding | `code/init.py`, `code/new.py`, `code/sync.py`, `code/map.py`, `code/adopt.py`, `code/templates.py`, `code/lint.py` | `test_code_init.py`, `test_code_new.py`, `test_code_sync.py`, `test_code_map.py`, `test_code_adopt.py`, `test_code_explain.py`, `test_code_init_reentrant.py`, `test_code_tree_lock.py`, `test_code_consent_regate.py`, `test_code_lint.py` |
| **M3** plugin + skills | `plugin/` bundle (`.claude` plugin, `plugin.json`, skills, commands) | `test_plugin_skills.py`, `test_plugin_commands.py`, `test_plugin_pin.py` |
| **M3a** authoring | `plugin/skills/authoring/*` (per-file authoring skills), golden example under `demo/` | `test_authoring_spec.py`, `test_golden_definition.py`, `test_authoring_validation.py` |
| **M4** dashboard | `code/dashboard/` (`data.py`, views, server, encoding) | `test_code_dashboard_seam.py`, `test_code_dashboard_data.py`, `test_code_dashboard_runs.py`, `test_code_dashboard_xss.py`, `test_code_dashboard_cost.py`, `test_code_dashboard_optimize.py` |
| **M4.5** operate | `code/optimize.py`, `code/deploy.py`, `code/control.py` | `test_code_optimize.py`, `test_code_deploy_fleet.py`, `test_code_control.py` |
| **M6** HITL | `code/gate.py`, `code/review.py`, `code/diagnose.py`, PreToolUse hook | `test_code_gate.py`, `test_code_review.py`, `test_code_diagnose.py` |
| **M5** MCP veneer | `code/mcp.py` (thin, 4 meta-tools over the CLI) | `test_code_mcp.py` |

Coordination points reconciled by the orchestrator at integration time only:
`crawfish/__init__.py` exports, `mkdocs.yml` nav, `demo/` shared assets.

## Dependency-ordered waves

- **Wave 1**: foundation (above) → lands + gated on integration.
- **Wave 2** (parallel): M1, M2-core (init→new→sync).
- **Wave 3** (parallel): M2-rest (map/adopt/templates/consent/treelock), M3, M3a-spec+golden.
- **Wave 4** (parallel): M3a per-file skills + eval, M4 dashboard.
- **Wave 5** (parallel): M4.5 operate, M6 HITL.
- **Wave 6** (serial): M5 veneer, full-system QA + live demo.

## ADRs written for this build

- `decisions/0010-jailed-compile-agent-authored-code.md`
- `decisions/0011-observersurface-dashboard-seam.md`
- `decisions/0012-export-relationship-adopt-subsumes-export.md`

(Numbers chosen sequentially after the highest existing ADR; the README's tentative 0008/0009
were placeholders — resolved here.)

## Status ledger

Updated as waves complete. See git log on `craw-code/integration` for the authoritative trail.

| Wave | Milestone | Branch | Built | Integration suite | Gate (sec/arch/qa) |
| --- | --- | --- | --- | --- | --- |
| 1 | foundation (CRA-266/267/268/269/270/243, ADR 0010) | `craw-code/foundation` → merged `e2a37c5` | ✓ | ✓ 1325 passed | gated ✓ (all PASS) |
| 2 | M1 describe/estimate/contracts | `craw-code/m1` | dispatched | — | — |
| 2 | M2-core init/new/sync | `craw-code/m2` | dispatched | — | — |
