# Phase 2 build log (CRA-170)

Orchestrator-maintained running log of what shipped, decisions, and open items for the
Phase 2 epic. Per-issue detail lives in the Linear issues; this is the merge/ordering record.

## Conventions

- Build in dependency order (pinned comments on CRA-170). **CRA-184 contracts merge first, alone.**
- Per-issue gate: `ruff` + `ruff format --check` + `mypy --strict` + `pytest -q` green & deterministic;
  security spine upheld; a demo exercises it; docs + ADR updated; all VETO reviewers pass.
- One owner per hot file (`run.py`, `output.py`, `runtime/base.py`, `cost.py`, `secrets.py`,
  `metrics.py`, `cli.py`). Serialize contended files.

## File-ownership map (from CRA-170 review comments)

| Hot file | Owner order |
| -- | -- |
| `run.py` | CRA-171 → CRA-172 (serialize); CRA-174 rebases after |
| `output.py` | CRA-172 owns; CRA-174 rebases after |
| `runtime/base.py` | CRA-184 (contracts) → CRA-173 |
| `cost.py` | `resolve_model` extracted in CRA-184 → CRA-182 builds on it |
| `metrics.py` | CRA-172 (removes hack) → CRA-175 expands |
| `secrets.py` | CRA-178 → CRA-180 |
| `cli.py` | CRA-180 / CRA-181 (distinct subcommands; coordinate) |

## Status

### ✅ CRA-184 — Interface freeze (contracts) — phase-2a — DONE (pending merge)
Branch: `nealkotval/cra-184-...`. Types + stubs + tests only, no behavior.

Shipped:
- `emission.py` — frozen `Emission` + closed `EmissionKind` (10 kinds) + `REQUIRED_ATTRS`
  (frozen MappingProxy) + `EMISSION_SCHEMA_VERSION`. `missing_attrs`/`is_valid` real;
  `to_event`/`from_event` stubs (CRA-171). `tainted` propagation field present.
- `validation.py` — `ValidationFailure` enum, frozen `ValidationError`, frozen `StructuralDiff`
  (`.equal`); `validate_output` / `validate_inputs` / `structural_diff` stubs (CRA-172).
- `provider.py` — `resolve_model` (single shared resolver, **real**), `Provider` protocol
  (runtime_checkable), frozen `ModelsConfig` + `ProviderPolicy`. `cost._resolve_model` and
  `CommandRuntime._resolve_model` now delegate to it (behaviour-identical; de-duplicated).
- `secrets.py` — frozen `Grant` dataclass (consumed by CRA-178/180).
- `__init__.py` — all symbols exported + in `__all__`.
- Tests: `tests/test_interface_freeze.py` (18 tests) — taxonomy closure, frozenness, stub
  honesty, resolver parity with legacy call sites, protocol structural check.
- Docs: ADR 0013 (taxonomy / inline Output.value / single resolve_model);
  `docs/architecture/emission-taxonomy.md`.

DoD gate: ruff clean · ruff format clean · mypy strict clean (70 files) · pytest 374 passed.

Decisions (ADR 0013): EmissionKind closed+versioned; `Output.value` inline (ArtifactRef
opt-in, single deref point); one `resolve_model` (no hardcoded vendor default in provider.py).

### ✅ CRA-171 — Typed emission substrate — phase-2a — DONE (pending merge)
Branch: `nealkotval/cra-171-...`. Implements the behavioural half of the CRA-184 emission contract.

Shipped:
- `emission.py` — `to_event`/`from_event` (typed + legacy back-compat shim, never raises),
  `emit` (per-run volume cap; drop-only, rotation deferred to CRA-191), `read_emissions`.
- Routed all existing telemetry through `Emission`: `runtime/base._emit_telemetry` → MODEL,
  `run.py` → RUN_START/RUN_FINISH (taint from `Output.tainted`), `nodes/sink` → SINK,
  `runtime/context_strategy` → COMPACTION, `observe` → OBSERVER.
- `inspector.py` reads the typed stream via `read_emissions`.
- **Cost-consumer regression fixed** (bug-reviewer BLOCKER): the new emission shape
  (`kind="model"`/`"run_finish"`, cost under `attrs`) broke `cost.spent_today`/`_event_cost`.
  Fixed: `_event_cost` reads nested `attrs`; `_COST_BEARING_KINDS` accepts typed+legacy kinds;
  new `_parse_event_ts` handles ISO-string AND epoch-float ts. Tests rewritten to be load-bearing.
- `emit`/`read_emissions` exported. Demo: `test_demo_run_produces_typed_emission_stream` runs
  triage-bot on MockRuntime; secret-never-in-ledger test through ScrubbingStore.

DoD gate: ruff clean · format clean · mypy strict clean (70 files) · pytest 390 passed.
Reviews: Security & Architecture **APPROVE**; Bug **APPROVE** (after cost fix re-review).

