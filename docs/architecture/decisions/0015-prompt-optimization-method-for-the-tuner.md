# ADR 0015 — Prompt-optimization method for the Tuner

**Status:** Accepted · **Date:** 2026-06-21 · **Milestone:** Phase 2 ·
**Spike:** CRA-187 · **Gates:** CRA-176 (the Tuner)

## Context

CRA-176 (the Tuner) is specced to do "DSPy-style prompt optimization": improve a
`Definition`'s `AgentSpec` knobs against a `Benchmark`. It names the *aesthetic* of
DSPy but does not choose a *method*, and a build agent cannot write its
`prompt_mutations`/search loop until one is settled.

The hard constraint is the **Definition of Done: determinism**. The Tuner must search
with **no live model calls** and be reproducible under `RecordReplayRuntime` /
`MockRuntime` — *identical inputs → identical proposed prompts*. This is non-negotiable:
the whole eval/improvement loop (CRA-175 `metrics.py`/`eval.py`) is built to score
without burning budget or drifting, and the Tuner is the consumer of that loop.

What the Tuner actually optimizes is a **small, typed knob space** already defined on
`AgentSpec`/`TeamSpec`/`Definition` (`packages/crawfish/src/crawfish/definition/types.py`):

- `AgentSpec.prompt` and `Definition.injected_prompts` (text — the prompt knobs)
- `AgentSpec.model` (`str | list[str] | None`), `context_strategy`, `policies`
- `AgentSpec.temperature` (per the Tuner spec), `TeamSpec.coordination`

Scoring already exists and is deterministic: `Benchmark.run` (metrics.py) executes a
`Definition` over a fixed task set through an injected `AgentRuntime` and aggregates a
`Rubric` to a comparable score vector; `compare`/`is_regression`/`gate_against_baseline`
give the ordering and the regression gate. CRA-175 added `structural_diff`-backed typed
metrics (`StructuralMatch`, `SetOverlap`, `SchemaConformance`).

The architectural invariant (ADR 0001): **all model calls go through the one
`AgentRuntime` seam.** Nodes/components never import an SDK or a concrete backend. ADR
0010 set the governing posture for heavy third-party infra: *borrow the idea,
reimplement typed/deterministic through our seams, and depend on heavy infrastructure
only after an evaluation spike + a follow-up ADR.* This is that ADR.

## Options compared

We evaluated DSPy (the `MIPROv2`/`BootstrapFewShot` optimizer family), an
**LLM-rewrites-the-prompt** loop, and an **in-house deterministic search** over the typed
knob space scored by the existing `Benchmark`.

| Axis | **DSPy (MIPROv2 / BootstrapFewShot)** | **LLM-rewrites-prompt loop** | **In-house deterministic search** |
| --- | --- | --- | --- |
| **Determinism under replay** | ✗ Optimizer **issues live LM calls during search** (proposes instructions, bootstraps few-shot demos, TPE/Bayesian trials). Seedable (`random_state`, `seed`) but seed governs *its* RNG, not *our* cassette keys; reproducible only if the entire combinatorial proposal space is pre-recorded. Optuna TPE adds stochastic search. **Not byte-reproducible under `RecordReplayRuntime`.** | ✗ Rewrite step is itself a model call; non-deterministic unless every rewrite is cassetted. The *proposals* (not just the scoring) need replay. | ✓ Search loop is **pure Python**: enumerate/sample the typed knob space with a fixed seed; only *scoring* hits a model, through `Benchmark` → `AgentRuntime` → cassette. Identical inputs → identical proposals, by construction. |
| **Fits the `AgentRuntime` seam** | ✗ Ships its own LM client (**LiteLLM**); assumes `dspy.configure(lm=...)`. Bypasses our single seam, taint, and budget. Re-routing DSPy through `AgentRuntime` means reimplementing its client anyway. | ~ Can be made to call through `AgentRuntime`, but the rewrite prompt is a second, unaudited model interaction. | ✓ Never calls a model directly; *all* model contact is the existing `Benchmark.run(definition, ctx, runtime)`. Zero new model-call paths. |
| **Reuses our metrics/benchmark** | ✗ Wants its own `dspy.Example` datasets + `metric(gold, pred)` callables; would wrap `GoldenSet`/`Rubric` rather than use them. | ~ Could score with our `Benchmark`. | ✓ Native: scores with `Rubric`/`Benchmark`, orders with `compare`, gates with `is_regression`/`gate_against_baseline`. Golden set (CRA-175) is the task set. |
| **Dependency weight** | ✗ Heavy: pulls **LiteLLM** + (for the strong optimizers) **Optuna** (~12.7 MB, now optional but required for MIPROv2/`BootstrapFewShotWithOptuna`), plus its transitive web of provider SDKs. Large surface far from our typed core. | ✓ None new. | ✓ None new (`itertools`/`random`/`stdlib`). |
| **Licensing** | ✓ MIT (compatible). | n/a | n/a |
| **Maintenance / fit** | ✗ Fast-moving external API; couples our trust loop to its release cadence. Conflicts with ADR 0010's "don't out-surface-area a faster project; keep the core small/typed." | ~ Trivial code, but a live, drifting proposal step. | ✓ Owned, small, typed, frozen-artifact-friendly. |
| **How much we'd use vs build** | We'd use ~the *idea* (propose instructions/few-shot, search, keep the best) but rebuild the seam integration, datasets, determinism. Net: import a heavy dep to reuse a concept we must reshape anyway. | We'd build the loop and own the non-determinism problem. | We build the loop (~a few hundred lines) and own all of it, deterministic by design. |

