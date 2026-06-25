# Train, calibrate, and promote

You can score a pipeline, let Crawfish search for better settings, and promote the version that wins. This page walks the loop in the order you run it: switch the agent into train mode, declare the settings to search, measure run-to-run noise, search under a cost-aware objective, promote only a real win, then carry the learned settings to another agent.

A *knob* is a setting the search may change: which model a step uses, its temperature, how many samples it takes. The whole search runs over knobs, never over your code.

Every example here is deterministic. It uses a `MockRuntime` or a recorded run, never a live model, so it reproduces the same bytes every time.

## You will learn

- How to put an agent in train mode and why only an eval-mode agent can act
- How to declare the knobs the search may change, in `tune.toml`
- How to measure run-to-run noise with `calibrate`
- How to search under a cost-aware objective and promote past the noise
- How to transfer learned settings to a sibling agent

## Switch between train and eval mode

A loaded agent is *frozen*. It is in *eval mode*, the default, and eval mode is the only mode that may act on the world. `train(defn)` returns an unfrozen copy whose knobs can move. `eval(defn)` freezes it again. If no knob moved, the two are reversible: the agent comes back with the same content hash it started with.

```python
from crawfish import train, eval, guard_consequential, FrozenError

loaded = ...  # a frozen, eval-mode Definition (from load_definition)

training = train(loaded)          # unfrozen copy: knobs may move
assert training.frozen is False
sealed = eval(training)           # freeze again
assert sealed.frozen is True
assert sealed.content_sha() == loaded.content_sha()   # no knob moved, same identity
```

The rule that enforces this is `guard_consequential`. Every step that does something irreversible, like writing to a sink or recording a run, calls it first. In eval mode it does nothing and the effect proceeds. In train mode it raises, because a training copy has no stable identity to attribute the effect to or to key idempotency on.

```python
guard_consequential(sealed)       # eval mode: no-op, the sink may fire

try:
    guard_consequential(training) # train mode: forbidden
except FrozenError as e:
    print("blocked:", e)          # consequential effects require an eval-mode Definition
```

This is the same boundary that keeps untrusted input out of consequential actions: only a sealed, content-addressed, eval-mode agent touches the outside world. The [security overview](../architecture/SECURITY.md) describes that boundary in full.

## Declare the tunable knobs in `tune.toml`

The set of knobs the search may change is data you author, not a flag baked into the agent. Write it as `tune.toml` in the agent's directory, one `[[knob]]` per setting:

```toml
# tune.toml: the knobs the search may change
[[knob]]
path = "agent.triage.model"
values = ["haiku", "sonnet"]
tunable = true

[[knob]]
path = "agent.triage.temperature"
values = [0.0, 0.3, 0.7]
tunable = true

[[knob]]
path = "agent.triage.prompt"        # pinned: never proposed
values = ["v1", "v2"]
tunable = false
```

`load_definition` finds this file and fills in `Definition.tune`. You can also build the spec in code. The spec is content-hashed, so changing the search space changes the agent's version:

```python
from crawfish import TuneSpec, KnobDomain, tune_spec_sha

spec = TuneSpec(
    knobs=[
        KnobDomain(path="agent.triage.model", values=["haiku", "sonnet"], tunable=True),
        KnobDomain(path="agent.triage.prompt", values=["v1", "v2"], tunable=False),
    ]
)

# Only tunable knobs are proposed, returned sorted so set order never matters:
print([path for path, _ in spec.named_knobs()])   # ['agent.triage.model']
print(spec.is_tunable("agent.triage.prompt"))     # False, pinned
print(tune_spec_sha(spec))                         # a stable 12-char content hash
```

An empty `tune.toml` does not change the hash. An agent with no knobs keeps the exact content hash it had before, so adding the file does nothing to its identity until you declare a real knob.

## Measure the noise band with `calibrate`

A single benchmark run hides how much an agent's score moves from run to run. `calibrate` runs each golden case several times under different seeds and reports the *noise band*: how far the score drifts when nothing about the agent changed. The promotion gate and the objective both read this number.

```python
import asyncio
from crawfish import calibrate
from crawfish.core.context import CostBudget, RunContext

report = asyncio.run(
    calibrate(
        sealed,                      # the eval-mode Definition under test
        golden,                      # a GoldenSet or a Sequence[EvalCase]
        runs=5,                      # re-runs per case under derived seeds
        ctx=RunContext(store=store, cost_budget=CostBudget(limit_usd=2.0)),
        runtime=runtime,             # a seed-honouring runtime, not replay
        rubric=rubric,
        target_accuracy=0.9,
    )
)

print("noise band:", report.rubric_std)               # per-metric standard deviation
print("output variance:", report.output_variance)     # 0.0 if every re-run agreed
print("abstain below:", report.abstention_threshold)  # confidence cutoff from the curve
print("brier:", report.brier)                          # None without labels
```

The same `runs` and base seed over the same golden set produce an identical report and seed schedule every time. `calibrate` refuses a `RecordReplayRuntime`, since replaying recorded runs would report zero variance that is not real. It also respects the cost budget and cancel token: if either runs out, you get a `report` with `partial=True` over what it measured, never unbounded spend.

Without labels, confidence calibration is undefined, so `brier` and `ece` are `None`. The noise band and output variance are still measured, and that is what the promotion gate needs.

## Search under a cost-aware objective

By default the tuner promotes on quality alone. It would pick a candidate that scores 1% higher but costs five times as much. An `Objective` re-ranks candidates by quality minus a cost penalty: `Σ wᵢ·scoreᵢ − λ·cost − μ·ece`. It only ranks candidates that already pass the hard regression gate, so the objective can never let a worse agent through.

