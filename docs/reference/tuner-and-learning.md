# Tuner & learning

The Tuner makes an agent better at its job by trying many candidate configurations and
keeping the one that scores best: no human editing it by hand, no live model in the loop.
The LearningLoop wraps that search in a safe, reversible promotion policy. You reach for
these to close the iterate→measure→tune→promote loop: turn knobs, score against a benchmark,
promote only a winner that clears the bar.

`Mutation` · `Candidate` · `PromptMutator` · `PromptVariantMutator` · `KnobGridMutator` ·
`FewShotMutator` · `ChainMutator` · `SearchStrategy` · `TrialResult` · `TuneResult` ·
`Tuner` · `LearningLoop` · `PromotionOutcome` · `VersionRecord`

These symbols are the train/eval mutability switch, the tunable knob space, calibration, the
cost-regularized objective, the promotion gate, weight transfer, and the serving-time explore
dial:

`train` · `eval` · `guard_consequential` · `TuneSpec` · `KnobDomain` · `tune_spec_sha` ·
`Objective` · `ObjectiveForm` · `ObjectiveScore` · `calibrate` · `CalibrationReport` ·
`ReliabilityBin` · `extract_confidence` · `abstention_threshold` · `promote_against_baseline` ·
`PromotionVerdict` · `save_baseline_from_report` · `load_baseline_std` · `state_dict` ·
`load_state` · `StateDict` · `RoleKnobs` · `IncompatibleStateError` · `ServingLoop` ·
`ServingDecision` · `ExploreSchedule` · `ExploreStrategy` · `GraduationVerdict`

These live in `crawfish.tuner`, `crawfish.learning`, `crawfish.metrics`, `crawfish.escalate`,
and `crawfish.eval`, and are all re-exported from the top-level `crawfish` package. The
runnable end-to-end walkthrough is the [Train, calibrate & promote guide](../guide/train-and-tune.md).

## Definitions, knobs, mutators, and the gate

An agent in Crawfish is described by a *Definition*: its team of agents, each agent's
prompt, its model, and other settings. Those settings are the knobs you can turn:
which model runs, what the prompt says, which few-shot examples are attached. Tuning means
trying different knob settings and keeping the best one.

A mutator produces the things to try. Given a starting Definition (the *base*), a
mutator enumerates candidates. Each candidate is a new Definition with some knobs
changed, plus a record of exactly what was changed (the *mutation*). A mutator
never asks a model to invent new text: it only selects and combines settings the author
already supplied. That keeps the search reproducible and keeps untrusted text off the
instruction path.

The Tuner runs the search. It scores the base, then scores each candidate against a
*Benchmark* (a fixed set of tasks plus a rubric that turns each run into numbers). It
keeps the best-scoring candidate, but only if that candidate actually beats the base and
does not score worse on any measured dimension. That last check is the *regression gate*:
a worse candidate is never chosen. The output of a full run is a TuneResult, and each
individual scored attempt is a TrialResult.

A search costs real money once a real model is wired in, so the Tuner enforces an autonomy
ceiling: three independent stops. It halts when a spend budget is exhausted, when a
cancel signal fires, or when a hard cap on the number of trials is reached. An autonomous
search can never run away.

The LearningLoop points the Tuner at an agent's own Definition and adds a promotion
policy: the winner becomes the agent's new active version only if it improves and clears
a stored quality bar (the *baseline*). Every version, the base and any promoted candidate,
is recorded as a frozen, content-hashed VersionRecord in the store, so a bad promotion
is fully reversible: you can roll back to any earlier version. The result of one improve
cycle is a PromotionOutcome.

!!! note "Good to know"

    Nothing in this loop calls a live model to invent configuration. Mutators only select
    and recombine settings the author already supplied, scoring is deterministic under a
    `MockRuntime` or replayed cassette, and the same `base` plus the same `seed` always yield
    the same result. That is what makes a tune reproducible and keeps an autonomous search
    auditable.

## Mutators: producing candidates

The Tuner proposes prompt variants and few-shot examples, searches, keeps the
benchmark-best, and regression-gates the winner. The mutators only select and recombine
settings the author supplied: no new dependency, no model inventing text.

### Mutators are pure and seeded

Every mutator subclasses `PromptMutator` and implements one method, `propose(base, *, seed)`,
which yields `Candidate`s. The contract is purity: no model call, no I/O, no wall clock,
no global random state. The same `base` plus the same `seed` must yield identical candidates
in identical order. Each mutator enforces this by sorting its inputs before enumerating,
so a Python `set` or `dict` iteration order never leaks into the proposal order.