Non-blocking follow-ups (→ CRA-191): `from_event` typed/legacy disambiguation is implicit
(known-kind + `attrs` dict) — not reachable from real producers but a latent trap; `emit`'s
`max_per_run` guard is wired but unused by emit sites (O(n)/emit when enabled — revisit at rotation).
Follow-up (→ emit sites): stamp real `ts` on MODEL/RUN_FINISH so per-day cost filtering is exact
(currently `ts=0.0` ⇒ always counted, never undercounts).

### ✅ CRA-172 — Typed input & output validation — phase-2a — DONE (pending merge)
Branch: `nealkotval/cra-172-...`. Implements the frozen `validate_output`/`validate_inputs`/`structural_diff`.

Shipped:
- `validation.py` — registry-driven validator (NO new dep): tolerant parse-from-text (code-fence
  strip + outermost balanced `{...}`/`[...]`, escape-aware), TypeDef walk (PRIMITIVE/RECORD/LIST/
  OPTIONAL), `canonicalize()` (sorted keys → deterministic equality/diffs). New `ValidationAction`
  enum (RETRY/REPAIR/DEAD_LETTER) — distinct from the frozen `ValidationFailure` reasons.
- `run.py` — typed input validation BEFORE any model call (`InputValidationError`); typed
  `Output.value` (not string); `ValidationAction` policy; REPAIR re-prompt is metered + now has a
  **pre-flight budget guard** (skips the extra call when `cost_budget.remaining_usd<=0` → dead-letter);
  tool-result run forces `tainted=True` (injection vector) even with all-static inputs.
- `metrics.py` — typed values read directly (JSON-decode hack demoted to no-schema fallback).
- `nodes/router.py` — classifier opts out of input-type/output-schema validation (over-binds free text).
- demo/triage-bot gains a typed `Triage` RECORD output (end-to-end MockRuntime assert: value is a dict).

DoD gate: ruff clean · format clean · mypy strict clean (70 files) · pytest 414 passed.
Reviews: Bug **APPROVE**, Security & Architecture **APPROVE** (full 7-point spine pass).
Back-compat: no-schema Definitions keep `Output.value` as the raw string; all `.value` consumers
(aggregator/eval/team/sink/source) verified dict-safe.

Non-blocking follow-ups (→ CRA-175 evals/golden-set): `validate_output` keeps only the FIRST
top-level JSON object when a model emits several (best-effort, no signal); `ValidationFailure.EMPTY_SCHEMA`
is a reserved-but-unemitted reason. Golden-set string→typed migration helper to be owned by CRA-175.

### ✅ CRA-191 — Store schema migration mechanism — phase-2a — DONE (pending merge)
Branch: `nealkotval/cra-191-...`. Versioned migrate-on-open for SqliteStore.

Shipped: `store/migrations.py` (`Migration`, ordered `MIGRATIONS`, `CURRENT_SCHEMA_VERSION`,
`StoreMigrationError`, `apply_migrations`, `RECORD_UPCONVERTERS`/`upconvert_record`). `PRAGMA
user_version` + apply-on-open; downgrade refused; baseline (v1) + a real v2 (index on
`events(org_id,run_id)`); read-path per-kind up-converters (generalizes `Emission.from_event`).
ADR 0014 + ARCHITECTURE.md migration-authoring contract.

**Review-surfaced MAJOR fixed:** `with conn:` does NOT wrap DDL in a transaction under stdlib
sqlite3 → the "rolls back on error" contract was false. Fixed with explicit `BEGIN`/`COMMIT`/
`ROLLBACK` around each migration (covers DDL; `user_version` is header-stored & transactional),
+ a regression test proving a failing multi-statement migration rolls back fully and leaves
`user_version` unchanged.

DoD gate: ruff clean · format clean · mypy strict clean (71 files) · pytest 421 passed.
Note: emission retention/rotation + `max_per_run` wiring explicitly deferred (separate concern).

### ✅ Parallel wave (isolated worktrees, merged sequentially) — phase-2a — DONE
All four built concurrently off `main`, each through its review gauntlet, merged in order. Final integrated gate: ruff/format/mypy-strict clean (73 files) · **pytest 471 passed**.
- **CRA-181** craw auto-dashboard — `craw dashboard` (loopback 7879) renders any `Emission.attrs` key generically; taint surfaced; DNS-rebind guard. Review APPROVE.
- **CRA-185** test-fixture & determinism harness — `canned_transport`, per-provider stream-json fixtures, injection fixtures, `assert_taint_conformance` (load-bearing, negative-tested). Review APPROVE.
- **CRA-173** unified provider layer — `ProviderRuntime` (failover + `ProviderPolicy` gating + alias-expand-all-entries + uniform telemetry/cost), `MockProvider`/`ClientProvider`. **Security sequencing upheld: zero egress / zero `.env` key onboarding; credential acquisition deferred to CRA-178.** Review APPROVE.
- **CRA-175** evals + metrics expansion — typed-value metrics (FieldExactMatch/SetOverlap/NumericTolerance/SchemaConformance/StructuralMatch), golden-set string→typed migration, deterministic LLM-judge, multi-JSON guard. Review APPROVE + MINOR (test registry collision) hardened post-merge.

