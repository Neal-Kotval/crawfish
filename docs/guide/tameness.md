# Taming stochasticity — vote, decline, distil, constrain

One primitive in Crawfish is stochastic: a model `Run`. The control plane wraps it in a
loop, the composition surface gives that loop shape, and the tunable-ML library searches
its knobs. This page is about the fourth move — **bounding the stochastic primitive
itself** — with four disciplines you can layer onto any producing step:

- **[Quorum / self-consistency](#quorum-self-consistency)** — sample the same step `k`
  times and reduce by a deterministic vote, so variance averages out instead of leaking
  through.
- **[Abstention](#abstention)** — let a step *decline* rather than hallucinate, as a
  typed, routable Output value.
- **[The house-guard](#the-house-guard)** — learn a quality rule stochastically, distil it
  to a pure predicate, and let it *earn* the authority to block.
- **[Constrained decoding](#constrained-decoding)** — tell the runtime the output *shape*
  up front, so a malformed value is an impossible state, not a repaired one.

Everything here is real public API, importable from the top-level `crawfish` package, and
runs deterministically under `MockRuntime` / pure functions — no live model call. The
worked thread mirrors the triage demo: an ambiguous ticket is voted on, a low-confidence
answer is declined to review, the house-guard blocks a disallowed label, and a structured
field is filled under a grammar.

On this page:

- [Quorum / self-consistency](#quorum-self-consistency)
- [Abstention as a typed Output discipline](#abstention)
- [The house-guard — learned, distilled, earned](#the-house-guard)
- [Constrained / grammar-guided decoding](#constrained-decoding)
- [How it fits the thesis](#how-it-fits-the-thesis)

## Quorum / self-consistency

Self-consistency — sample `N`, take the consensus — is the cheapest, best-attested
variance reducer there is, and the purest expression of the thesis: **N stochastic leaves
reduced by a deterministic vote**. `QuorumRuntime` is that operator. It wraps any inner
`AgentRuntime`, samples the *same* `RunRequest` `k` times (each a distinct seeded leaf
charging the shared budget), and reduces the `k` results by a typed, pure consensus vote.

```python
from crawfish import QuorumRuntime, majority_vote

quorum = QuorumRuntime(
    inner=base_runtime,               # any AgentRuntime
    k=5,                              # 5 samples; floor is 3
    consensus=majority_vote(field="label"),   # the modal-output estimand
    default_text='{"label": "needs_human"}',  # declared fallback on no-majority
)
winner = await quorum.run(request, ctx)        # -> RunResult (winner text)
detail = await quorum.run_quorum(request, ctx) # -> QuorumResult (winner + taint + tally)
```

Two seams, one for each need:

- **`run(request, ctx) -> RunResult`** is the plain `AgentRuntime` seam — drop
  `QuorumRuntime` in anywhere a runtime is expected and the winner text flows through.
- **`run_quorum(request, ctx) -> QuorumResult`** is the richer shape: the winner
  `RunResult`, the **aggregate taint**, the `ConsensusResult` (tally + runner-up gap), and
  the `Sample`s. `RunResult` carries no taint field (taint lives on `Output`), so the
  aggregate is surfaced here for callers wrapping the winner into an Output.

**The vote is the estimand.** `majority_vote(*, field=None, max_cardinality_ratio=1.0)`
votes for the **modal output**, with *mandatory canonicalization* — `{"a":1,"b":2}` and
`{"b":2,"a":1}` collapse to one candidate, and `field="label"` votes over a dotted
sub-field. Ties break to the first-seen key. When the outputs are all-distinct (plurality
is ill-defined), the vote **abstains** to the declared `default_text`; with no declared
default it raises `QuorumAbstention` — never a silent arbitrary winner (Router dead-letter
parity).

**`k` is a tunable knob.** Left unset, `k` defaults to the Definition's `sample_k` knob
(read via `request.resolved_decode()`), so the Tuner can search the cheapest `k` that hits
a reliability target; an explicit `k` overrides, and `3` is the floor. With
`early_stop=True` the run uses a **sequential proportion test** — it stops once a Wilson
lower bound on the leader's share exceeds `0.5`, or after the pre-registered `k` — so an
easy item costs fewer samples than a contested one, with no peeking penalty.

**Wrap the winner into a typed Output** with `quorum_output`, which carries the aggregate
taint forward:

```python
from crawfish import quorum_output

out = quorum_output(
    detail.winner,
    produced_by="triage#vote",
    tainted=detail.tainted,           # the union across the k samples
    output_schema=triage_schema,
)
```

A vote **does not launder taint**: the consensus winner is tainted iff *any* sample was
tainted (ALG-7). Each sample is an isolated leaf with a distinct derived `decode_seed`
(replayable under a distinct cassette key via the execution coordinate), and the consensus
reduction is **pure** over the recorded sample text — no model call, no I/O, no
wall-clock. The run is bounded by `k` + the cost budget + the cancel token; the tally and
the declared default are static/trusted, never fluid-derived.

## Abstention

Selective prediction — *decline rather than hallucinate* — is the formal frame for a
reliable agent. The tameness layer could already **escalate** (re-run on a stronger model)
but it could never **give up**. Abstention is the missing primitive: a first-class "I
decline to answer" that is a typed Output **value**, not an exception or a magic string.

`abstain_below(threshold, *, field="confidence", reason=None)` is the discipline — it
**measures** the confidence the producing run self-reported (a fluid self-report is data,
never an instruction) and either lets a confident Output through unchanged or returns a
fresh Output carrying an `Abstention`:

```python
from crawfish import abstain_below, is_abstention, Output

decline = abstain_below(0.7)

confident = Output(value={"label": "bug", "confidence": 0.95}, produced_by="triage#1")
uncertain = Output(value={"label": "bug", "confidence": 0.40}, produced_by="triage#2")

decline(confident) is confident      # True — confident enough to act, returned unchanged
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

The `Abstention` is a frozen payload (`reason`, measured `confidence`, the `threshold` it
fell under, the producing run's `tainted` bit, the `field` measured). `as_value()`
serialises it to a JSON dict tagged with `ABSTENTION_MARKER` (`"_abstention"`); the marker
travels **in the value** because no Python type survives a persisted/replayed Output —
that is what keeps it routable. The discipline is **fail-safe**: a confidence below the
threshold *or absent* abstains (declining is always allowed), and it is idempotent — an
already-abstaining Output is returned untouched.

**Abstention is routable.** `is_abstention(value) -> bool` is a pure, total predicate over
any JSON value — hand it to `Classifier.from_predicates` and a `Router` branches a declined
output to review while confident outputs proceed:

```python
from crawfish import Router, Classifier

route = Router(
    Classifier.from_predicates(
        {"review": is_abstention},    # declined -> human review
        default="proceed",
    )
)
```

**Calibrate the threshold, don't guess it.** A raw constant is unsound — it is only right
if the model happens to be calibrated. `abstain_below_calibrated(report, ...)` wires the
discipline to `CalibrationReport.abstention_threshold`, the confidence where observed
accuracy crosses target, read off the [calibration reliability
curve](train-and-tune.md#calibrate-measure-the-noise-band). On a mis-calibrated fixture
this declines answers a naive constant would have acted on. Taint propagates into the
`Abstention` (and lineage threads through `derive`), so an abstention derived from fluid
input stays tainted and can never become a Sink target or idempotency key. An abstaining
run **still charges what it spent** — abstention is post-hoc over the produced Output, not
a refund.

## The house-guard

The house-guard is the deepest expression of the thesis: a program *accretes its own
deterministic invariants*. Quality is **learned stochastically**, **distilled** to a pure
predicate, and only **earns** enforcement after clearing an absolute precision-and-coverage
bar. It is the same earn-the-right-to-gate discipline as the
[`Verifier`](refine-and-verify.md#verifier-a-critic-that-earns-the-right-to-stop-you),
applied to a *learned* rule.

The pipeline has three stages, and only the first touches the model:

1. **Propose** — `propose_rule` mines a `GoldenSet` of corrections and emits a **FLUID**
   candidate rule from a single model `Run` (the one stochastic leaf).
2. **Distil** — `distill` parses that candidate *as data* into a **closed predicate
   grammar**: `Predicate = Comparison | SetMembership | NumericBound | BoolCombination |
   Always`, a fixed, total, side-effect-free AST over typed Output fields, evaluated by an
   interpreter that **never** uses `eval`/`exec`. The fluid proposal can only *select
   within* the grammar — an unknown kind/operator/term raises `GuardGrammarError`; it can
   never *widen* the grammar.
3. **Synthesize** — `HouseGuard.synthesize(predicate, golden, *, precision_floor,
   min_coverage)` validates the distilled predicate against the corpus on a **joint**
   criterion and earns (or withholds) enforcement.

```python
from crawfish import HouseGuard, Comparison

# A distilled predicate: "the label field must never be the empty string"
disallow_empty = Comparison(field="label", op="==", literal="")

guard = HouseGuard.synthesize(
    disallow_empty,
    golden=decisions,                 # a GoldenSet of disallowed/allowed corrections
    precision_floor=0.95,             # Wilson LOWER bound must clear this
    min_coverage=0.30,                # and it must catch enough of the disallowed
)

guard.blocks(output)                  # True only if EARNED *and* stage is BLOCK
guard.require_earned()                # raises GuardNotEarned if it did not earn the right
```

**The gate is joint and honest.** The `GuardCertificate` reports **both** a precision
*lower* bound (Wilson) **and** coverage with a CI. Graduation is `precision_lb >=
precision_floor AND coverage.lo >= min_coverage AND corpus non-empty`. A 99%-precision /
2%-coverage rule therefore **cannot** earn the right to block — high precision on a sliver
of cases is not a guard. It **fails closed**: no corpus ⇒ the guard stays in `warn`, and
`require_earned()` raises `GuardNotEarned`.

`HouseGuard` carries a `GuardStage` (`shadow → warn → block`): `matches()` and
`as_metric()` are pure observation in any stage, but `blocks()` only *enforces* in `BLOCK`.
The guard is content-hashed over the predicate AST (a new rule mints a new sha, never an
edit), carries `org_id`, and is reversible. Expose the distilled predicate as a pure
`Metric` (0/1, $0) with `guard.as_metric()` to track it on a benchmark before you ever let
it block.

**Why it is safe.** The guard is a *consequential authority* — it blocks outputs. Fluid
never *sets* it: the proposer emission is FLUID and is parsed as data into the closed
grammar; authority is conferred only after the corpus (trusted, untainted corrections)
clears the joint bar. Taint propagates from any fluid input into the certificate. Only
`propose_rule` calls the model (replayed via cassette); the distilled predicate is pure
(same input ⇒ same 0/1, $0), so the whole guard runs in tests with no live model call.

## Constrained decoding

Decode-time constraint is *strictly stronger* than the post-hoc validate-and-repair loop.
Instead of detecting a malformed output and paying a metered repair re-prompt to fix it,
the runtime is told the output **shape** up front — so a malformed value becomes an
*impossible* state. A constrained decode is a per-call property of the leaf: it strengthens
determinism and adds **no** new control flow.

A `Grammar` is a frozen, declarative constraint on one decoded field. Build it via the
classmethods, not the raw initializer:

```python
from crawfish import Grammar

label = Grammar.enum(["bug", "feature", "question"])  # snap to a declared member
phone = Grammar.regex(r"\+?\d[\d -]{7,}")            # first match
record = Grammar.json_object(["label", "confidence"]) # recover a balanced object

label.satisfies("bug")          # True — already meets the constraint
label.enforce("looks like a bug to me")   # 'bug' — pure projection onto the surface
```

??? note "▶ Output"

    ```python
    >>> label.satisfies("bug")
    True
    >>> label.enforce("looks like a bug to me")
    'bug'
    ```

`enforce(text)` is a **pure, deterministic** projection of arbitrary text onto the
constraint surface (enum → snap to a declared member; regex → first match; json_object →
recover the first balanced `{...}`, keep declared keys, canonical serialization). It raises
`GrammarError` only when *no* candidate exists at all — never a silent coercion.
`Grammar.from_output_schema(outputs)` derives a grammar from a Definition's declared output
schema, returning `None` when there is nothing to constrain (an empty schema or a single
free-text `str`) so the caller leaves `grammar=None` and degrades to the ordinary validate
path.

Attach a grammar to a `Run` and the step takes the constrained single-agent path — the
grammar serialises onto the per-call `RunRequest.grammar` field, the runtime is invoked,
and `enforce` snaps the result onto the surface so validation passes with **no repair**:

```python
from crawfish import Run

step = Run(triage_definition, grammar=label, decode_seed=7)
# A grammar-honouring constrained decode keeps step.repair_count at 0;
# the unconstrained path that emits prose -> NOT_JSON increments it.
```

`Run.repair_count` is the observability counter: a grammar-honouring constrained decode
keeps it at **0** (the acceptance criterion); the unconstrained repair path increments it.
Passing `grammar=None` opts out even when the schema could yield one (the "let me speak
freely" caveat), and the ordinary validate path is unchanged.

**Why it is safe.** The grammar is **static / trusted** — it is built from a Definition's
declared output schema or from author constants, and has **no constructor that reads a
fluid value**, so untrusted session data cannot set the constraint. The prompt-injection
boundary holds: the constraint is config, not session data. `grammar` is a per-call
property kept **out of** the Definition content hash (it constrains the decode surface, it
does not version the agent); the output-affecting `decode_seed` enters run identity via the
replay cassette key, so two decode settings never collide on one cassette. `parse_grammar`
is the inverse of `to_request_grammar` — a runtime reads the request's grammar string back
into a typed constraint, then applies `enforce`.

## How it fits the thesis

Every move on this page bounds the *one* stochastic primitive without touching the
deterministic, typed, versioned spine around it:

| Discipline | What it does to the stochastic leaf |
| --- | --- |
| **Quorum** | vote it down — `k` samples reduced by a pure consensus |
| **Abstention** | let it decline — a typed, routable "I'm not sure" instead of a guess |
| **House-guard** | distil its invariants — learn a rule stochastically, enforce it purely |
| **Constrained decode** | constrain its surface — make a malformed shape impossible |

The house-guard is the keystone: **learn stochastically → distil to a pure predicate →
earn enforcement**. It turns a lesson the model taught you into a deterministic invariant
the program now owns — the same shape as a `Verifier` earning the right to gate, or a
`GatedVerifier` earning the right to stop a `Refine` loop. The stochastic part stays
contained; the program keeps accreting determinism.

## See also

- [Concepts → taming the stochastic primitive](concepts.md#taming-the-stochastic-primitive-vote-decline-distil-constrain) — the thesis framing.
- [Refine & verify](refine-and-verify.md) — the control-plane loop these disciplines plug into; the `Verifier`'s earn-the-right-to-gate pattern the house-guard mirrors.
- [Train, calibrate & promote](train-and-tune.md) — `calibrate` and the reliability curve that grounds `abstain_below_calibrated`.
- [Aggregator reference](../reference/nodes-aggregator.md) — where the consensus vote sits in the reduce layer.
- [Validation reference](../reference/validation.md) — the repair path constrained decoding short-circuits.
- [API reference](api-reference.md) — exact signatures for every symbol on this page.
