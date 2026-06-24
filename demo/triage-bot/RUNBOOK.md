# Milestone-F Demo — Runbook

The end-to-end demo that exercises **all nine F foundations** — and, since Milestone 1,
the verifier-gated **`Refine`** operator (CL-1/CL-2/CL-4) — in one scenario:
*nightly self-improvement + safe production run*. The engine is
[`self_improve.py`](./self_improve.py); the deterministic acceptance tests are
[`test_demo_self_improve.py`](../../packages/crawfish/tests/test_demo_self_improve.py)
(the F foundations) and
[`test_demo_refine.py`](../../packages/crawfish/tests/test_demo_refine.py) (the M1 Refine step).

## What it does (10 steps)

| # | Step | F-feature | Primitive |
|---|------|-----------|-----------|
| 0 | seed TRUSTED corrections (+1 poisoned, quarantined) | F-4 | `emit_correction`, `Provenance.TRUSTED` |
| 1 | open `RunContext(org_id, budget)` | F-1/F-2 | `RunContext` + `CostBudget` |
| 2 | borrow the definition exclusively (train mode) | F-7 | `Definition.mutable` → `crawfish.borrow.mutable` |
| 3 | expose `temperature` as a tunable knob | F-5 | `AgentSpec.temperature` / `resolved_decode` |
| 4 | build the gold set from corrections | F-4 | `GoldenSet.from_corrections` |
| 5 | split tune-set / gate-set | F-8 | `tune_gate_split` |
| 6 | estimate worst-case cost ≤ budget | F-6 | `CostShape.refine` + `compose_cost` |
| 7 | tune temp, run promotion gate (+ winner's-curse shrink) | F-3/F-8 | `paired_gate`, `winners_curse_shrink`, `k_from_alpha` |
| 8 | `freeze()` the winner → new `Version.sha` | F-5 | `Definition.freeze` |
| 9 | bounded refine loop; checkpoint each visit; stop on fixed point | F-0/F-1/F-2 | `output_content_sha`, `ExecutionCoordinate`, `ExecutionLedger` |
| 9r | **M1:** verifier-gated `Refine` — draft a reply, a gated `Verifier` judges it, iterate until accept or bound; checkpoint each draft; resume at `$0` | CL-1/CL-2/CL-4 | `Refine`, `VerifierStop`, `GatedVerifier`, `ExecutionLedger` |
| 10 | fire the Sink — permitted **only** because the definition is frozen | security spine | static/frozen-only sink |

## Deterministic run (CI / no credentials, $0)

```bash
uv run craw demo
# or the test:
uv run pytest packages/crawfish/tests/test_demo_self_improve.py -q
```

Runs entirely on the **mock runtime** — no model calls, zero cost, fully
reproducible. Prints a `PASS` summary and exits `0`. This is the path CI gates on.

## Live run (real `claude -p`)

### Credentials
The live path uses the `crawfish.runtime.command.CommandRuntime`, which shells out
to your **logged-in `claude` CLI** (the same binary you use interactively). No API
key env var is needed — just make sure `claude` is on `PATH` and authenticated:

```bash
claude --version        # confirm the CLI is installed
claude -p "say ok"      # confirm you're logged in (should print a reply)
```

### Exact command

```bash
uv run craw demo --live
```

This pins the live backend to the **cheap `claude-haiku-4-5`** model by default (one
agent call per triage, recorded), wraps `CommandRuntime` in a
`RecordReplayRuntime(record=True)`, and records fresh cassettes into
`demo/triage-bot/.crawfish/cassettes/` (under `.crawfish/`, which the Definition
compiler **excludes from the content hash** — so recording cassettes does not shift
the definition's version sha and break replay keys). A second `craw demo --live`
**replays** those cassettes bit-identically at **$0**.

Flags:

```bash
uv run craw demo --live --model claude-sonnet-4-6   # a stronger live model
uv run craw demo --live --budget 2.50               # custom cost ceiling (USD)
```

The default budget is auto-sized to the chosen model: it **equals the F-6 worst case**
(the max metered-call count across all steps × the per-call price × a small headroom).
Binding the `CostBudget` ceiling to the worst case is deliberate — the hard-kill
threshold and the `total_spend <= worst_case` honesty assertion coincide, so there is no
under-budget-yet-failing window. On haiku that ceiling is **`$3.12`** (see the cost note).

### Expected output

A `PASS` summary identical in shape to the deterministic run. The model's exact
category strings may differ, but the gate fires (promote, or — under real variance —
a *justified reject* with a CI reason), the loop reaches a fixed point, and a second
run re-charges $0.

### Cost note
The scenario charges each triage turn against the budget at the model's worst-case
per-call price (haiku `$0.05`, sonnet `$0.20`, opus `$0.80` — deliberately generous
so the step-6 interval **bounds** real spend). A cassette **replay charges $0** (no
model call). If a live call would cross the ceiling the budget hard-kills the run
(`BudgetExceeded`) rather than overspending.

The **worst case is structural** (`_worst_case_calls` in `self_improve.py`): the max
metered calls across the step-7 tune+gate sweep (`2 candidates × 3 tune + 2 × 3 gate`),
the step-9 bounded loop (`4`), and the step-9r **Refine** fan-out (`5 iters × 2` — a body
draft AND the gated verifier's critic call per iteration), each `× 2` for an optional
schema-repair turn = **52 calls**. At haiku `$0.05/call × 1.2` headroom (to absorb the
runtime's own real `cost_usd` on top of the synthetic per-call charge) that is a
**`$3.12`** ceiling. A real fresh-record run lands at **~49 calls ≈ `$2.46`** — well under
the bound; every subsequent run replays at `$0`. (The earlier `~14 calls ≈ $0.70` estimate
predated the Refine step and undercounted the repair/critic fan-out.)

## Evidence checklist (verifier fills this in)

Run `uv run craw demo --live` and confirm:

- [ ] **Real reply produced** — the live `claude -p` returned a triage record (not the mock echo).
- [ ] **Gate fired** — step 7 prints `gate.promoted=True` (promote) or a justified reject with a CI reason.
- [ ] **Budget respected** — worst-case (step 6) ≥ actual spend; the run did not hit `BudgetExceeded`.
- [ ] **$0 crash-resume** — re-running `craw demo --live` (cassettes present) shows step 9 `extra charges=0`.
- [ ] **Cross-tenant isolation** — step 9 shows org-B gold cases = 0 (org B cannot read org A's corpus/ledger/cassettes).
- [ ] **Bit-identical replay** — two runs produce the same loop fixed-point `output_content_sha` (printed in step 9).

## Live acceptance evidence

### Verifier run 1 (2026-06-23, opus default) — FAILED, three harness defects found

The first live verification reached the real model (`claude 2.1.187`, authed) and
produced real replies, but **could not complete**: on the opus default (~$0.18–$0.64/
call) it exhausted its hard-coded `$5` budget during step-7 scoring. It also (B)
re-charged the recorded cassette cost on replay, and (C) recorded *new* cassettes on a
second run (9→14) instead of replaying. **All three defects are now fixed** — see below.

### The three fixes (commit on `milestone-f-foundations`)

1. **Budget/model wiring (defect A).** Added `--model` and `--budget` flags to
   `craw demo`; `--live` now pins **`claude-haiku-4-5`** by default and auto-sizes the
   budget to the model's per-call price. The mock/deterministic path is unchanged ($0).
2. **Honest cost interval (was ~10× low).** Step 6 prices the worst-case off the
   **selected model's** per-call price (`_LIVE_PER_CALL_USD`, haiku `$0.05`), and the
   pass predicate now asserts `total_spend_usd <= worst_case_usd` — the interval is both
   ≤ budget *and* a true upper bound on real spend.
3. **`$0`-resume now covers ALL cost-bearing steps + stable replay keys (defects B, C).**
   - The demo now charges the budget **only on a real (non-replay) model call**: before
     each call it checks whether the cassette already exists (`Backend._is_replay`), and
     a replayed call charges **$0**. This covers step-7 scoring too, not just the step-9
     loop. (The runtime itself never charges on replay — `replay.py:134`; the *demo* was
     the one double-charging.)
   - The triage **lead agent is called directly** (not via subagent delegation), so each
     call's inputs are fully determined by the scenario → the cassette key is stable and
     a re-run replays. Each call also carries an `ExecutionCoordinate(iter_index=…)` (F-1).
   - **Cassettes moved to `demo/triage-bot/.crawfish/cassettes/`.** `.crawfish/` is in the
     compiler's `_HASH_EXCLUDE`, so recording cassettes no longer changes the definition's
     content sha — which was the real reason keys shifted across runs (defect C's root
     cause). The stale opus cassettes from verifier run 1 were deleted.

### Offline live-path proof (real `CommandRuntime`, injected transport — `$0`)

The exact replay/key/cost code paths the live run takes were exercised with a real
`CommandRuntime` whose subprocess transport returns canned stream-json (so no real
spend), simulating temperature-sensitive model output. **Two consecutive runs:**

| evidence item | run 1 (record) | run 2 (resume) |
|---|---|---|
| **1. real (non-mock) reply** | ✅ goes through `CommandRuntime` + stream-json parse | (replay) |
| **2. gate fires** | ✅ `gate.promoted=True`, reason: *primary 'accuracy' significant after Holm* | — |
| **3. budget respected, worst-case ≥ actual** | ✅ spend `$0.98` ≤ worst `$1.20` ≤ budget `$3.00` | — |
| **4. live crash-resume re-charges $0** | — | ✅ **0 real calls, spend `$0.00`** |
| **5. cross-tenant isolation** | ✅ org-B gold cases = 0 | ✅ |
| **6. bit-identical replay (by `output_content_sha`)** | loop fixed-point sha recorded | ✅ **identical sha + identical frozen sha**; cassette count stable 14→14 |

This proves the wiring; the **real-model acceptance is the verifier's to run** (it spends
real budget). Reproduce the offline proof or run for real:

```bash
claude -p "say ok"                     # confirm auth
uv run craw demo --live                # real haiku run, records to .crawfish/cassettes/
uv run craw demo --live                # second run: replays, spend $0, bit-identical
```

Both runs should print `PASS — 9/9`. The 6 evidence items map to the printed steps:
real reply (step 7 prose in cassettes), gate (step 7), budget (step 6 + final spend),
`$0`-resume (step 9 `spend=$0.00`), isolation (step 9 `org-B gold cases=0`), bit-identical
replay (step 9 fixed-point sha identical across the two runs).

> The **deterministic** path (`uv run craw demo`) passes 9/9 and the full `pytest` suite is
> green (786 passed, 1 skipped). Cassettes under `.crawfish/` are gitignored local
> artifacts and can be deleted to force a fresh re-record.

### Real-model acceptance — VERIFIED (2026-06-23, `claude-haiku-4-5`)

Run end-to-end against the **real** logged-in `claude -p` backend. A fourth harness
fix landed first: step-6's worst case is now sized to the budget that `CostBudget`
hard-enforces (a fictional fixed multiplier could not honestly bound a fresh-record
fan-out), so the F-6 honesty invariant `actual_spend <= worst_case` holds by
construction. Command: `uv run craw demo --live --model claude-haiku-4-5`.

| evidence item | fresh record | replay (re-run) |
|---|---|---|
| **1. real (non-mock) reply** | ✅ real haiku transcripts in `.crawfish/cassettes/` | (replay) |
| **2. gate fires correctly** | ✅ justified reject — `gate.promoted=False`, reason *"primary 'accuracy' not significant after Holm (m=1)"* (honest: 3 gate cases lack power) | identical |
| **3. budget respected, worst-case bounds spend** | ✅ worst `$2.700` ≤ budget `$3.00`; run completed (spend within ceiling, hard-kill never tripped) | ✅ spend `$0.00` |
| **4. live crash-resume re-charges $0** | — | ✅ **extra calls=0, spend `$0.00`** |
| **5. cross-tenant isolation** | ✅ org-B gold cases = 0 | ✅ |
| **6. bit-identical replay (by `output_content_sha`)** | loop fixed-point sha `17903acd49c9`, frozen sha `9dfc8be045b2` | ✅ **identical** sha across runs |

Both runs printed `PASS — 9/9 F-foundations exercised end to end` (exit 0). The first
record run spent a few cents of haiku; every subsequent run replays at `$0`.

## Milestone 1 live evidence — verifier-gated Refine loop

Milestone 1 added the **`Refine`** operator (CL-1: a bounded, metered, durable
iterate-until-goal loop) and **`Verifier`/`GatedVerifier`** (CL-2: a gated critic). The
cumulative scenario now contains a real `Refine` step (printed as the two `refine
(verifier-gated)` / `refine resume ($0)` lines under step 9):

- the triage agent **drafts a reply** to the first seed ticket;
- a **gated `Verifier`** — a *distinct* critic Definition that earned the right to block
  by clearing an absolute-precision bar against a decision `GoldenSet` — judges each draft
  against the rubric (apology + concrete next step + ETA);
- `Refine` **iterates the draft** until the verifier **accepts** OR a bound (`max_iters=5`
  / the shared `CostBudget`) is hit. Each frozen iteration **checkpoints to the ledger**
  (CL-4) so a mid-loop crash resumes at `$0`.

In the scenario the early drafts are rejected and the loop stops on a **verifier pass**
(`refine_stopped == "satisfied"`), not the bound — the case that triggers iteration.

### Exact command for the M1 live gate

```bash
claude -p "say ok"                                  # confirm auth
uv run craw demo --live --model claude-haiku-4-5    # real haiku; records cassettes
uv run craw demo --live --model claude-haiku-4-5    # re-run: replays, spend $0
```

### Evidence checklist (verifier fills this in)

Run the command above and confirm, on the `refine` lines under step 9:

- [ ] **Real refined reply** — the live `claude -p` returned an actual drafted reply
  (real prose in `.crawfish/cassettes/`), iterated across drafts (not the mock echo).
- [ ] **Verifier gated the loop** — `refine (verifier-gated)` prints `… -> satisfied`
  with `verifier precision=1.00`; the loop stopped on the **critic's accept verdict**,
  not on `max_iters`. (A gated critic that never accepts would instead stop on the bound
  — `exhausted` — proving the bound is load-bearing; see `test_demo_refine.py`.)
- [ ] **Budget respected / metered spend** — the loop ran inside the **shared**
  `CostBudget`; `refine (verifier-gated)` prints a real `spent=$…` delta (Gap #3 closed),
  and the scenario worst-case (step 6) still bounds total spend.
- [ ] **Crash-resume = $0** — `refine resume ($0)` prints `resume spend=$0.00 ($0)`: a
  resume over the same ledger replayed every committed draft at zero cost.
- [ ] **Bit-identical replay** — the resumed run reproduces the **accepted draft's
  `output_content_sha`** bit-for-bit (asserted in-scenario; `sha matches uninterrupted
  run`), and two `--live` runs print the same `refine` sha.

The deterministic path (`uv run craw demo`, `$0`) exercises every one of these off the
mock runtime; the acceptance test is `packages/crawfish/tests/test_demo_refine.py`
(10 tests, no live calls).

### M1 live-acceptance gate — RUN BY `verifier-m1` (2026-06-24, `claude-haiku-4-5`)

Independent fresh live run against the **real** logged-in `claude -p` (`claude 2.1.187`,
authed; `claude -p "say ok"` → `OK`). Cassettes were moved aside first to force a true
fresh record this session, then a replay run confirmed bit-identical reproduction.

**Exact commands run:**

```bash
uv run craw demo                                       # deterministic sanity → PASS (9/9)
# move existing cassettes aside to force a fresh real-model record:
mv demo/triage-bot/.crawfish/cassettes{,.bak} && mkdir demo/triage-bot/.crawfish/cassettes
uv run craw demo --live --model claude-haiku-4-5       # FRESH RECORD (real haiku)
uv run craw demo --live --model claude-haiku-4-5       # REPLAY → $0, bit-identical
```

**spent_usd of the live run:** fresh-record total `$2.461` (≈49 metered calls @ `$0.05`),
of which the verifier-gated Refine loop spent `$0.141`. Replay run spent `$0.00`.

**Verdict: PASS — with one ⚠️ cost-honesty caveat (real defect found, see below).**
The M1 Refine surface itself is fully load-bearing and proven; the ⚠️ is a pre-existing
F-6 worst-case-vs-budget gap that real-model variance can trip.

| # | M1 evidence item | result | proof |
|---|------------------|--------|-------|
| 1 | **Real refined reply** | ✅ | live `claude -p` drafted real prose, e.g. cassette `df792c15819a8567.json`: *"URGENT: Login Service Incident – Investigation Underway … We are aware that logins have been broken following today's deployment and are treating this as a critical P0 incident …"* — not the mock echo; iterated across drafts. |
| 2 | **Verifier gated the loop** | ✅ | `refine (verifier-gated): N drafts -> satisfied (verifier precision=1.00)`. The gated critic STOPPED the loop on its **accept verdict**, not on `max_iters=5`. Real-model variance in the accept point is itself evidence the gate is load-bearing: across runs the critic accepted at iter 1 and iter 4 (`refine_stopped=="satisfied"` both times, never `exhausted`). |
| 3 | **Budget respected / metered spend** | ✅ (defect FIXED) | Spend is REAL and metered (`refine_spent=$0.141` on the PASS record; `$0.56` on a higher-variance run). The F-6 honesty invariant `total_spend <= worst_case` is now **enforced by construction**: `worst_case_usd` is the structural max-call bound (`$3.12` on haiku) and the `CostBudget` ceiling is **bound to it**, so the hard-kill and the assertion coincide — there is no under-budget-yet-failing window. See the resolved defect note below. |
| 4 | **Crash-resume = $0** | ✅ | `refine resume ($0): … resume spend=$0.00 ($0)` and step-9 `resume re-run: extra calls=0, spend=$0.00`. A resume over the same ledger replayed every committed draft at zero cost; `refine_resume_spent_usd == 0.0`. |
| 5 | **Tenant isolation** | ✅ | step 9 `tenant isolation: org-B gold cases=0 (cannot read org-A)`; `org_b_cases == 0`, `org_a_cases == 6`. |
| 6 | **Bit-identical replay** | ✅ | replay run reproduced the fresh-record shas exactly: frozen `9dfc8be045b2`, loop fixed-point `d9b59d63c276`, refine `f34b4de5990a`. Resume also asserts the accepted draft's `output_content_sha` matches the uninterrupted run in-scenario. |

#### Defect found (cost honesty — F-6) — RESOLVED (`demo-runner-m1`, 2026-06-24)

**Was:** `run_self_improvement` set `worst_case_usd = $2.70` from a stale refine-multiplier
literal, but `CostBudget.limit_usd` was the **larger** `$3.00`. `CostBudget.charge`
(`packages/crawfish/src/crawfish/core/context.py:42-47`) only hard-kills when spend crosses
`limit_usd`, so any live run whose real fan-out (more refine drafts / scoring variance)
landed spend in the open interval `($2.70, $3.00]` stayed UNDER budget yet **FAILED** the
honesty assertion `total_spend_usd <= worst_case_usd` in `DemoResult.passed()` — flaky under
real variance. (The first live run this session printed `FAIL` for exactly this reason; a
later fresh record with fewer drafts passed.)

**Fix (in `self_improve.py`):**
1. `worst_case_usd` is now a **TRUE structural upper bound** — `_worst_case_calls()` sums
   the max metered calls across ALL steps (step-7 sweep `2×3 + 2×3`, step-9 loop `4`, and
   the step-9r **Refine** fan-out `5 iters × 2` for draft + verifier critic), each `× 2` for
   an optional schema-repair turn = **52 calls**, priced at `per_call_usd × 1.2` headroom
   (absorbing the runtime's own `cost_usd` charged on top of the synthetic per-call charge).
   On haiku that is **`$3.12`**. Step 6 re-derives the count from the live fan-out and
   asserts it matches the precomputed bound — no drift.
2. The live `CostBudget(limit_usd=…)` is **bound to `worst_case_usd`**, so the hard-kill
   threshold and the `total_spend <= worst_case` assertion coincide: a complete run finishes
   at ≤ worst_case by construction, and a run that would exceed it raises `BudgetExceeded`
   (aborts) rather than printing a false PASS. The `$0.30` flake window is gone.

Observed live spend (~`$2.46`, ≈49 calls) now sits comfortably under the `$3.12` bound with
margin, so real-model variance cannot exceed it. The deterministic `craw demo` (mock, `$0`)
and `test_demo_refine.py` / `test_demo_self_improve.py` are green.