### Evidence (CRA-187 spike)

- DSPy is MIT, ~35k stars, built **on LiteLLM** as its LM client and uses **Optuna**
  Bayesian optimization for MIPROv2 — confirming both the seam bypass and the stochastic
  optimizer. ([DSPy LM docs](https://dspy.ai/api/models/LM/),
  [DSPy installation](https://dspy.ai/getting-started/installation/),
  [MIPROv2 API](https://dspy.ai/api/optimizers/MIPROv2/))
- MIPROv2 **runs the LM during optimization** — bootstrapping few-shot demos and
  proposing instructions, then searching combinations with Bayesian/TPE trials. Its
  `seed`/`random_state` gives best-effort reproducibility of *its* sampling, not the
  byte-identical replay our cassette model (`runtime/replay.py`, which keys on definition
  id+version+role+model+inputs) requires.
  ([MIPROv2 deep-dive](https://dspy.ai/deep-dive/optimizers/miprov2/),
  [DeepWiki MIPROv2](https://deepwiki.com/stanfordnlp/dspy/4.4-miprov2:-instruction-and-parameter-optimization))
- Crawfish already owns the deterministic scoring half: `Benchmark`, `Rubric`,
  `compare`, `is_regression`, `gate_against_baseline` (`metrics.py`/`eval.py`), all
  documented as deterministic under `MockRuntime`.

## Decision

**Build an in-house deterministic search over the typed `AgentSpec` knob space, scored by
the existing `Benchmark`. Do NOT add DSPy (or any optimizer) as a dependency.** Borrow
DSPy's *ideas* (propose prompt variants + few-shot exemplars, search, keep the
benchmark-best, regression-gate the winner); reject its *dependency*, its LM client, and
its stochastic, live-call optimizer.

This is the exact posture ADR 0010 mandates: borrow the idea, reimplement typed and
deterministic through our seam, and decline heavy infra after the spike shows it doesn't
fit. The verdict **gates CRA-176**.

### Determinism verdict

DSPy **cannot** satisfy the DoD as a dependency: its optimizer makes live LM calls and
runs a stochastic search, so "identical inputs → identical proposed prompts" holds only
under best-effort seeding, never byte-reproducibly under `RecordReplayRuntime`. The
in-house search satisfies it **by construction**: proposal generation is pure Python
(deterministic given a seed), and the *only* model contact is `Benchmark.run` through the
injected `AgentRuntime`, which is already replay-deterministic via cassettes.

## Implementation guidance for CRA-176

**The `PromptMutator` contract (the interface this spike hands CRA-176):**

```python
class Candidate(BaseModel):
    """A proposed point in the knob space + the patch that produced it."""
    definition: Definition          # a mutated, re-frozen Definition
    mutation: Mutation              # the typed knob change (for the audit trail)

class PromptMutator(ABC):
    """Deterministically enumerate candidate Definitions from a base one.

    PURE: no model calls, no I/O, no wall-clock/global RNG. Given the same base
    Definition and the same seed, `propose` MUST yield identical candidates in
    identical order. This is the determinism contract the DoD requires.
    """
    @abstractmethod
    def propose(self, base: Definition, *, seed: int) -> Iterator[Candidate]: ...
```

Concrete mutators operate on the **typed knobs**, never on free text heuristically:

- `PromptVariantMutator` — swap/append from an **author-supplied, static** pool of
  `injected_prompts` / `AgentSpec.prompt` variants (the prompt text is data the author
  provides; the Tuner only *selects/combines*, it does not invent text via a model —
  that keeps it pure and keeps fluid/untrusted text off the instruction path per
  SECURITY.md).
- `KnobGridMutator` — Cartesian/`itertools.product` over discrete knobs:
  `model` choices, `context_strategy` names, `policies` subsets,
  `TeamSpec.coordination`, and a **discretised** `temperature` grid (e.g.
  `[0.0, 0.3, 0.7]`).
- `FewShotMutator` — select few-shot exemplars deterministically from the
  `GoldenSet` (sort by case id, take a seeded subset) and inject them — DSPy's
  bootstrap idea, made pure.

**The search loop (the Tuner core):**

1. Build the base `Definition`, a `Benchmark` (rubric + golden-set tasks), and a
   `RunContext` with a `CostBudget`.
2. For each `Candidate` from `mutator.propose(base, seed=seed)` (deterministic order):
   - re-freeze the mutated `Definition` (mutating a frozen artifact is rejected — build a
     new one);
   - `scores = await benchmark.run(candidate.definition, ctx, runtime)` — the **only**
     model contact, replay-deterministic;
   - keep the candidate if `compare(best_scores, scores)` improves and
     `not is_regression(best_scores, scores, tolerance=...)`.
3. Search strategy is a **deterministic enumerator** over the knob space:
   - **grid** (exhaustive product) for small spaces;
   - **seeded random** (`random.Random(seed)`) sample for larger ones — fixed seed ⇒
     fixed sample;
   - optional **seeded evolutionary** step (mutate the current best's knobs with the same
     seeded RNG) — still pure, still reproducible.
   Bound the search by `CostBudget`/`max_candidates`, not wall clock.
4. Return the benchmark-best `Definition` (a new frozen version per ADR 0012) plus the
   ordered trial log (each `Mutation` + its score vector) for the audit trail.

**Determinism rules CRA-176 must honour (and test):**

- `PromptMutator.propose` is pure and seeded — **no model/LLM call inside the mutator.**
- The cassette key (`runtime/replay.py::_key`) already varies on `definition.version` and
  `inputs`; because each candidate is a distinct re-frozen `Definition` (distinct
  id/version), candidates get distinct cassettes and never collide on replay. CRA-176's
  test seeds a `RecordReplayRuntime` (or `MockRuntime`) and asserts two runs over the same
  base+seed yield the **identical** winning Definition and identical trial order
  (`acceptance: identical inputs → identical proposed prompts`).
- No `set`/`dict` iteration order leaks into proposal order — sort before iterating;
  derive all randomness from the single passed `seed`.

## Alternatives rejected

- **Adopt DSPy as a dependency.** Fails the DoD (live-call, stochastic optimizer; not
  byte-reproducible under replay), bypasses the `AgentRuntime` seam with its own LiteLLM
  client, drags in Optuna + provider SDKs, and re-implements concepts (datasets, metrics)
  we already own deterministically — all to reuse an *idea* we must reshape regardless.
  Contradicts ADR 0010's "don't import heavy off-thesis surface area." MIT license is the
  only green axis.
- **LLM-rewrites-the-prompt loop.** The proposal step is itself a model call, so the
  *mutator* becomes non-deterministic; every rewrite would need cassetting, and a model
  inventing prompt text risks routing fluid/untrusted content onto the instruction path
  (SECURITY.md). Reintroduces the exact determinism + injection problems we are avoiding.
  May return as an *optional, recorded* proposal source later, behind `AgentRuntime`,
  never as the default.
- **Lift DSPy's algorithms but not the package.** Reimplementing MIPROv2's Bayesian
  search is more machinery than our small, mostly-discrete knob space needs; grid + seeded
  random/evolutionary search is sufficient and trivially deterministic.

## Consequences

CRA-176 builds a small, owned, typed `PromptMutator` + deterministic search loop that
reuses `metrics.py`/`eval.py` wholesale and stays reproducible under
`RecordReplayRuntime`. No new runtime dependency enters `pyproject`. The cost is forgoing
DSPy's sophisticated Bayesian instruction-proposal — acceptable because our knob space is
small/typed and the determinism + seam constraints are load-bearing. If a future need for
model-proposed prompt variants is proven, it returns as an optional, cassette-recorded
proposal source behind `AgentRuntime` with its own ADR — never as a hard dependency or a
live-call default.