`PromptVariantMutator` swaps or appends prompt text from an author-supplied pool. It sorts
and de-duplicates the variants, then in `mode="replace"` substitutes the primary agent's
`prompt`, or in `mode="append"` adds a `Prompt` to the Definition's `injected_prompts`
targeting that agent's role. With `include_base=True` (the default) it yields the unchanged
base first.

`KnobGridMutator` is a Cartesian product (`itertools.product`) over discrete typed knobs:
the primary agent's `model`, `context_strategy`, and `policies`; the team's `coordination`;
and a discretised `temperature` grid. Each axis is sorted before the product. `AgentSpec`
has no `temperature` field, so `temperature` rides in the `Mutation`'s audit trail (`knobs`)
rather than being written onto the spec.

`FewShotMutator` injects few-shot exemplars chosen from a golden set of `EvalCase`s. It sorts
the cases by id, then for each of `samples` runs derives a seeded subset of size `k` (seed +
sample index), renders the picks as one static `Prompt` block, and appends it. The seed
governs *which* `k` cases are chosen, so the choice is reproducible.

`ChainMutator` concatenates several mutators' proposals in declared order: the way you
combine, say, a prompt sweep with a knob grid in one search.

The "primary agent" the knobs apply to is the team lead if one is set, otherwise the
first agent. Tuning a Definition with no agents raises `ValueError`.

## Each candidate is a fresh frozen artifact

A frozen Definition rejects mutation, so the search never edits in place. For every candidate
the mutator builds a new Definition and re-freezes it with a fresh content-hash version:
the model is serialised (minus its volatile `version` field), hashed, and that hash becomes
the new `version.sha`. Two structurally-identical candidates collapse to the same sha
(idempotent); any knob difference produces a distinct sha. This matters for determinism: when
a real model is replayed from a recorded cassette, the cassette key varies on the Definition's
version, so distinct candidates never collide on replay.

## How the search decides

`Tuner.tune` scores the base first (the bar to beat). For each candidate it computes the score
deltas against the current running best. A candidate is accepted when it strictly improves
on at least one dimension and is no worse than `tolerance` on every dimension (`beats_best`),
and it is not a regression versus the base within `tolerance` (`clean_vs_base`). On
acceptance it becomes the new best. The winner is therefore never worse than the base.

`SearchStrategy` controls the order in which candidates are tried, never which candidates
exist (the mutator owns that). `GRID` keeps the mutator's proposal order. `RANDOM` takes a
seeded sample of `sample_size` candidates (a fixed seed gives a fixed sample). `EVOLUTIONARY`
is a seeded shuffle, a reproducible reordering of the full pool.

## The autonomy ceiling

Before scoring *anything*, `tune` checks the ceiling: an already-cancelled or
already-exhausted context returns the base unscored with an empty trial log, so the search
never starts past its ceiling. Inside the loop the order is: stop at `max_trials`; check the
cancel token then the budget; then charge `cost_per_trial_usd` before scoring (a trial costs
even on a replay hit). `CostBudget.charge` raises `BudgetExceeded` past the hard limit. The
`stopped_reason` on the result records which bound fired: `"exhausted"`, `"budget"`,
`"cancelled"`, or `"max_trials"`. The loop is never bounded by wall clock.

## The promotion gate

`LearningLoop.improve` is a thin policy over `Tuner.tune`. It runs the search, records the
tuned-from base as a frozen `VersionRecord` (seeding the regression baseline on first use),
then decides:

- A ceiling breach (`budget` / `cancelled` / `max_trials`) with no improvement is never a
  promotion: outcome reason `"ceiling:<reason>"`.
- If the Tuner found nothing better than the base: reason `"no_improvement"`.
- If the winner regresses against the stored baseline (via `gate_against_baseline`): reason
  `"gated"`. The baseline is the separate, persisted quality bar; it survives restarts and is
  what stops a noisy candidate from silently replacing a working agent.
- Otherwise the winner is promoted: recorded as a frozen `VersionRecord`, marked the single
  active version, and the baseline advances to its scores.

`rollback(sha)` re-activates any prior recorded version and resets the baseline to that
version's scores, so subsequent cycles are gated against the version actually in force. An
unknown `sha` raises `KeyError`.

!!! warning "Promotion only ever changes static configuration"

    The loop mutates only **static** configuration through the pure mutators, so a promotion
    can never introduce a **FLUID (untrusted)**, per-item sink target, and untrusted content
    can never drive a promotion. The improvement loop stays inside the
    [security spine](../architecture/SECURITY.md): a noisy or adversarial output can move
    scores, but it can't move the instruction path.

## Example

A deterministic tune: a `KnobGridMutator` sweeps the agent's `model` knob, scored by a fixed
function (`slow`→1, `mid`→5, `fast`→9) through a `MockRuntime`, no live model. The grid sorts
the models alphabetically, so `fast` is tried first and accepted as the best.

