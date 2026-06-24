# M5 Review — Surfaces & accuracy (CRA-219..222), branch `cra/m-5`

Reviewer: `review-m5` (combined ARCHITECTURE + SECURITY). Source not edited; no git run.
Diffs reviewed: `cost.py`, `cache.py`, `resolve.py`, `cli.py`, `escalate.py`, `run.py`
and the four test files. All 52 M5 tests pass (`test_single_flight`, `test_cost_interval`,
`test_resolve`, `test_cli_optimize`).

## Verdicts

- **ARCHITECTURE: PASS-WITH-NOTE** — F-6 single-owner law upheld, seams respected, all four
  surfaces are thin orchestration over shipped primitives. Two non-blocking notes (A1, A2).
- **SECURITY: PASS** — single-flight is org-isolated, the lockfile is data-only and
  fail-closed, the cost band never undercounts, and the CLI keeps fluid inputs as data and
  gates recorded/consequential work behind eval-mode freeze.

No BLOCK defects.

---

## OPT-2 — Honest cost interval (CRA-220) — ARCH PASS / SEC PASS

- **F-6 single-owner law: CONFIRMED.** Every per-operator multiplier lives only in
  `cost.py`: `CostShape.refine/escalate/quorum/retry/repair/recurse` each encode the law
  once (`cost.py:319-392`). `escalate.py` and `run.py` carry *doc pointers* back to
  `CostShape.escalate` / `CostShape.repair` and explicitly state they do not re-implement
  the multiplier (diff: `escalate.py:+19..23`, `run.py:+374..377`) — consumers, not
  re-definers. `compose_cost` is the one fold (`cost.py:458-506`).
- **`total_usd` back-compatible: CONFIRMED.** Additive fields default to a `-1.0` sentinel
  and collapse to `total_usd` in `_default_interval` (`cost.py:121-145`); a bare
  `CostEstimate(...)` becomes the degenerate interval `[total, total, total]`. `total_usd`
  is never written by `compose_cost` (`model_copy` updates only the four new fields,
  `cost.py:499-505`). No breaking change to `craw dev --estimate`.
- **expected ≤ worst_case, never undercount: CONFIRMED.** Invariant
  `total ≤ lo ≤ expected ≤ hi ≤ worst_case` is asserted at construction
  (`cost.py:146-160`). With no `measured_rate`, `expected_factor()` returns
  `worst_case_factor()` (`cost.py:312-313`) ⇒ `expected == worst_case`
  (`test_no_rates_expected_equals_worst_case_no_undercount`). The multiplicative nesting
  law is verified at 40× (`Refine(4)∘Escalate(2)∘Quorum(5)`,
  `test_from_runtime_full_refine_escalate_quorum_40x`).
- **Deterministic / pure: CONFIRMED.** `from_runtime` is a static `_inner` traversal,
  models resolved through the shared `resolve_model` (`cost.py:436-455`); no model call, no
  ledger sample during estimation (`test_from_runtime_is_deterministic_no_model_call`).
- **Honesty (SEC): CONFIRMED.** The advertised band is a true upper bound — escalation is
  re-priced on the strong model (`strong_multiplier = strong/base`, `cost.py:343-355`) and
  degrades to the count-based 2× when the primary is free/unknown (never an undercount);
  the band's CI edges are clamped into `[lower, worst]` (`cost.py:493-497`).
- **Note A1 (non-blocking):** `escalate.py`/`run.py` only added doc comments — no runtime
  call into `cost.py`. The single-owner law is enforced by *convention + tests*, not by the
  operators importing the cost owner. Acceptable for F-6 (the cost model is the substrate
  others consume, and a hard import would invert the dependency), but the binding is social.

## OPT-3 — Single-flight caching (CRA-221) — ARCH PASS / SEC PASS

