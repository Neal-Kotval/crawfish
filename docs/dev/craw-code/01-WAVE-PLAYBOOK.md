# craw code — Living Wave Playbook (orchestrator resume doc)

This is the **durable dispatch script** for the autonomous build. If context is compacted or
the session resumes, READ THIS FILE and continue from the first wave whose row in the Status
Ledger (in `00-ORCHESTRATION-LOG.md`) is not `gated ✓`. Never restart a completed wave.

## Invariants (apply to every agent dispatched)
- Each milestone agent works ONLY in its own worktree `../cc-<name>` (branch `craw-code/<name>`),
  branched from `craw-code/integration` AFTER the prior wave merged. cd into the worktree first.
- One owner per file. Ownership is the table in `00-ORCHESTRATION-LOG.md`. All `craw code` source
  goes under `packages/crawfish/src/crawfish/code/`. Verbs self-register via the pkgutil registry
  in `code/__init__.py` — agents NEVER edit `code/cli.py` or top-level `cli.py` (foundation owns them).
- DoD before any agent reports success (run in its worktree root):
  `uv run ruff check .` · `uv run ruff format --check .` · `uv run mypy packages/crawfish/src` · `uv run pytest -q`
  ALL green + deterministic (no live model calls; MockRuntime/cassettes only).
- Each new fluid surface → append a red-team payload to `tests/test_redteam_security.py`.
- Read your spec sections FIRST (paths below). If a spec is wrong, fix the spec with a one-line rationale, then build.
- Product model imports Store/AgentRuntime/ArtifactStore PROTOCOLS only. Structural typing via crawfish.typesystem. No raw SQL outside a Store impl.
- Commit to your branch (Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>). Do NOT push. Report: files changed, CRA issues done + criteria verified, the 4 DoD command tails proving green, red-team payloads, spec corrections, new exported symbols.

## Orchestrator merge/gate loop (between waves)
1. For each finished milestone branch: `git merge --no-ff` into integration (from the main worktree). Resolve only the coordination points (`crawfish/__init__.py` exports, `mkdocs.yml` nav, shared `demo/` assets).
2. Run the FULL suite at integration level (ruff+format+mypy+pytest). If red, dispatch a fix agent in a fresh worktree on integration.
3. Gate: spawn security-agent + architecture-agent + qa-agent on the integrated diff (`git diff d8e232c..HEAD`). Each returns PASS or a BLOCK fix-list. On BLOCK, dispatch a fix agent; re-gate. Only mark the wave `gated ✓` when all three PASS and the suite is green.
4. Update the Status Ledger in `00-ORCHESTRATION-LOG.md`. Remove merged worktrees (`git worktree remove`).

## Spec source paths
- M0/M1 (foundation, describe, estimate, contracts): `docs/specs/craw-code/01-foundations-and-cli.md`
- M2/M3/M3a (scaffolding, plugin, authoring): `docs/specs/craw-code/02-scaffolding-plugin-authoring.md`
- M4/M4.5/M6 (dashboard, operate, HITL): `docs/specs/craw-code/03-dashboard-operate-hitl.md`
- Why + hardening: `docs/rfcs/0001-craw-code.md`. Spine: `docs/architecture/SECURITY.md`, `ARCHITECTURE.md`.

---

## WAVE 1 — foundation  (STATUS: dispatched, agent `foundation`)
1 agent, serial (keystone). Worktree `../cc-foundation`.
Builds: CRA-266 provenance, CRA-267 jailed compile (+ADR 0010), CRA-268 harness, CRA-270 craw.error.v1,
CRA-269 schema negotiation, CRA-243 --json/exit-code audit. Establishes `code/__init__.py` (registry+envelope+
schema+exit codes+provenance record), `code/cli.py`, wires `code` into top-level `cli.py`.
Tests: test_file_provenance, test_jailed_compile, test_authoring_harness, test_error_envelope, test_schema_negotiation, test_cli_json_coverage.

## WAVE 2 — parallel (after Wave 1 gated)
Dispatch BOTH at once, each own worktree branched from integration:
- agent `m1` (worktree ../cc-m1): CRA-244 describe → CRA-271 redaction, CRA-274 cost+standalone; CRA-272 assembly-gate-in-run (extends build.py); CRA-273 estimate + [budget] crawfish.toml section; CRA-275 org_id threading.
  Files: code/describe.py, code/estimate.py; extends build.py. Tests: test_describe, test_describe_redaction, test_describe_cache, test_code_estimate, test_run_assembly_gate, test_code_org_isolation.
- agent `m2core` (worktree ../cc-m2): CRA-245 init → CRA-246 new → CRA-247 sync. Files: code/init.py, code/new.py, code/sync.py. Tests: test_code_init, test_code_new, test_code_sync.
  NOTE: m2core continues into Wave 3 for the rest of M2 (same owner, same worktree, serialized) — do NOT spawn a second M2 owner.

