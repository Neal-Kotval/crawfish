# Train, calibrate & promote

This is the **PyTorch-for-LLMs** workflow: treat the agent as a model with tunable weights,
move it into *train mode*, search the knob space under a cost-regularized objective, measure
its run-to-run noise, and promote a winner only when it clears that noise — then transfer the
learned weights and seal it back to *eval mode*. The conceptual frame is on the
[Concepts page](concepts.md#the-pytorch-for-llms-half-train-eval-and-the-tunable-knob); this
guide is the runnable path, in the order you actually do it:

1. [`train()` / `eval()`](#train-mode-and-the-consequential-guard) — the mutability switch and the consequential guard
2. [Declare the tunable knobs](#declaring-the-tunable-knobs-tunetoml) — `tune.toml` → `TuneSpec`
3. [`calibrate`](#calibrate-measure-the-noise-band) — measure the noise band and abstention threshold
4. [The cost-regularized `Objective`](#tune-under-a-cost-regularized-objective) — search past a quality-only rule
5. [The variance-aware promotion gate](#promote-only-past-the-noise-band) — promote only past the band
6. [`state_dict` / `load_state`](#transfer-the-learned-weights-state_dict) — transfer the learned weights
7. [`ServingLoop`](#serve-with-an-explore-dial) — the serving-time explore dial

Every example is deterministic — a `MockRuntime` or recorded cassette, never a live model —
so it reproduces byte-for-byte.

## Train mode and the consequential guard

A loaded Definition is **frozen** — it is in **eval mode**, the default, and the only mode
that may act. `train(defn)` returns an *unfrozen* copy whose knobs may move; `eval(defn)`
re-freezes it. The two are idempotent when nothing changed:

```python
from crawfish import train, eval, guard_consequential, FrozenError

loaded = ...  # a frozen, eval-mode Definition (from load_definition)

training = train(loaded)          # unfrozen copy — knobs may move
assert training.frozen is False
sealed = eval(training)           # re-freeze via the content-hash path
assert sealed.frozen is True
assert sealed.content_sha() == loaded.content_sha()   # idempotent: no knob moved
```

The load-bearing rule is `guard_consequential`. Every consequential boundary — a Sink write,
a recorded run — calls it before committing an irreversible effect. It is a no-op in eval
mode and raises in train mode, because a training artifact has no stable content identity to
key idempotency or attribute the effect to:

```python
guard_consequential(sealed)       # eval mode → no-op, the Sink may fire

try:
    guard_consequential(training) # train mode → forbidden
except FrozenError as e:
    print("blocked:", e)          # consequential effects require an eval-mode Definition
```

!!! note "Train/eval *is* the security boundary"

    The prompt-injection boundary and the train/eval boundary are the same boundary: only a
    sealed, content-addressed, eval-mode agent touches the world. See the
    [security spine](../architecture/SECURITY.md).

## Declaring the tunable knobs (`tune.toml`)

Which knobs the Tuner may search is **data**, not a flag baked into the model. Author it as
`tune.toml` in the Definition directory — an array-of-tables of `[[knob]]`:

```toml
# tune.toml — the tunable knob space (Axis 1)
[[knob]]
path = "agent.triage.model"
values = ["haiku", "sonnet"]
tunable = true

[[knob]]
path = "agent.triage.temperature"
values = [0.0, 0.3, 0.7]
tunable = true

[[knob]]
path = "agent.triage.prompt"        # pinned — never proposed
values = ["v1", "v2"]
tunable = false
```

`load_definition` discovers it and populates `Definition.tune`. You can also build it in
code, and the spec content-hashes — so **changing the search space versions the agent**:

```python
from crawfish import TuneSpec, KnobDomain, tune_spec_sha

spec = TuneSpec(
    knobs=[
        KnobDomain(path="agent.triage.model", values=["haiku", "sonnet"], tunable=True),
        KnobDomain(path="agent.triage.prompt", values=["v1", "v2"], tunable=False),
    ]
)

# Only tunable knobs are ever proposed, and they come back path-sorted (set-order-free):
print([path for path, _ in spec.named_knobs()])   # ['agent.triage.model']
print(spec.is_tunable("agent.triage.prompt"))     # False — pinned
print(tune_spec_sha(spec))                         # a stable 12-char content hash
```

An empty `tune.toml` is **hash-neutral**: a tune-less Definition keeps its content sha
byte-for-byte, so adding one is a no-op on identity until you declare a knob.

## `calibrate` — measure the noise band

A single benchmark run hides run-to-run variance. `calibrate` runs each golden case `runs`
times under distinct, deterministically-derived seeds and reports the noise band — the
measurement the promotion gate and the objective consume:

```python
import asyncio
from crawfish import calibrate
from crawfish.core.context import CostBudget, RunContext

report = asyncio.run(
    calibrate(
        sealed,                      # the eval-mode Definition under test
        golden,                      # a GoldenSet or a Sequence[EvalCase]
        runs=5,                      # N re-runs per case under derived seeds
        ctx=RunContext(store=store, cost_budget=CostBudget(limit_usd=2.0)),
        runtime=runtime,             # a live/seed-honouring runtime — NOT replay
        rubric=rubric,
        target_accuracy=0.9,
    )
)

print("noise band:", report.rubric_std)              # per-metric population std
print("output variance:", report.output_variance)    # 0.0 iff every re-run agreed
print("abstain below:", report.abstention_threshold)  # read off the reliability curve
print("brier:", report.brier)                          # None without labels
```

The same `(base_seed, runs)` over the same golden yields a **byte-identical report and seed
schedule**. `calibrate` refuses a `RecordReplayRuntime` (replay would fabricate zero
variance) and honours the autonomy ceiling — a budget/cancel breach returns a `partial=True`
report over what was measured, never unbounded spend.

When you have no labels, confidence calibration is undefined (`brier`/`ece` are `None`), but
`rubric_std` and `output_variance` are still measured — that is all the promotion gate needs.

## Tune under a cost-regularized `Objective`

The Tuner's default rule is pure quality: it would promote a 1%-better, 5×-pricier candidate.
An `Objective` re-ranks — **only among candidates that already pass the hard regression
gate** — by `Σ wᵢ·scoreᵢ − λ·cost − μ·ece`:

```python
from crawfish import Objective
from crawfish.tuner import Tuner, KnobGridMutator

objective = Objective(
    weights={"accuracy": 1.0},
    cost_weight=0.5,                 # λ — quality points traded per unit cost
    cost_baseline_usd=0.01,          # normalizer; λ becomes unit-free
)

tuner = Tuner(
    benchmark,
    KnobGridMutator(models=["haiku", "sonnet"]),
    objective=objective,
    objective_items=1,
)
result = asyncio.run(tuner.tune(base, ctx, runtime, seed=0))

# Two equal-quality candidates → the cheaper wins; a 2%-better/much-pricier one is rejected
# for a suitable λ. A candidate that regresses past tolerance is STILL rejected by the hard
# gate, objective notwithstanding.
print("best model:", result.best.team.agents[0].model)
for t in result.trials:
    print(f"  {t.mutation.label!r}: cost={t.cost_usd} obj={t.objective_value}")
```

`cost_weight=0` reproduces today's winner exactly (the cost term vanishes). Set `pareto=True`
to additionally require non-domination on `(quality, cost)`; `result.pareto_front` reports the
regression-clean non-dominated trial indices. `ObjectiveForm.EPSILON` switches to "minimize
cost subject to `quality >= quality_floor`".

## Promote only past the noise band

`promote_against_baseline` promotes a candidate only when its gain over the stored baseline
**clears the noise band**, not merely when it is positive. Seed the baseline from a
calibration report so the band travels with it:

```python
from crawfish import save_baseline_from_report, promote_against_baseline

# Persist the calibrated mean as the baseline and its std as the noise band.
save_baseline_from_report(store, "triage", report)

verdict = promote_against_baseline(
    store,
    "triage",
    candidate=result.best_scores,
    primary="accuracy",
    alpha=0.05,                      # k·std band derives from alpha
)
print(verdict.promoted, verdict.reason)
print("primary gain:", verdict.primary_gain, "vs band:", verdict.primary_band)
```

The candidate is promoted **iff** both hold: no metric regresses past its own band (the hard
F-3 invariant, just made noise-robust), *and* the primary metric's gain exceeds `k·std`. A
candidate that maxes one metric while truly regressing another is rejected; a within-noise
"win" does not promote. With no recorded `std` (a pre-existing baseline) the band is
zero-width and the gate reduces byte-for-byte to the single-point behaviour. Pass a
`fresh_sample` to shrink the stored baseline toward an independent estimate (winner's-curse
correction) so the bar cannot ratchet up on selection noise.

!!! tip "The `LearningLoop` wires this together"

    For the full self-versioning cycle — search, gate, promote, and a reversible version
    lineage in the `Store` — use the [`LearningLoop`](../reference/tuner-and-learning.md#learningloop).
    `promote_against_baseline` is the variance-aware gate underneath it.

## Transfer the learned weights (`state_dict`)

Once a Definition has learned good knobs, `state_dict` extracts them as JSON-only **weights**
— per-role knobs, the coordination choice, `injected_prompts`, and summoned units as
references-by-version — carrying *no* architecture and *no* executable nested Definition:

```python
from crawfish import state_dict, load_state, IncompatibleStateError

weights = state_dict(result.best)
print("structure:", weights.structure_sha)   # architecture identity (transfer key)
print("weights:", weights.sha)                # knob-value identity — editing a knob changes it

# Carry the weights onto a sibling Definition of the SAME shape (copy-on-write):
tuned_sibling = load_state(sibling, weights)              # strict=True by default
assert tuned_sibling.content_sha() != sibling.content_sha()  # a NEW frozen artifact

# A shape mismatch is refused in strict mode:
try:
    load_state(different_shape, weights)
except IncompatibleStateError:
    tuned = load_state(different_shape, weights, strict=False)  # loads the intersection

# Transfer only the few-shot exemplars, nothing else:
just_fewshots = load_state(sibling, weights, only=["fewshots"])
```

`load_state` is copy-on-write — it returns a new frozen Definition and never mutates the
target. `d.load_state(d.state_dict())` re-mints the same content sha (sha-identity). Only
**static** knobs cross; no fluid value can ride along.

## Serve with an explore dial

`ServingLoop` is the serving-time explore/exploit overlay. It routes `(1-ε)` of live items to
the promoted best and `ε` to a trial candidate, choosing *which* items explore by a seeded
hash of the recorded `item_id` — so a replay re-explores exactly the same items:

```python
from crawfish import ServingLoop, ExploreSchedule

loop = ServingLoop(
    promoted=tuned_sibling,
    trial=result.best,
    schedule=ExploreSchedule(epsilon=0.1, decay=0.0),  # 10% explore, flat
    seed=0,
    sample_size=100,                                    # pre-registered N (no peeking)
    min_lift=0.0,
)

decision = loop.route("item-42", ctx)
print(decision.explore, decision.version)

# The deterministic explored subset of a batch (side-effect-free):
explored = loop.explored_items(["a", "b", "c", "d"], ctx)

# Graduate only after the pre-registered sample size, only on a strict lift:
verdict = loop.graduate(trial_rewards, baseline_rewards)
print(verdict.decided, verdict.graduate, verdict.reason)
```

`epsilon=0` disables exploration (a no-op overlay). ε is bounded by the shared `CostBudget` —
once it is exhausted, every item routes to the promoted best. `graduate` returns
`decided=False` until `sample_size` outcomes have accrued (the pre-registered-N rule that
controls Type-I error under continuous peeking), and even a graduating trial is promoted only
through the eval gate on the `LearningLoop`.

## See also

- [Concepts → the PyTorch-for-LLMs half](concepts.md#the-pytorch-for-llms-half-train-eval-and-the-tunable-knob) — the thesis.
- [Tuner & learning reference](../reference/tuner-and-learning.md) — exact signatures for every symbol here.
- [Metrics reference](../reference/metrics.md) — the `Rubric` and `calibrate` measurement layer.
- [Evals reference](../reference/evals.md) — golden sets and the promotion baseline.
- [Refine & verify](refine-and-verify.md) — the control-plane sibling of this loop.