```python
from crawfish import Objective
from crawfish.tuner import Tuner, KnobGridMutator

objective = Objective(
    weights={"accuracy": 1.0},
    cost_weight=0.5,                 # how many quality points one unit of cost is worth
    cost_baseline_usd=0.01,          # normalizer, so cost_weight is unit-free
)

tuner = Tuner(
    benchmark,
    KnobGridMutator(models=["haiku", "sonnet"]),
    objective=objective,
    objective_items=1,
)
result = asyncio.run(tuner.tune(base, ctx, runtime, seed=0))

# Two equal-quality candidates: the cheaper one wins. A slightly better but much
# pricier one loses for a suitable cost_weight. A candidate that regresses past
# tolerance is still rejected by the hard gate, objective or not.
print("best model:", result.best.team.agents[0].model)
for t in result.trials:
    print(f"  {t.mutation.label!r}: cost={t.cost_usd} obj={t.objective_value}")
```

Set `cost_weight=0` and the cost term vanishes, reproducing the quality-only winner exactly. Set `pareto=True` to also require that no other candidate beats the winner on both quality and cost at once; `result.pareto_front` lists the regression-clean candidates that nothing dominates. `ObjectiveForm.EPSILON` switches the rule to "use the cheapest candidate whose quality clears a floor."

## Promote only past the noise band

`promote_against_baseline` promotes a candidate only when its gain over the stored baseline clears the noise band, not merely when the gain is positive. Seed the baseline from a calibration report so the band travels with it.

```python
from crawfish import save_baseline_from_report, promote_against_baseline

# Store the calibrated mean as the baseline and its std as the noise band.
save_baseline_from_report(store, "triage", report)

verdict = promote_against_baseline(
    store,
    "triage",
    candidate=result.best_scores,
    primary="accuracy",
    alpha=0.05,                      # sets the width of the band in std units
)
print(verdict.promoted, verdict.reason)
print("primary gain:", verdict.primary_gain, "vs band:", verdict.primary_band)
```

A candidate is promoted only when two things hold: no metric regresses past its own noise band, and the primary metric's gain is larger than the band. A candidate that maxes one metric while truly regressing another is rejected. A win that sits inside the noise does not promote. When the baseline has no recorded std, the band has zero width and the gate behaves exactly like a single-point comparison. Pass a `fresh_sample` to pull the stored baseline toward an independent estimate, which corrects for the way a search tends to over-credit its own winner.

For the full cycle of search, gate, promote, and a reversible version history in the `Store`, use the [`LearningLoop`](../reference/tuner-and-learning.md#learningloop). `promote_against_baseline` is the noise-aware gate inside it.

## Transfer the learned settings with `state_dict`

Once an agent has learned good knobs, `state_dict` extracts them as JSON *weights*: the per-role knobs, the coordination choice, any injected prompts, and summoned units referenced by version. It carries no structure and no executable agent.

```python
from crawfish import state_dict, load_state, IncompatibleStateError

weights = state_dict(result.best)
print("structure:", weights.structure_sha)   # identity of the shape, the transfer key
print("weights:", weights.sha)                # identity of the values, changes when a knob changes

# Carry the weights onto a sibling agent of the SAME shape. Copy-on-write:
tuned_sibling = load_state(sibling, weights)              # strict=True by default
assert tuned_sibling.content_sha() != sibling.content_sha()  # a new frozen artifact

# A shape mismatch is refused in strict mode:
try:
    load_state(different_shape, weights)
except IncompatibleStateError:
    tuned = load_state(different_shape, weights, strict=False)  # loads what overlaps

# Transfer only the few-shot examples, nothing else:
just_fewshots = load_state(sibling, weights, only=["fewshots"])
```

`load_state` is copy-on-write: it returns a new frozen agent and never changes the target. Calling `d.load_state(d.state_dict())` mints the same content hash it started with. Only static knobs cross, so no untrusted value can ride along with the weights.

## Serve with an explore dial

`ServingLoop` runs an explore-and-exploit overlay at serving time. It routes most live items to the promoted best and a small share to a trial candidate, picking which items explore by a seeded hash of the recorded `item_id`. A replay re-explores exactly the same items.

```python
from crawfish import ServingLoop, ExploreSchedule

loop = ServingLoop(
    promoted=tuned_sibling,
    trial=result.best,
    schedule=ExploreSchedule(epsilon=0.1, decay=0.0),  # 10% explore, flat
    seed=0,
    sample_size=100,                                    # fixed N, decided up front
    min_lift=0.0,
)

decision = loop.route("item-42", ctx)
print(decision.explore, decision.version)

# The explored subset of a batch, computed without side effects:
explored = loop.explored_items(["a", "b", "c", "d"], ctx)

# Graduate only after the fixed sample size, and only on a real lift:
verdict = loop.graduate(trial_rewards, baseline_rewards)
print(verdict.decided, verdict.graduate, verdict.reason)
```

Set `epsilon=0` to turn exploration off entirely. The explore rate is bounded by the shared `CostBudget`: once it runs out, every item routes to the promoted best. `graduate` returns `decided=False` until `sample_size` outcomes have accrued, which is what keeps you from declaring a winner early by peeking at partial results. Even a graduating trial is promoted only through the eval gate on the `LearningLoop`.

## Next steps

- [Tuner and learning reference](../reference/tuner-and-learning.md): exact signatures for every symbol here.
- [Metrics reference](../reference/metrics.md): the `Rubric` and the `calibrate` measurement layer.
- [Evals reference](../reference/evals.md): golden sets and the promotion baseline.
- [Taming stochasticity](tameness.md): `abstain_below_calibrated` reads its threshold from the calibration curve on this page.