- **One inner.run per key ⇒ one charge: CONFIRMED.** Leader registers an `asyncio.Future`,
  waiters `await existing` and charge `$0` (`cache.py:158-169`); exactly one `_compute`
  runs per key (`test_two_concurrent_identical_calls_collapse_to_one` asserts
  `coalesced==1, misses==1`, budget charged once).
- **Coalesced waiters $0, signature unchanged: CONFIRMED.** `run(request, ctx)` signature is
  untouched; coalescing is a strict refinement of the deterministic key
  (`test_replay_is_bit_for_bit_whether_coalesced_or_not`).
- **Error clears the key / no poisoned future: CONFIRMED.** On exception the future is
  failed for all awaiters and the key is popped in `finally` (`cache.py:178-198`); a retry
  recomputes (`test_inflight_exception_propagates_to_all_and_clears_key`). The `finally` also
  reads `.exception()` to suppress the spurious "never retrieved" warning — correct.
- **Cancel before coalescing: CONFIRMED.** `ctx.cancel_token.raise_if_cancelled()` runs
  before any inflight lookup (`cache.py:156`; `test_cancel_raises_before_coalescing`).
- **TENANCY (gap S2) — SEC CONFIRMED, no cross-org hit.** The coalescing key is
  `_key(request, org_id=ctx.org_id)` (`cache.py:132-141`); two non-default orgs produce
  distinct keys and never coalesce (`test_cross_org_identical_inputs_never_coalesce`,
  `test_cross_org_keys_differ_at_the_cache_key`). A fluid/tainted value can only enter via
  `inputs` (already in the key), never as the `org_id` coordinate — it cannot widen one
  tenant's key onto another's.
  - **Note S-isolation (informational, not a defect):** `_key` folds `org_id` into the hash
    only when `org_id != "local"` (`replay.py:100-101`), so the *local* tenant's coalescing
    key equals the legacy key. This is by design (byte-for-byte legacy reproduction) and is
    safe: `"local"` collides only with `"local"`, and every named tenant gets a distinct
    salted key. Cross-org isolation holds for all `org_a != org_b`.

## OPT-4 — Resolver + lockfile (CRA-222) — ARCH PASS / SEC PASS

- **Pure / deterministic / offline: CONFIRMED.** `resolve` takes an injected
  `CandidateSource`, does no IO/network/model call, walks deps in sorted `(id, version)`
  order, sorts+dedups pins (`resolve.py:272-328`); `closure_sha` is order- and org-
  independent (`test_closure_sha_independent_of_insertion_order`,
  `test_closure_sha_independent_of_org`).
- **SemVer + ranges: CONFIRMED.** Pure-Python comparator, no new third-party dep
  (`resolve.py:69-118`); `^` caret (incl. 0.x breaking-minor), `~` tilde, exact pin all
  tested.
- **Fail-closed: CONFIRMED.** Unknown unit, unsatisfiable range, version conflict (names
  *both* requirers, `resolve.py:311-317`), and cycle (`resolve.py:307-309`) all raise
  `ResolutionError` — each has a test.
- **Lockfile data-only + integrity (SEC): CONFIRMED.** `from_dict`/`read_lockfile`
  reconstruct pins and **re-verify** the recorded `closure_sha`, raising on mismatch
  (`resolve.py:246-269`) and on an unsupported `lockfile_version` — a supply-chain tamper
  gate (`test_tampered_lockfile_fails_closed`, `test_unsupported_lockfile_version_fails_closed`).
  Reading executes **no unit code**: it only parses JSON and hashes pin dicts. A mutated
  summoned unit gets a new content sha ⇒ new `closure_sha` (`test_mutated_unit_gets_new_closure_sha`).
- **Registry/Store boundary: CONFIRMED.** Registry stays discovery-only; pins are
  content-addressed/org-agnostic; the recorded closure carries `org_id` without it entering
  the pins (`resolve.py:206-235`, `Lockfile.org_id`).

## OPT-1 — Optimization-plane CLI (CRA-219) — ARCH PASS-WITH-NOTE / SEC PASS