### ✅ CRA-187 / CRA-190 / CRA-192 — phase-2a — DONE (merged)
- **CRA-187** (spike): ADR 0015 — **in-house deterministic search, NOT DSPy** (DSPy makes live LM calls, bypasses the AgentRuntime seam, can't be replay-deterministic). Gates CRA-176 with concrete guidance.
- **CRA-190** anomaly/auto-halt: `anomaly.py` rule engine over the Emission stream; tiered FLAG/ALERT/HALT; kill-switch trips CancelToken + forces CostBudget over ceiling. Non-spoofable (acts on typed signals only). Review APPROVE + 2 fast-follows (unconditional HALT at zero spend; zero-budget guard).
- **CRA-192** model aliases: `crawfish.toml [models]` → `ModelsConfig` threaded to runtime+cost; Claude-first back-compat preserved; alias→alias rejected at load. Review pending → merged on green gate.

**Phase-2a status: 11/12 merged** (184, 171, 172, 191, 185, 173, 192, 175, 187, 181, 190). Only **CRA-176 (Tuner)** remains — in progress. Integrated gate on `main`: ruff/format/mypy-strict clean (74 files) · **pytest 497 passed**.

**Orchestration note:** parallel worktree agents are fast but git-state-fragile — a doc-only spike run in the *main* checkout concurrent with merges, plus worktree `uv sync`, tangled HEAD/branch refs and re-pointed the editable install once. Recovered each time (worktree prune + `uv sync` + verify `crawfish.__file__`). Lesson: keep spikes/doc-only work OUT of the main checkout during merges; one big-issue worktree at a time.

### ✅ Phase-2b core wave — DONE (merged, 574 passed)
- **CRA-183 / CRA-188** spikes: ADR 0011 (do-not-adopt ruvLLM/rvagent → seeded LocalHTTPProvider + wasmtime-py; no escalation) · ADR 0016 (Jail abstraction).
- **CRA-179** sandboxed pipelines: `jail.py` — `Jail` ABC (FakeJail + BwrapJail/SeatbeltJail + NoJail), `select_jail`. Static-only `allow_paths`/`allow_net` (rejected before spawn in all backends), folder-escape + egress denial (real, non-vacuous), `JAIL_VIOLATION` audit emissions (secret-free), taint re-tag across boundary, registry rehydration. Review APPROVE + 2 fixes (network-granted output tainted on real backends; backends bind RO system+interpreter so they're actually usable, integration tests now meaningful).
- **CRA-174** transferable typed Context: `Context`/`ContextEntry` artifact threading through team.py (replaces lossy string threading); carry strategies (Full/Recency/TypedFields/Summary); taint+lineage preserved (survives compaction); ArtifactRef single-deref per ADR 0013. Review APPROVE.
- **CRA-182** cost/routing: `RoutingPolicy` (first-match, via shared `resolve_model` — no drift, `estimate_cost` matches runtime), `CachingRuntime` over RecordReplay (hit=$0), credential-free `LocalHTTPProvider` (mocked, no egress). Review APPROVE.

**Status: 17/22 done.** Remaining: CRA-178 (★ secret broker), CRA-180 (consent), CRA-189 (red-team demo), CRA-177 (learning), CRA-186 (integration gate).

### ✅ CRA-178 (★ secret broker) / CRA-177 (learning) — phase-2b — DONE (merged, 596 passed)
- **CRA-178** secret broker: `SecretBroker` keeps values out-of-band; nodes get a value-free `LeaseHandle`; injection at egress; Grant-gated, static-only, redirect-proof (host re-checked vs broker table), SECRET_LEASE audit (ref not value), fail-closed approval queue. **Security review REJECT→fixed**: the MCP leak was still open (`build_mcp_config` embedded the secret VALUE in the agent-readable config; brokered builder had zero callers) → fixed to reference-by-name only, value appears nowhere (tested). Residual: transparent network interception depends on jail/network layer (documented).
- **CRA-177** learning agents: `LearningLoop` composes the Tuner; two-gate promotion (Tuner regression-gate + `gate_against_baseline` vs stored baseline) — never promotes a worse candidate; content-hashed reversible lineage with `rollback`; autonomy ceiling inherited. Review APPROVE.

**Status: 19/22 done.** In flight: CRA-180 (consent + grant manifest), CRA-189 (red-team demo). Then CRA-186 (integration gate) closes the epic.

## Review-surfaced notes for downstream issues
- **CRA-185** (taint-conformance suite): add explicit acceptance criterion — `tool`/MCP-result
  emissions MUST be `tainted=True`. The Emission envelope *carries* taint; producers enforce it.
  (Security reviewer, CRA-184 gauntlet.)
- **CRA-192** (model aliases): reject alias→alias chains at config-load (`resolve_model` is
  single-hop by contract; a 2-hop alias yields a non-concrete id that fails at runtime).
- **CRA-173** (provider/failover): when failover lands, alias-expand *all* entries of a model
  list, not just the primary `model[0]`.

## Open items / deferrals
- Audit-log tamper-evidence (hash-chain) and cross-org data governance: noted on CRA-171/173
  as "decide or defer" — not blocking Phase 2; conscious deferral.