```python
import asyncio
import os
import tempfile

from crawfish.batch import Task
from crawfish.core.context import CostBudget, RunContext
from crawfish.core.types import Flow, Parameter
from crawfish.definition.types import AgentSpec, Definition, TeamSpec
from crawfish.metrics import Benchmark, OutputNumber, Rubric
from crawfish.runtime.base import RunRequest
from crawfish.runtime.mock import MockRuntime
from crawfish.runtime.prompt import pick_agent
from crawfish.store import SqliteStore
from crawfish.tuner import KnobGridMutator, Tuner


# A fixed deterministic scorer: the score depends only on the `model` knob.
def responder(request: RunRequest) -> str:
    agent = pick_agent(request.definition, request.role)
    return str({"slow": 1, "mid": 5, "fast": 9}.get(agent.model or "", 0))


base = Definition(
    team=TeamSpec(agents=[AgentSpec(role="worker", prompt="do the thing", model="slow")]),
    inputs=[Parameter(name="task", type="text", flow=Flow.FLUID)],
)
benchmark = Benchmark(Rubric([OutputNumber(name="score")]), [Task(description="a"), Task(description="b")])
tuner = Tuner(benchmark, KnobGridMutator(models=["slow", "mid", "fast"]))

with tempfile.TemporaryDirectory() as d:
    store = SqliteStore(os.path.join(d, "t.db"))
    ctx = RunContext(store=store, cost_budget=CostBudget(limit_usd=None))
    result = asyncio.run(tuner.tune(base, ctx, MockRuntime(responder), seed=0))

print("improved:", result.improved)
print("best model:", result.best.team.agents[0].model)
print("base score:", result.base_scores["score"])
print("best score:", result.best_scores["score"])
print("stopped:", result.stopped_reason)
for t in result.trials:
    print(f"  trial {t.index}: {t.mutation.label!r} score={t.scores['score']} accepted={t.accepted}")
```

??? success "▶ Output"

    ```text
    improved: True
    best model: fast
    base score: 1.0
    best score: 9.0
    stopped: exhausted
      trial 0: 'model=fast' score=9.0 accepted=True
      trial 1: 'model=mid' score=5.0 accepted=False
      trial 2: 'model=slow' score=1.0 accepted=False
    ```

## API reference

### `Mutation`

`class Mutation(BaseModel)`: the typed knob change that produced a candidate (the audit
trail).

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `kind` | `str` | — (required) | The mutator family, e.g. `"knob_grid"`, `"prompt_variant"`, `"few_shot"`. |
| `label` | `str` | — (required) | Short stable id for the change, e.g. `"variant[0]"`, `"model=fast"`. |
| `knobs` | `dict[str, JSONValue]` | `{}` | The concrete settings applied. |

### `Candidate`

`class Candidate(BaseModel)`: a proposed point in the knob space plus the patch that produced
it. Allows arbitrary types.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `definition` | `Definition` | — (required) | A mutated, re-frozen Definition with a distinct version sha. |
| `mutation` | `Mutation` | — (required) | The typed knob change. |

### `PromptMutator`

`class PromptMutator(ABC)`: deterministically enumerate candidate Definitions from a base.

```python
@abstractmethod
def propose(self, base: Definition, *, seed: int) -> Iterator[Candidate]
```

Pure: no model calls, I/O, wall clock, or global RNG. Same `base` + `seed` ⇒ identical
candidates in identical order.

### `PromptVariantMutator`

`class PromptVariantMutator(PromptMutator)`: swap/append from an author-supplied pool of
prompt variants.

```python
def __init__(
    self,
    variants: Sequence[str],
    *,
    mode: str = "replace",
    include_base: bool = True,
) -> None
```

`mode` must be `"replace"` or `"append"` (else `ValueError`). Variants are sorted and
de-duplicated. `mode="replace"` substitutes the primary agent's `prompt`; `mode="append"`
adds a `Prompt` to `injected_prompts`. `include_base=True` yields the unchanged base first.

### `KnobGridMutator`

`class KnobGridMutator(PromptMutator)`: Cartesian product over discrete typed knobs.

```python
def __init__(
    self,
    *,
    models: Sequence[str] | None = None,
    context_strategies: Sequence[str | None] | None = None,
    policies: Sequence[list[str]] | None = None,
    coordination: Sequence[Coordination] | None = None,
    temperature: Sequence[float] | None = None,
) -> None
```

Each supplied axis is sorted before the product. `model` / `context_strategy` / `policies`
land on the primary agent; `coordination` lands on the team; `temperature` travels only in the
`Mutation` audit trail. With no axes supplied, `propose` yields nothing.

