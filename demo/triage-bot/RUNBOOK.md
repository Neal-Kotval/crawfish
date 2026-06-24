# Milestone-F Demo — Runbook

The end-to-end demo that exercises **all nine F foundations** in one scenario:
*nightly self-improvement + safe production run*. The engine is
[`self_improve.py`](./self_improve.py); the deterministic acceptance test is
[`packages/crawfish/tests/test_demo_self_improve.py`](../../packages/crawfish/tests/test_demo_self_improve.py).

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

The default budget is auto-sized to the chosen model (`max($3, 20 × per-call price)`),
so the full 10-step flow completes for cents on haiku.

### Expected output

A `PASS` summary identical in shape to the deterministic run. The model's exact
category strings may differ, but the gate fires (promote, or — under real variance —
a *justified reject* with a CI reason), the loop reaches a fixed point, and a second
run re-charges $0.

### Cost note
The scenario charges each triage turn against the budget at the model's worst-case
per-call price (haiku `$0.05`, sonnet `$0.20`, opus `$0.80` — deliberately generous
so the step-6 interval **bounds** real spend). A cassette **replay charges $0** (no
model call). If a live call is unexpectedly expensive the budget hard-kills the run
(`BudgetExceeded`) rather than overspending. On haiku the whole flow is ~14 calls
≈ `$0.70` against a ~`$1`+ auto budget.

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