## WAVE 3 — parallel (after Wave 2 gated)
- agent `m2core` (resume, ../cc-m2): CRA-276 reference-only templates+lint, CRA-277 MCP consent re-entry, CRA-278 tree lock, CRA-279 idempotent init, UNFILED-MAP (`code/map.py`), UNFILED-ADOPT + `explain` (`code/adopt.py`) + ADR 0012 export relationship.
  Files: code/templates.py, code/lint.py, code/map.py, code/adopt.py. Tests: test_code_lint, test_code_consent_regate, test_code_tree_lock, test_code_init_reentrant, test_code_map, test_code_adopt, test_code_explain, test_claude_namespace. ADR: 0012-export-relationship-adopt-subsumes-export.md.
- agent `m3` (../cc-m3): CRA-248/249/250 skills (security-spine, pipeline mental-model, determinism/ledger), CRA-251 slash commands, UNFILED-PIN plugin integrity. Files: `plugin/` bundle (plugin.json, skills/, commands/). Tests: test_plugin_skills, test_plugin_commands, test_plugin_pin.
- agent `m3a-spec` (../cc-m3a): CRA-256 authoring spec, CRA-257 golden example. Files: plugin/skills/authoring/ spec doc + golden definition under demo/. Tests: test_authoring_spec, test_golden_definition.
  NOTE: m3a continues into Wave 4 (same owner). UNFILED-OPT (optimizing skill) + UNFILED-O4 handled here/Wave4.

## WAVE 4 — parallel (after Wave 3 gated)
- agent `m3a` (resume, ../cc-m3a): CRA-258 definition.py skill, 259 instructions/agents, 260 tools/taint, 261 mcp/auth, 262 policies+skills, 263 knowledge, 264 fixtures/evals, 265 validation eval (needs harness+golden), UNFILED-OPT optimizing skill. Tests: test_authoring_validation (+per-skill). May parallelize internally via sub-agents (258-264 independent).
- agent `m4` (../cc-m4): UNFILED-SEAM ObserverSurface dashboard read-model (+ADR 0011) → CRA-252 data layer → CRA-253/254 views, UNFILED-XSS output-encode+CSP, UNFILED-COST org-scoped aggregate cost-vs-ceiling. Files: code/dashboard/ (data.py, views, server, encoding). Tests: test_code_dashboard_seam, test_code_dashboard_data, test_code_dashboard_runs, test_code_dashboard_xss, test_code_dashboard_cost, test_code_dashboard_optimize. ADR: 0011-observersurface-dashboard-seam.md.

## WAVE 5 — parallel (after Wave 4 gated)
- agent `m45` (../cc-m45): UNFILED-OPTIMIZE (`code/optimize.py` — tune/refine/learn orchestrator over existing tuner/refine/learning), UNFILED-DEPLOY+fleet (`code/deploy.py` over existing deploy.py), UNFILED-CONTROL cancel/resume (`code/control.py` over CancelToken). Tests: test_code_optimize, test_code_deploy_fleet, test_code_control.
- agent `m6` (../cc-m6): UNFILED-GATE PreToolUse hook + propose/apply human approval (`code/gate.py`, reuses secret-broker approval queue), UNFILED-REVIEW ledger→authoring digest (`code/review.py`), UNFILED-DIAGNOSE (`code/diagnose.py`). Tests: test_code_gate, test_code_review, test_code_diagnose.

## WAVE 6 — serial (after Wave 5 gated)
- agent `m5` (../cc-m5): thin MCP veneer — 4 fixed meta-tools over the CLI (`code/mcp.py`). Test: test_code_mcp.
- Orchestrator: integrate `mkdocs.yml` nav (craw code guide group after Operate + reference pages), reconcile `crawfish/__init__.py` exports, write/finish all guide+reference docs (per writing-docs.md), build demo/craw-code-tour/ end-to-end (mock), run live `claude -p` smoke test → demo/craw-code-tour/TRANSCRIPT.md (OUT of pytest), full integration suite green.
- Final PR: `craw-code/integration` → `main` with issue→commit map, ADRs, docs, demo + transcript. Then merge.

## Standing specialist prompts (re-spawn per gate with the diff)
- security-agent: audit the diff against docs/architecture/SECURITY.md spine + trust-collapse mitigations (provenance stamp, jailed compile, consent re-gate, fluid≠sink-target, secrets-by-ref, --live gate). Verify each new fluid surface has a red-team payload. Return PASS or BLOCK + exact fix-list.
- architecture-agent: audit seam discipline (protocols-not-backends, structural typing, no raw SQL outside Store, registry not hand-wired dispatch, --json schema versioning, ADR coverage). Return PASS or BLOCK + fix-list.
- qa-agent: run full suite + demo; check each issue's acceptance criteria from the spec; confirm determinism. Return PASS or BLOCK + fix-list.
