# Roadmap

Where Crawfish is and where it's going. This is the public, outside-in view; it
describes capabilities, not internal tracker IDs. For claimable work and discussion,
see the project's GitHub **Issues** and **Discussions**.

<!-- TODO(maintainer): link the real Issues/Discussions URLs once the repo slug is set
     (e.g. https://github.com/Neal-Kotval/crawfish/issues). -->

## Phase 1 — the local trust loop (shipped)

Crawfish runs an end-to-end pipeline locally with **no hosted dependency and no API
key** (a mock runtime drives the demo). The loop:

> A multi-item **Source** fans out → a **Definition** team runs per item via `claude -p`
> → an **Aggregator** reduces → a **Router** branches → a **Sink** writes.

…and it's **typed, versioned, and benchmarked**, with retries, a dead-letter queue, and
crash-resume. What's in the box today:

- **Authoring as directories** — a directory compiles to a typed Definition; single- and
  multi-agent teams; MCP tool access; pluggable context-window management.
- **Typed structural IO + versioning** — structural type compatibility (never string
  equality), freezable/versioned artifacts and lockfiles.
- **Three swappable seams** — `AgentRuntime`, `Store` (WAL SQLite: tenancy, idempotency,
  event ledger), `ArtifactStore`. The product model imports protocols, never backends,
  so cloud + scale stay a driver swap, not a rewrite.
- **The full node set** — Source, Sink (idempotency, approval gate, static targets),
  Filter/Router/Classifier, Aggregator, Memory, durable Run.
- **Pipelines** — fan-out/fan-in Batch, rule-based scheduling, execution-state ledger,
  retries + dead-letter + replay.
- **Measurement & knowledge** — metrics, rubrics, benchmarks against golden sets, eval
  data lifecycle, cost preview + budgets, a streaming run inspector.
- **Operate, observe & integrate** — `craw deploy` (always-on detached supervisor,
  auto-restart, ledger resume), an observer primitive (rules + LLM judge), `craw manage`,
  a loopback-only `craw visualize` dashboard, `craw export --claude-code`, and a
  configurable project structure with `craw doctor`.
- **Security spine** — fluid (untrusted) inputs reach the model as data, never
  instructions; consequential Sink targets and idempotency keys are static-only; secrets
  resolve by reference and are never logged or in-prompt.
- **Ship surface** — `pip install` → `craw init` → a 5-minute zero-key demo;
  `craw build` → container; a MkDocs docs site; an API-stability contract (stable /
  experimental / deprecated tiers + semver).

## The agent language — control plane, composition surface, tunable-ML library + tameness layer shipped (in progress)

Phase 2 includes a larger bet: an **agent language** where composition operators
(Refine, Program, Quorum, Escalate) and a Tuner make agents self-improving over your
data. The first four milestones — the **control plane**, the **composition surface**, the
flagship **tunable-ML library**, and the **tameness layer** that bounds the one stochastic
primitive — have now shipped on top of the foundational primitives:

- **`Refine` — a bounded, metered, durable iterate-until-goal loop.** Run a producing
  Definition, check each frozen Output against an *external* stop condition, and iterate
  until good enough — but never past `max_iters` or a `$X` `CostBudget` (and never on
  wall-clock). It mutates nothing, and with a ledger a crash mid-loop resumes for **\$0**,
  content-hash verified. Folds the three fixed-bound re-run atoms into one operator.
- **`Verifier` — a critic that must *earn* the right to stop you.** A bare `Verifier`
  only describes an Output and cannot gate; `Verifier.gated(...)` admits a `GatedVerifier`
  only after the critic clears an absolute-precision bar against a decision golden set,
  and **fails closed** — a never-benchmarked critic is never trusted to block production.
  A generator may never critique itself.
- **`branch` / `Program` / `recurse` — control flow with shape.** `branch(...)` makes a
  `Router` a runnable step (each branch inherits the same budget/taint/checkpoint
  guarantees). `Program` is a `Workflow` whose **edges may cycle** — back-edges re-enter
  a region while a guard holds, bounded by `max_visits` / budget / cancel / no-progress
  (never wall-clock), and a crash mid-cycle resumes for **\$0**, content-hash verified.
  `recurse(...)` is a depth-guarded back-edge into the *same frozen Definition*. Cycles
  and recursion are **assembly-required to be bounded** (`UnboundedCycleError` /
  `UnboundedRecursionError`); taint carries across every edge, and a fold never launders
  it.
- **The tunable-ML library — an agent is a model with tunable weights (flagship).** This is
  the *PyTorch-for-LLMs* half, unified with the rest by one idea: `mutable` is the train/eval
  switch. `train()`/`eval()` make *which knobs may move* and *whether the artifact is sealed*
  orthogonal axes, and `guard_consequential()` makes **acting eval-only** — only a sealed,
  content-addressed agent touches the world. The tunable knob space is *data* (`TuneSpec`,
  authored as `tune.toml`) that folds into the content hash, so **tuning versions the agent**.
  `calibrate()` measures the run-to-run **noise band**; `promote_against_baseline()` promotes
  only when a gain **clears that band** (the F-3 rejection invariant, made noise-robust); a
  cost-regularized `Objective` re-ranks the gate-passing set so cost can never promote a
  regression. `state_dict()`/`load_state()` are the architecture/weights split
  (*Hugging-Face-for-agent-weights*), and `ServingLoop` is the budget-bounded, no-peeking,
  deterministic-under-replay explore dial. **Only static knobs are ever promoted** — the whole
  loop stays inside the security spine.
- **The tameness layer — bounding the one stochastic primitive.** A model `Run` is the only
  stochastic atom; this milestone bounds it *itself*, four ways, without touching the
  deterministic spine. **`QuorumRuntime`** is self-consistency as a typed operator — sample the
  same request `k` times (each a seeded, replayable leaf charging the shared budget) and reduce
  by a **pure** consensus vote (`majority_vote`, the modal-output estimand); an ill-defined
  plurality abstains to a *declared* default, `k` defaults to the tunable `sample_k` knob, a
  sequential proportion test stops early with no peeking, and a vote **never launders taint**.
  **Abstention** (`abstain_below` / `abstain_below_calibrated`) lets a step *decline* rather
  than hallucinate, as a typed, routable Output **value** (`is_abstention`) with its threshold
  read off the calibration reliability curve. **The house-guard** (`HouseGuard`) accretes the
  program's own invariants — quality is **learned stochastically**, **distilled** to a pure
  closed-grammar predicate (no `eval`/`exec`, the proposal can only select within the grammar),
  and only **earns** enforcement after a **joint** precision-and-coverage gate that fails closed.
  **Constrained decoding** (`Grammar`) makes a malformed output shape an *impossible* state
  rather than a repaired one — a per-call, static/trusted property that keeps `repair_count` at
  0 and stays out of the agent's content hash. The house-guard is the keystone:
  *learn stochastically → distil to a pure predicate → earn enforcement.*

See the [Refine & verify guide](docs/guide/refine-and-verify.md), the
[Compose guide](docs/guide/compose.md), the
[Train, calibrate & promote guide](docs/guide/train-and-tune.md), the
[Taming stochasticity guide](docs/guide/tameness.md), the
[control-plane reference](docs/reference/refine-and-verify.md), the
[Tuner & learning reference](docs/reference/tuner-and-learning.md), and the
[release notes](docs/guide/release-notes.md).

These stand on the *foundational primitives* shipped earlier — substrate contracts, not
operators themselves:

- **A canonical Output content hash** — one content-identity primitive every ledger and
  replay path keys off.
- **An execution-coordinate cassette key** — record/replay now distinguishes each re-run
  of a leaf (sample, iteration, visit, depth), and folds tenancy into run identity.
- **A loop/program ledger** — per-`(item, edge, visit)` and per-recursion-depth resume
  with deterministic loop identity, so resuming a loop re-charges \$0 for work already done.
- **One cost model with a composition law** — a three-number interval
  (lower-bound / expected / worst-case) that multiplies along operator nesting.
- **A statistical gate algebra** — paired, variance-aware promotion gates plus a
  fail-closed precision gate for consequential guards, over a shared experiment-design spec.
- **Decode-knob ownership, a determinism tier, a correction corpus, and a Store-backed
  train-mode borrow** — the seams the Tuner and the operators need.

These foundations and their security and migration guarantees are documented in
[`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) and
[`docs/architecture/SECURITY.md`](docs/architecture/SECURITY.md).

## Phase 2 — themes (next)

Phase 2 turns the local trust loop into something teams run together. Directions we're
exploring (priorities will shift with contributor and user input):

- **Cloud + scale by driver swap** — production `Store` / `ArtifactStore` / runtime
  backends behind the existing protocols, and a managed-deploy path beyond the local
  detached supervisor.
- **A connectors ecosystem** — more first-party and community Sources/Sinks, and a
  smooth path for contributing one (see
  [contributing a connector](docs/guide/contributing-a-connector.md)).
- **A knowledge hub** — promoting the company-brain primitive (built in Phase 1, not yet
  wired) into a shared, reusable knowledge surface across pipelines.
- **Deeper observability** — richer dashboards, alerting, and SLOs over the run-info
  surface.

## Get involved

The best first contribution is a **connector** — a self-contained Source or Sink that
doesn't touch the core seams. Start with
[`docs/guide/contributing-a-connector.md`](docs/guide/contributing-a-connector.md) and
[`CONTRIBUTING.md`](.github/CONTRIBUTING.md). Have an idea for Phase 2? Open a Discussion.