### `FewShotMutator`

`class FewShotMutator(PromptMutator)`: inject few-shot exemplars from a golden set.

```python
def __init__(self, cases: Sequence[EvalCase], *, k: int = 2, samples: int = 1) -> None
```

`k < 1` or `samples < 1` raises `ValueError`. Cases are sorted by id; `k` is clamped to the
number of cases. Each of `samples` runs derives a seeded subset of `k` cases (seed + sample
index) and appends it as one static `Prompt`. Empty `cases` yields nothing.

### `ChainMutator`

`class ChainMutator(PromptMutator)`: concatenate several mutators' proposals in declared
order.

```python
def __init__(self, mutators: Sequence[PromptMutator]) -> None
```

### `SearchStrategy`

`class SearchStrategy(str, Enum)`: the order candidates are tried (not which exist).

| Member | Value | Meaning |
| --- | --- | --- |
| `SearchStrategy.GRID` | `"grid"` | Exhaustive enumeration in the mutator's proposal order. |
| `SearchStrategy.RANDOM` | `"random"` | Seeded sample of `sample_size` candidates (fixed seed → fixed sample). |
| `SearchStrategy.EVOLUTIONARY` | `"evolutionary"` | Seeded shuffle, a reproducible reordering of the full pool. |

### `TrialResult`

`class TrialResult(BaseModel)`: one scored trial (the ordered audit log). Allows arbitrary
types.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `index` | `int` | — (required) | Position in the trial order. |
| `mutation` | `Mutation` | — (required) | The knob change scored in this trial. |
| `version` | `str` | — (required) | The candidate's `str(Version)` (`major.minor-sha`). |
| `scores` | `dict[str, float]` | — (required) | Benchmark scores for this candidate. |
| `accepted` | `bool` | — (required) | True iff it beat the running best and was regression-clean. |

### `TuneResult`

`class TuneResult(BaseModel)`: the outcome of a tune. Allows arbitrary types.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `best` | `Definition` | — (required) | The winning frozen Definition (the base if nothing beat it). |
| `best_scores` | `dict[str, float]` | — (required) | The winner's benchmark scores. |
| `base_scores` | `dict[str, float]` | — (required) | The base's benchmark scores (the bar to beat). |
| `improved` | `bool` | — (required) | True iff the winner beats the base and is regression-clean. |
| `trials` | `list[TrialResult]` | — (required) | The ordered trial log. |
| `stopped_reason` | `str` | — (required) | `"exhausted"` \| `"budget"` \| `"cancelled"` \| `"max_trials"`. |

### `Tuner`

`class Tuner`: deterministic search over a mutator's candidates, scored by a Benchmark.

```python
def __init__(
    self,
    benchmark: Benchmark,
    mutator: PromptMutator,
    *,
    strategy: SearchStrategy = SearchStrategy.GRID,
    max_trials: int = 64,
    sample_size: int | None = None,
    tolerance: float = 0.0,
    cost_per_trial_usd: float = 0.0,
    emit_progress: bool = False,
    pipeline: str | None = None,
) -> None
```

`max_trials < 1` raises `ValueError`. `tolerance` is the per-dimension slack allowed before a
delta counts as a regression. `cost_per_trial_usd` is charged against `ctx.cost_budget` per
trial. `emit_progress` emits per-trial `METRIC` emissions (lazily imported, failures swallowed
so a search never breaks).

```python
async def tune(
    self,
    base: Definition,
    ctx: RunContext,
    runtime: AgentRuntime,
    *,
    seed: int = 0,
) -> TuneResult
```

Scores the base, then each candidate in strategy order; returns the regression-gated
benchmark-best. The autonomy ceiling is checked before any scoring. The only model contact is
`Benchmark.run`, which is replay-deterministic.

### `VersionRecord`

`class VersionRecord(BaseModel)`: one frozen, auditable point in an agent's version lineage,
persisted through the `Store`. Allows arbitrary types.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `agent` | `str` | — (required) | The learning-loop name this version belongs to. |
| `sha` | `str` | — (required) | The candidate's content-hash version sha (the lineage key). |
| `version` | `str` | — (required) | Human-readable `str(Version)` (`major.minor-sha`). |
| `definition` | `Definition` | — (required) | The frozen Definition at this point. |
| `scores` | `dict[str, float]` | — (required) | The benchmark scores that justified this version. |
| `role` | `str` | — (required) | `"base"` \| `"promoted"`. |
| `parent_sha` | `str \| None` | `None` | The version this one was derived from (lineage edge). |
| `active` | `bool` | `False` | True iff this is the agent's currently-active version. |

