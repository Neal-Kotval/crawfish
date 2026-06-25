# Taming stochasticity: vote, decline, distil, constrain

A model call is the one part of a Crawfish pipeline that is not deterministic: ask the same question twice and you can get two answers. This page shows four ways to bound that randomness, each of which you can add to any step that calls a model:

- [Quorum](#quorum): sample a step several times and take the consensus, so the noise averages out.
- [Abstention](#abstention): let a step say "I'm not sure" as a typed value you can route, instead of guessing.
- [The house-guard](#the-house-guard): learn a quality rule, turn it into a plain checker, and let it block bad output only after it proves it is accurate.
- [Constrained decoding](#constrained-decoding): tell the model the exact output shape up front, so a malformed value cannot happen.

Everything here is public API you import from the top-level `crawfish` package, and every example runs deterministically under `MockRuntime` or pure functions, with no live model call. The worked thread follows the triage demo: an ambiguous ticket gets voted on, a low-confidence answer is sent to review, the house-guard blocks a disallowed label, and a structured field is filled under a fixed shape.

## Quorum

The cheapest way to reduce noise is to sample a step several times and take the answer that comes up most. `QuorumRuntime` does this. It wraps any inner `AgentRuntime`, runs the same request `k` times (each a separately seeded call charging the shared budget), and reduces the results with a pure consensus vote.

```python
from crawfish import QuorumRuntime, majority_vote

quorum = QuorumRuntime(
    inner=base_runtime,               # any AgentRuntime
    k=5,                              # 5 samples; the floor is 3
    consensus=majority_vote(field="label"),   # vote on the most common output
    default_text='{"label": "needs_human"}',  # fallback when there is no majority
)
winner = await quorum.run(request, ctx)        # -> RunResult (the winning text)
detail = await quorum.run_quorum(request, ctx) # -> QuorumResult (winner + taint + tally)
```

There are two ways to call it, one for each need:

- `run(request, ctx)` returns a `RunResult`. This is the plain `AgentRuntime` interface, so you can drop `QuorumRuntime` in anywhere a runtime is expected and the winning text flows through.
- `run_quorum(request, ctx)` returns a `QuorumResult` with more detail: the winning `RunResult`, the combined taint, the `ConsensusResult` (the tally and the gap to the runner-up), and every `Sample`. A `RunResult` has no taint field, so this is where you read the combined taint when you wrap the winner into an `Output`.

`majority_vote(*, field=None, max_cardinality_ratio=1.0)` picks the most common output. It canonicalizes first, so `{"a":1,"b":2}` and `{"b":2,"a":1}` count as the same answer, and `field="label"` votes over one sub-field. Ties break to the first answer seen. When every sample is different and there is no plurality, the vote falls back to `default_text`; with no declared default it raises `QuorumAbstention` rather than pick an arbitrary winner.

Left unset, `k` defaults to the agent's `sample_k` knob, so the tuner can search for the cheapest `k` that hits a reliability target. An explicit `k` overrides that, and `3` is the floor. With `early_stop=True` the run uses a sequential test: it stops once it is statistically confident in the leader, or after `k` samples, so an easy item costs fewer samples than a contested one with no penalty for stopping early.

Wrap the winner into a typed `Output` with `quorum_output`, which carries the combined taint forward:

```python
from crawfish import quorum_output

out = quorum_output(
    detail.winner,
    produced_by="triage#vote",
    tainted=detail.tainted,           # the union across the k samples
    output_schema=triage_schema,
)
```

A vote does not clean taint. The winner is tainted if any sample was tainted. Each sample is an isolated call with its own derived seed, and the vote itself is pure over the recorded sample text: no model call, no I/O, no clock. The run is bounded by `k`, the cost budget, and the cancel token, and both the tally and the declared default are trusted config, never derived from untrusted input.

## Abstention

A reliable agent should be able to decline rather than make something up. Crawfish lets a step return "I decline to answer" as a typed `Output` value, not an exception or a magic string, so you can route it like any other result.

`abstain_below(threshold, *, field="confidence", reason=None)` reads the confidence the step reported about itself and either passes a confident output through unchanged or returns a fresh output carrying an `Abstention`. A self-reported confidence is data, never an instruction.

```python
from crawfish import abstain_below, is_abstention, Output

decline = abstain_below(0.7)

confident = Output(value={"label": "bug", "confidence": 0.95}, produced_by="triage#1")
uncertain = Output(value={"label": "bug", "confidence": 0.40}, produced_by="triage#2")

decline(confident) is confident      # True: confident enough to act, returned unchanged
declined = decline(uncertain)        # a fresh Output carrying an Abstention
is_abstention(declined.value)        # True
```

??? note "▶ Output"

    ```python
    >>> decline(confident) is confident
    True
    >>> declined.value
    {'_abstention': True,
     'reason': 'measured confidence 0.40 below threshold 0.7',
     'confidence': 0.4,
     'threshold': 0.7,
     'field': 'confidence'}
    >>> is_abstention(declined.value)
    True
    ```

An `Abstention` is a frozen record: the reason, the measured confidence, the threshold it fell under, the producing run's taint bit, and the field that was measured. `as_value()` serializes it to a JSON dict tagged with `ABSTENTION_MARKER` (`"_abstention"`). The marker lives inside the value because no Python type survives being saved and replayed, and keeping it in the value is what lets you route it. The check is safe by default: a confidence below the threshold, or missing entirely, abstains. It is also idempotent, so an already-abstaining output is returned untouched.

You can route an abstention. `is_abstention(value) -> bool` is a pure check over any JSON value, so hand it to `Classifier.from_predicates` and a `Router` sends a declined output to review while confident ones proceed:

```python
from crawfish import Router, Classifier

route = Router(
    Classifier.from_predicates(
        {"review": is_abstention},    # declined -> human review
        default="proceed",
    )
)
```

Calibrate the threshold instead of guessing it. A fixed constant is only correct if the model's reported confidence happens to match its real accuracy. `abstain_below_calibrated(report, ...)` ties the threshold to `CalibrationReport.abstention_threshold`, the confidence where observed accuracy crosses your target, read from the calibration curve described in [Train, calibrate, and promote](train-and-tune.md#measure-the-noise-band-with-calibrate). On a poorly calibrated model this declines answers a fixed constant would have acted on. Taint propagates into the `Abstention`, so an abstention derived from untrusted input stays tainted and can never become a sink target or idempotency key. An abstaining run still pays for what it spent: abstention happens after the output is produced, it is not a refund.

## The house-guard

The house-guard turns a quality lesson into a rule your program enforces on its own. The quality rule is learned with a model, then turned into a plain checker, and it earns the authority to block output only after it clears a precision-and-coverage bar. This is the same earn-the-right-to-block pattern as the [`Verifier`](refine-and-verify.md#gate-a-verifier), here applied to a learned rule.

The pipeline has three stages, and only the first calls a model:

1. Propose: `propose_rule` reads a `GoldenSet` of past corrections and emits a candidate rule from one model call. This is the only stochastic step, and its output is untrusted.
2. Distil: `distill` parses that candidate as data into a closed checker grammar: `Predicate = Comparison | SetMembership | NumericBound | BoolCombination | Always`. This is a fixed, total, side-effect-free expression over typed output fields, run by an interpreter that never uses `eval` or `exec`. The untrusted proposal can only pick within this grammar. An unknown kind, operator, or term raises `GuardGrammarError`, and the proposal can never widen the grammar.
3. Synthesize: `HouseGuard.synthesize(predicate, golden, *, precision_floor, min_coverage)` tests the checker against the corpus and either grants or withholds enforcement.

```python
from crawfish import HouseGuard, Comparison

# A distilled checker: "the label field must never be the empty string"
disallow_empty = Comparison(field="label", op="==", literal="")

guard = HouseGuard.synthesize(
    disallow_empty,
    golden=decisions,                 # a GoldenSet of disallowed/allowed corrections
    precision_floor=0.95,             # the lower bound on precision it must clear
    min_coverage=0.30,                # and it must catch enough of the disallowed cases
)

guard.blocks(output)                  # True only if it earned the right AND its stage is BLOCK
guard.require_earned()                # raises GuardNotEarned if it did not earn the right
```

The gate checks two things at once. The `GuardCertificate` reports both a lower bound on precision and a coverage figure with a confidence interval. The guard graduates only when precision clears `precision_floor`, coverage clears `min_coverage`, and the corpus is non-empty. So a rule that is 99% precise but catches only 2% of cases cannot earn the right to block: high precision on a sliver of cases is not a useful guard. With no corpus the guard stays in `warn` and `require_earned()` raises `GuardNotEarned`.

A `HouseGuard` moves through three stages, `shadow → warn → block`. `matches()` and `as_metric()` observe in any stage, but `blocks()` only enforces in `BLOCK`. The guard is content-hashed over its checker, so a new rule mints a new hash rather than editing the old one, and it carries an `org_id` and is reversible. Expose the checker as a pure `Metric` with `guard.as_metric()` (scored 0 or 1, costing nothing) to watch it on a benchmark before you ever let it block.

The guard is an authority that blocks output, so untrusted input is never allowed to set it. The proposer's output is untrusted and is parsed only as data into the closed grammar. Authority is granted only after the trusted corpus of corrections clears the bar. Taint propagates from any untrusted input into the certificate. Only `propose_rule` calls the model, replayed from a recording, and the checker itself is pure, so the whole guard runs in tests with no live model call.

## Constrained decoding

Constraining the output at decode time is stronger than checking and repairing it afterward. Instead of detecting a malformed output and paying for a repair prompt to fix it, you tell the model the output shape up front, so a malformed value cannot happen. A constrained decode is a property of a single call. It adds no new control flow.

A `Grammar` is a frozen rule on one decoded field. Build it with the class methods, not the raw initializer:

```python
from crawfish import Grammar

label = Grammar.enum(["bug", "feature", "question"])  # snap to a declared member
phone = Grammar.regex(r"\+?\d[\d -]{7,}")            # first match
record = Grammar.json_object(["label", "confidence"]) # recover a balanced object

label.satisfies("bug")          # True: already meets the constraint
label.enforce("looks like a bug to me")   # 'bug': projected onto the allowed surface
```

??? note "▶ Output"

    ```python
    >>> label.satisfies("bug")
    True
    >>> label.enforce("looks like a bug to me")
    'bug'
    ```

`enforce(text)` is a pure, deterministic projection of any text onto the constraint: an enum snaps to a declared member, a regex returns the first match, a json_object recovers the first balanced `{...}`, keeps the declared keys, and serializes it the same way every time. It raises `GrammarError` only when no candidate exists at all, never coercing silently. `Grammar.from_output_schema(outputs)` builds a grammar from an agent's declared output schema, returning `None` when there is nothing to constrain (an empty schema or a single free-text `str`), so the caller leaves `grammar=None` and falls back to the ordinary validate path.

Attach a grammar to a `Run` and the step takes the constrained path. The grammar travels on the per-call `RunRequest.grammar` field, the runtime is invoked, and `enforce` snaps the result onto the allowed surface so validation passes with no repair:

```python
from crawfish import Run

step = Run(triage_definition, grammar=label, decode_seed=7)
# A grammar-honouring constrained decode keeps step.repair_count at 0;
# the unconstrained path that emits prose -> NOT_JSON increments it.
```

`Run.repair_count` is the counter to watch: a constrained decode that honours the grammar keeps it at 0, while the unconstrained repair path increments it. Passing `grammar=None` opts out even when the schema could produce a grammar (the "let me speak freely" case), and the ordinary validate path is unchanged.

The grammar is trusted config. It comes from an agent's declared output schema or from author constants, and it has no constructor that reads an untrusted value, so untrusted session data cannot set the constraint. The grammar is a per-call property and is kept out of the agent's content hash, since it shapes the decode rather than versioning the agent. The output-affecting `decode_seed` does enter run identity through the replay key, so two decode settings never collide on one recording. `parse_grammar` is the inverse of `to_request_grammar`: a runtime reads the request's grammar string back into a typed constraint, then applies `enforce`.

## How the four moves relate

Each move bounds the one stochastic step in a different way, without touching the typed, versioned pipeline around it.

| Discipline | What it does to the model call |
| --- | --- |
| Quorum | Votes it down: `k` samples reduced by a pure consensus. |
| Abstention | Lets it decline: a typed, routable "I'm not sure" instead of a guess. |
| House-guard | Distils its lessons: learn a rule with a model, enforce it as a plain checker. |
| Constrained decode | Constrains its shape: a malformed value cannot happen. |

The house-guard is the fullest version of the pattern: learn a rule with a model, distil it to a plain checker, then earn the right to enforce it. It turns a lesson the model taught you into a rule your program owns, the same shape as a `Verifier` earning the right to gate or a `GatedVerifier` earning the right to stop a `Refine` loop.

## Next steps

- [Refine and verify](refine-and-verify.md): the loop these disciplines plug into, and the `Verifier` pattern the house-guard mirrors.
- [Train, calibrate, and promote](train-and-tune.md): `calibrate` and the reliability curve behind `abstain_below_calibrated`.
- [Aggregator reference](../reference/nodes-aggregator.md): where the consensus vote sits in the reduce layer.
- [API reference](api-reference.md): exact signatures for every symbol on this page.
