# craw code — Implementation Spec (index)

This folder is the deep, implementation-ready spec for **craw code** — the Claude Code
plugin + `craw code` CLI namespace + ledger dashboard that lets an LLM agent author and
operate a Crawfish project. It elaborates every issue in the
[`craw code` Linear project](https://linear.app/crawfish/project/craw-code-7d0986a663db)
and the gaps in [RFC 0001](../../rfcs/0001-craw-code.md) §12.

Read the RFC first for the *why* (the two decisions, the trust-collapse analysis). These
specs are the *how*: per issue — Context, Design, Interface (CLI signatures, `--json`
schemas, types), Acceptance criteria, Test plan, and Security review notes.

## The documents

| Spec | Covers | Milestones |
| --- | --- | --- |
| [01 — Foundations & CLI](01-foundations-and-cli.md) | provenance, jailed compile, test harness; the CLI contracts (schema negotiation, error envelope, describe, estimate, assembly gate, org_id) | M0, M1 |
| [02 — Scaffolding, Plugin & Authoring](02-scaffolding-plugin-authoring.md) | init/new/sync/map/adopt, templates, consent re-entry, tree lock; the plugin package + skills; the file-by-file authoring playbook | M2, M3, M3a |
| [03 — Dashboard, Operate Plane & HITL](03-dashboard-operate-hitl.md) | the ledger dashboard; optimize/deploy/fleet/cancel/resume; the human approval gate, review digest, diagnose | M4, M4.5, M6 |

## The thesis in one paragraph

craw code collapses a trust boundary the framework assumed: Definition code
(`definition.py`, `tools/*.py`, `policies/*.py`) was *authoring-time trusted* because a
human wrote it; now an LLM writes it, possibly steered by fluid (untrusted) data it read.
The spine must therefore be **enforced**, not merely **taught**. Almost every mitigation
is wiring an existing seam — the jail, `ScrubbingStore`, the consent gate, `ObserverSurface`,
`CancelToken`, the secret-broker approval queue, `crawfish.lock`, the `Provenance` ledger —
into the new agent-authoring path. The CLI stays the one execution path; the plugin is
ergonomics; the dashboard is a scrubbed, loopback read-model.

## Dependency order (the keystone graph)

```text
M0  CRA-266 provenance ──┬─> CRA-267 jailed compile ──> M1 describe (CRA-244/271/274)
  (authored_by + taint)  ├─> CRA-277 MCP consent re-entry (M2)
                         ├─> CRA-272 assembly-gate-in-run (M1)
                         └─> UNFILED-GATE promotion/approval (M6)
    CRA-268 loop harness ─────────────────────────────> CRA-265 validation eval (M3a)

M1  CRA-269 schema negotiation ─┐
    CRA-270 craw.error.v1       ├─> every later milestone parses --json & recovers
                                ┘
M2  CRA-245 init ──> CRA-246 new ──> CRA-247 sync ──> CRA-256 authoring spec (M3a)
                                          └─> UNFILED-MAP, UNFILED-ADOPT
M3a CRA-256 authoring spec ──> CRA-258..264 per-file skills ; CRA-257 golden ──> CRA-265 eval
M4  UNFILED-SEAM (ObserverSurface) ──> CRA-252 data layer ──> CRA-253/254 views, UNFILED-XSS/COST
M4.5 (operate verbs) and M6 (HITL/feedback) depend on M4 ledger + M0 provenance
```

The three highest-leverage items: **M0** (provenance + jailed compile + harness — every
later mitigation keys on them), the **M1 contracts** (schema negotiation + error envelope
— everything parses `--json`), and the two responsibility gates, **cost governance**
(CRA-273) and **HITL approval** (UNFILED-GATE). An agent firing `--live` runs and version
promotions with no preview, ceiling, or human checkpoint is the plan's single largest risk.

## Issue inventory

**Filed in Linear (CRA-243…279):**

- M0: 266 provenance · 267 jailed compile · 268 loop harness
- M1: 243 `--json`/exit-code audit · 244 `describe` · 269 schema negotiation · 270 `craw.error.v1` · 271 `describe` redaction · 272 assembly-gate-in-run · 273 `estimate` + project budget · 274 `describe` cost + standalone · 275 org_id threading
- M2: 245 init · 246 new · 247 sync · 276 reference-only templates + lint · 277 MCP consent re-entry · 278 tree lock · 279 idempotent init
- M3: 248 security-spine skill · 249 pipeline mental-model skill · 250 determinism/ledger skill · 251 slash commands
- M3a: 256 authoring spec · 257 golden example · 258 `definition.py` · 259 instructions/agents · 260 tools/taint · 261 mcp/auth · 262 policies+skills · 263 knowledge · 264 fixtures/evals · 265 validation eval

**Unfiled (blocked by Linear free-tier cap — fully specced here, ready to paste):**

| Tag | Title | Milestone | Spec |
| --- | --- | --- | --- |
| UNFILED-MAP | `craw code map` — project discovery graph | M2 | 02 |
| UNFILED-ADOPT | `craw code adopt` + first-run flow + `explain` | M2 | 02 |
| UNFILED-PIN | Pin/version-range/integrity-check the plugin bundle | M3 | 02 |
| UNFILED-OPT | Authoring skill: optimizing a component | M3a | 02 |
| UNFILED-O4 | ADR: export relationship (`adopt` subsumes export) | M3a | 02 |
| UNFILED-SEAM | Dashboard reads via ObserverSurface/Store seam | M4 | 03 |
| UNFILED-XSS | Output-encode + CSP against tainted-ledger XSS | M4 | 03 |
| UNFILED-COST | org-scoped dashboard + aggregate cost-vs-ceiling | M4 | 03 |
| UNFILED-OPTIMIZE | `craw code optimize` (tune/refine/learn orchestrator) | M4.5 | 03 |
| UNFILED-DEPLOY | `craw code deploy` + `fleet` | M4.5 | 03 |
| UNFILED-CONTROL | `craw code cancel` / `resume` | M4.5 | 03 |
| UNFILED-GATE | Human approval/promotion gate (`propose`/`apply`) | M6 | 03 |
| UNFILED-REVIEW | `craw code review` — ledger→authoring digest | M6 | 03 |
| UNFILED-DIAGNOSE | `craw code diagnose <run_id>` | M6 | 03 |

## ADRs to write (the `decisions/` dir does not exist yet — create it)

The repo references ADRs (0002, 0004, 0008) that are not yet present as files. craw code
needs three, to be authored under `docs/architecture/decisions/`:

1. **Jailed compile of agent-authored code** — supersedes the "compiling `definition.py`
   is authoring-time trusted" assumption in `docs/reference/definition.md` for
   agent-authored provenance (CRA-267).
2. **ObserverSurface dashboard seam** (the spec calls it ADR 0008 — *verify number*) —
   the dashboard read-model goes through `ObserverSurface`/`Store`, loopback-only, Python
   aggregation, no concrete backend import (UNFILED-SEAM).
3. **Export relationship** (the spec calls it 0009 — *verify number*) — `craw code adopt`
   subsumes `craw export --claude-code`; disjoint `.claude/` namespaces under a reserved
   `crawfish-*` prefix (UNFILED-O4).

## Open items surfaced during spec-writing (need an owner's call)

- **`assert_build_safe`** lives at `packages/crawfish/src/crawfish/build.py` and wraps
  `crawfish.alg3.assert_no_fluid_to_static_sink` — confirmed present (CRA-272).
- **Cost field name:** the lower bound in `crawfish/cost.py` is **`total_usd`**, not
  `lower_usd`. RFC §7 and all specs now use `total_usd`.
- **`[budget]` project ceiling** (CRA-273) is a *proposed new* `crawfish.toml` section —
  no project-wide ceiling exists today, only the per-run `--budget` → `CostBudget` path.
  Needs config-owner sign-off.
- **Authoring-loop harness** (CRA-268): the framework has a per-run cassette layer
  (`replay.py`) but no transcript-level authoring-loop harness — CRA-268 builds it on top.
  CI's `--bare` vs Agent-SDK choice is unconfirmed (no CI config surfaced).
- **Secret-broker approval-queue module name** (UNFILED-GATE) is marked *(verify name)* —
  confirm the symbol the `(component, sha)` approval record reuses.

## Definition of done (per the repo bar, applied to every issue here)

`ruff` + `mypy` clean; `pytest` green and deterministic (no live model calls —
fixtures / cassettes / `MockRuntime`); the security spine upheld (fluid never reaches a
sink target via the agent loop; agent-authored code is provenance-stamped, jailed at
compile, and gated before `--live`); the demo (`demo/triage-bot/`) exercises the feature
end to end; docs updated.