### `PromotionOutcome`

`class PromotionOutcome(BaseModel)`: the result of one `improve` cycle. Allows arbitrary
types.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `promoted` | `bool` | — (required) | True iff a strictly-better, gate-clean candidate replaced the active one. |
| `reason` | `str` | — (required) | `"promoted"` \| `"no_improvement"` \| `"gated"` \| `"ceiling:<reason>"`. |
| `active` | `Definition` | — (required) | The active Definition after this cycle (base if not promoted). |
| `base_sha` | `str` | — (required) | The frozen version tuned from (the lineage parent). |
| `candidate_sha` | `str` | — (required) | The Tuner's winning version (== `base_sha` if nothing better). |
| `base_scores` | `dict[str, float]` | — (required) | The base's scores. |
| `candidate_scores` | `dict[str, float]` | — (required) | The winner's scores. |
| `tune` | `TuneResult` | — (required) | The full Tuner trial log (the search audit trail). |

### `LearningLoop`

`class LearningLoop`: a self-improving agent, the Tuner plus an eval-gated, versioned
promotion policy.

```python
def __init__(
    self,
    name: str,
    tuner: Tuner,
    store: Store,
    *,
    org_id: str = "local",
    tolerance: float = 0.0,
) -> None
```

```python
async def improve(
    self,
    base: Definition,
    ctx: RunContext,
    runtime: AgentRuntime,
    *,
    seed: int = 0,
) -> PromotionOutcome
```

Runs one eval-gated self-versioning cycle: delegates the search to `Tuner.tune`, then promotes
the winner only if it improved *and* passes the stored baseline. Same `base` + `seed` ⇒ same
outcome.

Other methods: `history() -> list[VersionRecord]` (the full lineage); `active() -> VersionRecord
| None` (the currently-active record); `rollback(sha) -> Definition` (re-activate a prior
version and reset the baseline to its scores; raises `KeyError` if `sha` is unknown).

## The tunable-ML library

The symbols below are the train/eval mutability switch, the tunable knob space as data,
calibration, the cost-regularized objective, the variance-aware promotion gate, weight
transfer, and the serving-time explore dial. See [Core concepts](../guide/concepts.md)
and the runnable path in the [Train, calibrate & promote guide](../guide/train-and-tune.md).

### Two-axis mode (`crawfish.tuner`)

#### `train`

```python
def train(definition: Definition) -> Definition
```

Train mode. Returns an unfrozen deep copy with a fresh `Version` (`frozen is False`,
`version.sha is None`). Copy-on-write: a training mutation mints a new `version.sha` when
re-frozen, never an in-place edit of the original.

#### `eval`

```python
def eval(definition: Definition) -> Definition
```

Eval mode (the default for a loaded Definition). Re-freezes via the content-hash path, so
`eval(train(d))` is idempotent: it hashes back to `d`'s eval sha whenever no knob moved. Only
in eval mode may a consequential Sink fire or a run be recorded. (Shadows the builtin `eval`;
import it as `from crawfish import eval as eval_mode` if that collides in your module.)

#### `guard_consequential`

```python
def guard_consequential(definition: Definition) -> None
```

The gate every consequential boundary calls before an irreversible side effect.
A no-op in eval mode; raises `FrozenError` against an unfrozen (train-mode) Definition: a
training artifact has no stable content identity to key idempotency or attribute the effect to.

#### `TuneSpec`

`class TuneSpec(BaseModel)` (frozen): the tunable knob space as content-hashable data (the
typed form of `tune.toml`). Lives in `crawfish.tune` and is re-exported (identity-stable) from
`crawfish.tuner`.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `knobs` | `list[KnobDomain]` | `[]` | The declared knob domains. |

| Method | Signature | Purpose |
| --- | --- | --- |
| `named_knobs` | `() -> Iterator[tuple[str, KnobDomain]]` | Yields only `tunable=True` knobs, path-sorted (set/insertion-order-free). |
| `is_tunable` | `(path: str) -> bool` | Declared-and-tunable test; unknown paths are not tunable. |
| `from_toml` | `(text: str) -> TuneSpec` *(classmethod)* | Parse the `[[knob]]` array-of-tables authoring shape. |
| `to_dict` | `() -> dict` | Canonical, path-sorted, JSON-ready payload for export + hashing. |

#### `KnobDomain`

`class KnobDomain(BaseModel)` (frozen): one knob's search domain.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `path` | `str` | — (required) | Dotted address into the knob vocabulary (`agent.<role>.model` / `.prompt` / `.temperature` / `.sample_k` / `.context_strategy` / `.policies`, `team.coordination`, `injected_prompts`). |
| `values` | `list[KnobValue]` | — (required) | The discrete values the knob may take (static scalar leaves). |
| `tunable` | `bool` | `True` | When `False` the knob is pinned and never proposed. |