- **Subcommands bind shipped primitives, no duplicated business logic: CONFIRMED.** `eval`→
  `gate_against_baseline`/`estimate_cost`; `tune`→`Tuner.tune`; `refine`→`Refine`/CL-1;
  `learn`→`LearningLoop.improve`/`rollback`; `guard`→`HouseGuard.synthesize`/`distill`;
  `lock`→`resolve`. `cli.py` orchestrates; cost/search/gate/resolve all live in their owners.
- **`--budget` honored (SEC): CONFIRMED.** `_opt_ctx` projects `--budget` through
  `Budget.as_cost_budget()` onto `ctx.cost_budget` (`cli.py:140-150`); the Tuner stops with
  `stopped_reason="budget"` when `remaining_usd < cost_per_trial` and `CostBudget.charge`
  raises `BudgetExceeded` past the hard ceiling (`tuner.py:648-666,787-789`). No unbounded run.
- **Frozen-Sink / eval-mode gate (SEC): CONFIRMED.** `eval`/`refine` load the Definition,
  call `eval_mode(...)` then `guard_consequential(...)` (`cli.py:227-228,346`), which raises
  `FrozenError` against an unfrozen (train-mode) Definition (`tuner.py:195-209`).
  Optimization commands (`tune`/`learn`) run in train mode over **copies** and drive
  benchmarks/searches — not a consequential Sink. The `--json` surface emits data only;
  no Sink fires from the CLI.
- **Fluid inputs stay data (SEC): CONFIRMED.** The mock responder shapes a typed output
  skeleton and a numeric `score`; the `--predicate` for `guard` goes through `distill` (a
  closed JSON grammar, `GuardGrammarError` on violation — never `eval`/`exec`,
  `cli.py:482-485`); `--until` is parsed by a strict regex DSL, fail-closed
  (`cli.py:379-394`). No path interpolates a CLI arg as an instruction.
- **Audit trail (gap B4): CONFIRMED.** `learn` promote/rollback and a synthesized `block`
  guard emit an `Emission` audit event (`cli.py:192-207,423,448,498-501`), defensively
  wrapped so audit failure never breaks the command — reachable by the AnomalyEngine.
- **Note A2 (non-blocking):** with the default `--cost-per-trial 0.0`, `tune`/`learn` charge
  $0 per trial, so `--budget` alone does **not** produce `stopped_reason="budget"` — the
  budget bites only when paired with a non-zero per-trial cost (or the runtime actually
  charges). This matches the issue's AC (`tune --budget 0.50` is exercised with a per-trial
  cost) and is honest, but an operator who sets only `--budget` on a free mock run will see
  `max_trials`/`exhausted`, not `budget`. Worth a one-line `--help` clarification; not a defect.
- **Note A3 (minor, non-blocking):** `_cmd_eval` loads the baseline via `load_baseline`
  *and* `gate_against_baseline` re-loads it internally (`cli.py:236-244`) — one redundant
  Store read. Correctness unaffected (same org-scoped read); a cleanup, not a bug.

---

## Confirmations (requested checklist)

- Single-flight **org-isolated**: YES — coalescing key embeds `org_id`; cross-org never
  coalesces; fluid input never becomes the org coordinate.
- Lockfile **data-only + fail-closed**: YES — reading executes no code; `closure_sha`
  re-verified; tamper / unknown version / conflict / cycle / unknown unit all raise.
- Cost band **never undercounts**: YES — no measured rate ⇒ `expected == worst_case`;
  invariant `total ≤ lo ≤ expected ≤ hi ≤ worst_case` asserted; escalation re-priced on the
  strong model.
- CLI **honors budget + frozen-Sink**: YES — `--budget` → `CostBudget` hard ceiling;
  `eval`/`refine` gate behind `guard_consequential` (eval-mode freeze); `tune`/`learn` run
  on train-mode copies and fire no Sink.

BLOCK defects: **none.**
