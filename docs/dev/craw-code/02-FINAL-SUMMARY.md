# craw code — Final Build Summary (integration → main)

This is the top-level summary for the `craw-code/integration` → `main` PR: what shipped,
every issue mapped to the commit(s) that closed it, the gates that passed, the spec
corrections made, and an honest accounting of what is and isn't done.

## What shipped

`craw code` — a Claude Code plugin + a `craw code` CLI verb family + a scrubbed ledger
dashboard that lets an LLM agent **author and operate** a Crawfish project, with the
security spine *enforced* (not merely taught) across the new agent-authoring trust
boundary. Built in 6 dependency-ordered waves, each merged to `craw-code/integration` only
after the full suite was green and three independent specialists (security, architecture,
QA) signed off.

**24 `craw code` verbs**, all self-registering through an auto-discovered pkgutil registry
(so one-owner-per-file held across 9 parallel milestones): `init, new, sync, describe,
estimate, lint, map, adopt, explain, grant, dashboard, validate-authoring, optimize,
deploy, fleet, cancel, resume, propose, apply, reject, review, diagnose, schema, mcp`.

Final suite at integration: **1650 passed, 1 skipped** (pre-existing), `ruff` + `ruff
format` + `mypy --strict` clean, deterministic (no live model calls — MockRuntime /
cassettes / FakeJail only).

## Issue → commit map

**M0 foundation (keystone):** CRA-266 provenance · CRA-267 jailed compile · CRA-268
authoring harness — `012bea7`, merged `e2a37c5`. ADR 0010.

**M1 CLI contracts:** CRA-243 `--json`/exit-code audit · CRA-269 schema negotiation ·
CRA-270 `craw.error.v1` — `012bea7`. CRA-244 describe · CRA-271 redaction · CRA-272
assembly-gate-in-run · CRA-273 estimate + `[budget]` · CRA-274 describe cost/standalone ·
CRA-275 org_id — `a0ad96b`, seam fix `a4172e3`, merged `1e101f1`.

**M2 scaffolding:** CRA-245 init · CRA-246 new · CRA-247 sync — `8b96de9`, merged
`1f89862`; policy-template fix `8590e0f`. CRA-276 lint · CRA-277 consent re-gate · CRA-278
tree lock · CRA-279 idempotent init · UNFILED-MAP · UNFILED-ADOPT — `a99e0cc`, exit-code
fix `6e1e6e7`, merged `ddbf146`. ADR 0012.

**M3 plugin:** CRA-248/249/250 skills · CRA-251 slash commands · UNFILED-PIN bundle
integrity — `ce307f7`, merged `eecca73`.

**M3a authoring:** CRA-256 authoring spec · CRA-257 golden — `1dcab53`, merged `92b72c7`.
CRA-258..264 per-file skills · UNFILED-OPT · CRA-265 validation eval — `e031e8c`, verb
`8a0d37a`, merged `94d3b44`.

**M4 dashboard:** UNFILED-SEAM · CRA-252 data · CRA-253/254 views · UNFILED-XSS ·
UNFILED-COST — `b3efd86`, schema fix `295ed72`, merged `7f9f64f`/`a0b7541`. ADR 0011.
Lineage-determinism fix `9ffaa87`.

**M4.5 operate:** UNFILED-OPTIMIZE · UNFILED-DEPLOY (+fleet) · UNFILED-CONTROL
(cancel/resume) — `5bfaa5b`, exit-code fix `a851393`, merged `340ba59`.

**M6 HITL:** UNFILED-GATE (propose/apply/reject + PreToolUse hook) · UNFILED-REVIEW ·
UNFILED-DIAGNOSE — `496c004`, merged `011dae1`.

**M5 MCP veneer:** the thin 4-meta-tool surface over the CLI — `906e905`, merged `3bea9dd`.

**Security fixes caught by the gate (load-bearing):** Wave-3 sec BLOCK — `adopt`/`map`/
`consent`/`sync` executed untrusted authored code **unjailed**; routed all through
`load_definition_jailed` + exfil red-team tests — `077e654`, `24a237a`.

**Docs:** 7 guide pages + 2 reference pages + mkdocs nav — `503c14a`. Plus
`docs/guide/craw-code/writing-docs.md` (contributor house-style guide), RFC §10 resolved,
and this orchestration log set.

The 14 **UNFILED-*** gaps had no Linear issue (free-tier cap) and were built from their
specs in `docs/specs/craw-code/`; each is closed by the commit(s) above.

## ADRs written

- **0010** — jailed compile of agent-authored code (supersedes the trusted-compile
  assumption in `docs/reference/definition.md`).
- **0011** — ObserverSurface dashboard seam (loopback, scrubbed, Python aggregation,
  protocol-only).
- **0012** — export relationship (`adopt` subsumes `craw export --claude-code`; disjoint
  `.claude/` namespaces).

## Gates that passed

Every wave: full DoD (ruff + format + mypy + pytest) green at integration **before** the
gate, then security + architecture + QA each returned PASS (or BLOCK → fix → re-verify).
Highlights: the security gate **caught the unjailed-execution trust-collapse regression**
(Wave 3) and **adversarially audited the HITL approval gate** (Wave 5), confirming an agent
cannot self-approve and an approval cannot be replayed across a different `(component, sha)`.

## Spec corrections made (with rationale)

- Cost lower-bound field is `total_usd`, not `lower_usd` (RFC §7 + specs aligned).
- `new policy` template must use `Policy(kind=PolicyKind.…)` — core `Policy` has no
  `description` field (caught by the golden; would have failed `load_definition`).
- Granular CLI sub-codes (5/6/7/8/9) ride in `detail.exit`; the **process** exit stays in
  the closed 0–4 table — a contract the architecture gate enforced repeatedly.
- Plugin integrity pin lives in `crawfish.plugin.lock`, not `crawfish.lock` (the latter is
  a pip-requirements file consumed by the container build).
- Tree-lock rides Store `kv_get`/`kv_set` (no `borrow` primitive exists on the protocol).
- The dashboard `_lineage_for` orders by parent-chain depth, not Store row order (the
  `list_records` `updated_at` sort had no tie-breaker → a real flaky test).

## Honest accounting — follow-ups (non-blocking)

- The shipped jail backend is `SandboxPolicy(kind="fake")` (FakeJail) — *certifies-then-
  imports in-process*. True out-of-process OS isolation is a backend swap behind the
  existing `select_jail` seam; required before any real `--live` host-execution path.
  Candidate for a dedicated ADR.
- `new mcp --dir <project-root>` writes an inert top-level MCP that escapes the consent
  scan (not a live hole — it's never wired into a Definition's capability surface); should
  require a Definition target.
- Minor missing-assertion coverage noted by QA (CRA-278 `craw doctor` torn-tree check,
  UNFILED-MAP edge structure, CRA-279 `--upgrade` re-pin field); behavior verified, tests
  to backfill.

## Linear

Tracked under the `craw code` project (team CRA). The board was treated as best-effort;
the source of truth is `docs/specs/craw-code/` and this commit trail. The 14 UNFILED-*
gaps remain unfiled (free-tier cap) and are closed here per their specs.