#### `tune_spec_sha`

```python
def tune_spec_sha(spec: TuneSpec) -> str
```

Deterministic 12-char content hash of a `TuneSpec`. An empty spec hashes to a stable constant
(an empty `tune.toml` is hash-neutral). `Definition.content_dict()` folds this in only for
a non-empty tune, so declaring a knob versions the agent while a tune-less Definition keeps its
sha byte-for-byte.

### Cost-regularized objective (`crawfish.tuner`)

#### `Objective`

`class Objective(BaseModel)` (frozen): the cost-regularized loss the Tuner maximizes among
candidates that already pass the hard regression gate, so cost can never promote a quality
regression.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `weights` | `dict[str, float]` | `{}` | Per-metric quality weights; an absent metric defaults to `1.0` (a bare objective sums every metric). |
| `cost_weight` | `float` | `0.0` | λ, the cost penalty. `0` reproduces today's pure-quality winner. |
| `ece_weight` | `float` | `0.0` | μ, the calibration penalty (a passed-in value; ships as 0 until `calibrate` feeds it). |
| `form` | `ObjectiveForm` | `LINEAR` | Scalarization vs ε-constraint. |
| `quality_floor` | `float` | `0.0` | ε-constraint: the minimum acceptable `Σ wᵢ·scoreᵢ`. |
| `cost_baseline_usd` | `float \| None` | `None` | Cost normalizer (set to the cheapest candidate's cost so λ is unit-free); `None` uses raw dollars. |

| Method | Signature | Purpose |
| --- | --- | --- |
| `value` | `(scores, *, cost_usd, ece=0.0) -> float` | The scalar ranking key `Σ wᵢ·scoreᵢ − λ·cost − μ·ece`. |
| `score` | `(scores, *, cost_usd, ece=0.0) -> ObjectiveScore` | The decomposed result. |
| `quality` | `(scores) -> float` | `Σ wᵢ·scoreᵢ`. |

#### `ObjectiveForm`

`class ObjectiveForm(str, Enum)`: `LINEAR` (weighted scalarization) / `EPSILON` (minimize cost
subject to `quality >= quality_floor`).

#### `ObjectiveScore`

`class ObjectiveScore(BaseModel)` (frozen): `value`, `quality`, `cost_penalty`, `ece_penalty`,
`feasible` (the ε-constraint gate; always `True` in linear form).

`Tuner` gains (all optional; defaults preserve legacy behavior): `objective: Objective |
None = None`, `pareto: bool = False`, `objective_items: int = 1`. `TrialResult.cost_usd` and
`TrialResult.objective_value` are recorded per candidate (both `None` with no objective);
`TuneResult.pareto_front: list[int]` is populated only when `pareto=True`.

### Calibration (`crawfish.metrics`)

#### `calibrate`

```python
async def calibrate(
    definition: Definition,
    golden: GoldenSet | Sequence[EvalCase],
    *,
    runs: int = 5,
    ctx: RunContext,
    runtime: AgentRuntime,
    rubric: Rubric | None = None,
    confidence_field: str = "confidence",
    cost_per_run_usd: float = 0.0,
    target_accuracy: float = 0.9,
    n_bins: int = 10,
    alpha: float = 0.05,
    n_resamples: int = 1000,
    base_seed: int = 0,
    inputs_for: Callable[[EvalCase], dict[str, JSONValue]] | None = None,
) -> CalibrationReport
```

Runs each golden case `runs` times under distinct, deterministically-derived per-run seeds and
returns the noise band + calibration measurement. Drives the runtime directly via
`RunRequest(decode_seed=...)`. The same `(base_seed, runs)` over the same golden yields a
byte-identical report and seed schedule. Raises `CalibrationError` on a `RecordReplayRuntime`
(replay would fabricate zero variance). Honours the autonomy ceiling: a budget/cancel breach
returns a `partial=True` report.

#### `CalibrationReport`

`class CalibrationReport(BaseModel)` (frozen): the `org_id`-tagged measurement the promotion
gate and objective consume.

| Field | Type | Notes |
| --- | --- | --- |
| `rubric_mean` / `rubric_std` | `dict[str, float]` | Per-metric mean and population std across `runs × len(golden)` scored outputs (the noise band). |
| `output_variance` | `float` | Mean fraction of structurally-differing fields across a case's re-runs; `0.0` iff every re-run agreed. |
| `brier` | `float \| None` | Primary calibration metric (binning-free); `None` without labels. |
| `ece` / `ece_ci` | `float \| None` / `tuple[float, float] \| None` | ECE diagnostic (equal-mass bins) and its bootstrap CI; `None` without labels; `ece ∈ [0,1]`. |
| `reliability` | `tuple[ReliabilityBin, ...]` | The equal-mass confidence→accuracy curve. |
| `abstention_threshold` / `abstention_rate` | `float` / `float` | The confidence below which acting is unsafe (read off `reliability`) and the share of outputs below it. |
| `determinism_tier` / `infra_variance_floor` | `DeterminismTier` / `float` | The runtime's F-5 tier and, when not `honors-seed`, the variance attributed to infra. |
| `org_id`, `definition_id`, `definition_version`, `content_sha`, `base_seed`, `runs`, `cases` | — | Tenancy + reproducibility coordinates. |
| `partial` | `bool` | `True` when a budget/cancel ceiling cut the measurement short. |

`report.gate_safe(margin) -> bool` (F-8 guard) forbids gating on `ece` when its CI is wider
than the gate margin, and fails safe (`False`) with no CI.

#### `ReliabilityBin`

`class ReliabilityBin(BaseModel)` (frozen): `confidence`, `accuracy`, `count` for one
equal-mass bin.

#### `CalibrationError`

`class CalibrationError(RuntimeError)`: raised when `calibrate` is handed a `RecordReplayRuntime`.

### Confidence & abstention (`crawfish.escalate`)

#### `extract_confidence`

```python
def extract_confidence(output: Output[JSONValue], *, field: str = "confidence") -> float | None
```

Read a `[0,1]` self-reported confidence from a typed Output (a mapping field, or a bare numeric
value), clamped; `None` when absent. The fluid value is measured, never trusted as an
instruction.

#### `abstention_threshold`

```python
def abstention_threshold(
    bin_confidence: list[float],
    bin_accuracy: list[float],
    bin_count: list[int],
    *,
    target: float = 0.9,
    default: float = 1.0,
) -> float
```

The evidence-derived replacement for the old guessed escalation constant: the lowest bin
confidence above which observed accuracy stays `>= target`. Empty bins are skipped; fails safe
to `default` (`1.0`, abstain on everything) when no level is reliable. Pure and deterministic.

### Variance-aware promotion (`crawfish.eval`)

#### `promote_against_baseline`

```python
def promote_against_baseline(
    store: Store,
    name: str,
    candidate: dict[str, float],
    *,
    primary: str,
    alpha: float = 0.05,
    tolerance: float = 0.0,
    org_id: str = "local",
    fresh_sample: dict[str, float] | None = None,
    shrink_weight: float = 1.0,
) -> PromotionVerdict
```

Promotes `candidate` iff BOTH: no metric regresses past its recorded noise band (the hard F-3
invariant, made noise-robust), and the `primary` metric's gain exceeds `k·std`
(`k` from `alpha`). With no recorded `std` the band is zero-width and the gate reduces
byte-for-byte to `gate_against_baseline` + "primary gain > 0". A `fresh_sample` shrinks the
stored baseline (winner's-curse correction). A rejected candidate writes nothing.

#### `PromotionVerdict`

`class PromotionVerdict` (frozen dataclass): `promoted`, `regressed`, `cleared_band`,
`primary`, `primary_gain`, `primary_band`, `reason` (auditable).

#### `save_baseline_from_report`

```python
def save_baseline_from_report(
    store: Store, name: str, report: CalibrationReport, *, org_id: str = "local"
) -> None
```

Persist a baseline from a `CalibrationReport`: the report's `rubric_mean` becomes the scores
and its `rubric_std` the noise band. The report's `org_id` is respected at the default.

#### `load_baseline_std`

```python
def load_baseline_std(store: Store, name: str, *, org_id: str = "local") -> dict[str, float] | None
```

Load the per-metric std recorded alongside a baseline. `None` (no std record, any pre-CRA-212
baseline) signals a zero-width band, reducing the gate to `gate_against_baseline`.

`save_baseline` gained an optional `std: dict[str, float] | None = None`; the `scores` record
format is unchanged (`std=None` writes exactly the old record and never erases an existing band).

### Weight transfer (`crawfish.learning`)

#### `state_dict`

```python
def state_dict(definition: Definition) -> StateDict
```

Extract the tunable knobs as the "weights": per-role knobs, the coordination choice,
`injected_prompts`, and summoned units as references-by-version. Excludes architecture keys
(IO schema, dependency structure, team topology). JSON-only and deterministic.

#### `load_state`

```python
def load_state(
    definition: Definition,
    state: StateDict,
    *,
    strict: bool = True,
    only: list[str] | None = None,
) -> Definition
```

Transfer the knob VALUES from `state` onto `definition`, copy-on-write (a NEW frozen
Definition; the target is never mutated). `strict=True` raises `IncompatibleStateError` on a
`structure_sha` mismatch; `strict=False` loads the structural intersection. `only` restricts
the transferred groups to members of `{prompt, model, context_strategy, policies, decode,
fewshots, coordination}`. `d.load_state(d.state_dict())` re-mints the same content sha.

#### `StateDict`

`class StateDict(BaseModel)` (frozen, JSON-only): the tunable knobs as the "weights".

| Field / property | Type | Notes |
| --- | --- | --- |
| `roles` | `dict[str, RoleKnobs]` | Per-role tunable knobs. |
| `coordination` | `Coordination` | The team topology *choice* (a tunable knob). |
| `injected_prompts` | `list[Prompt]` | Few-shots / appended instruction blocks. |
| `summons` | `list[DefinitionRef]` | Summoned units as references-by-version (`{id, version}`); embedding a nested Definition is rejected. |
| `structure_sha` | `str` | Content hash of the architecture, the transfer-compatibility key. |
| `sha` *(property)* | `str` | Content hash of the knob values; editing any knob changes it (excludes `structure_sha`). |

#### `RoleKnobs`

`class RoleKnobs(BaseModel)` (frozen): one role's knob bundle: `prompt`, `model`,
`context_strategy`, `policies`, and decode knobs (`temperature` / `top_p` / `sample_k`, carried
only when pinned). Every field is a static, author-supplied knob; none is fluid.

#### `IncompatibleStateError`

`class IncompatibleStateError(TypeError)`: `load_state(strict=True)` was asked to load onto an
incompatible architecture (a `structure_sha` mismatch).

### Serving-time explore (`crawfish.learning`)

#### `ServingLoop`

```python
def __init__(
    self,
    promoted: Definition,
    trial: Definition,
    schedule: ExploreSchedule,
    *,
    seed: int = 0,
    sample_size: int = 100,
    min_lift: float = 0.0,
    org_id: str = "local",
) -> None
```

The serving-time explore/exploit overlay. Routes `(1-ε)` of items to `promoted`, `ε` to
`trial`, choosing explored items by a seeded hash of the recorded `item_id` (a replay
re-explores exactly the same items). `sample_size < 1` raises `ValueError`.

| Method | Signature | Purpose |
| --- | --- | --- |
| `route` | `(item_id: str, ctx: RunContext) -> ServingDecision` | Route one live item; explores iff the budget has room AND the seeded item hash falls under the effective (decaying) rate. Advances the served counter. |
| `explored_items` | `(item_ids: list[str], ctx: RunContext) -> list[str]` | The deterministic explored subset of a batch (side-effect-free). |
| `graduate` | `(trial_rewards: list[float], baseline_rewards: list[float]) -> GraduationVerdict` | The no-peeking graduation gate (`decided=False` until `sample_size` outcomes). |

ε is bounded by the shared `CostBudget`: once `remaining_usd == 0`, every item routes to the
promoted best. Promotion stays with the `LearningLoop` (eval-gated + reversible).

#### `ExploreSchedule`

`class ExploreSchedule(BaseModel)` (frozen): `epsilon` (base rate in `[0,1]`; `0` disables
exploration), `decay` (effective rate after `n` served items is `epsilon / (1 + decay·n)`;
`decay=0` is flat fixed-ε), `strategy: ExploreStrategy`. `rate_at(served) -> float` gives the
effective rate.

#### `ExploreStrategy`

`class ExploreStrategy(str, Enum)`: `HASH` (the shipped deterministic router) plus reserved
`UCB1` / `THOMPSON` hooks (declared so a future strategy plugs in without an API change).

#### `ServingDecision`

`class ServingDecision(BaseModel)` (frozen): per-item routing verdict: `item_id`, `explore`,
`version`.

#### `GraduationVerdict`

`class GraduationVerdict(BaseModel)` (frozen): `decided`, `graduate`, `n_outcomes`,
`sample_size`, `trial_mean`, `baseline_mean`, `reason`. `decided` is `False` until
`n_outcomes >= sample_size` (no peeking); once decided, `graduate` is `True` iff the trial
mean beats baseline by at least `min_lift`.

## See also

- [Train, calibrate & promote](../guide/train-and-tune.md): the runnable end-to-end workflow for the symbols above.
- [Metrics](metrics.md): the `Benchmark` and `Rubric` that turn a candidate run into scores, and `calibrate`.
- [Evals](evals.md): the golden set, `gate_against_baseline`, and the variance-aware promotion gate.
- [Definition](definition.md): the agents, prompts, and knobs the mutators turn; `Definition.tune`.
