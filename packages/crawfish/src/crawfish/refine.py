"""Refine — the bounded, metered, durable iterate-until-goal operator (CL-1, CL-4).

A hand-rolled ``while`` loop around a model call is the wrong easy path: it bypasses
the shared :class:`~crawfish.core.context.CostBudget` (a fresh ``Run`` would default an
*unbounded* budget), loses per-iteration checkpointing, and reports ``spent=0.0``.
:class:`Refine` makes the bounded loop the easy path. It runs a producing
:class:`~crawfish.definition.types.Definition` (the ``body``), checks each frozen
:class:`~crawfish.output.Output` against an **external** :class:`StopCondition`, and
loops until the condition is satisfied OR a bound is hit — never past ``max_iters``
iterations, never past the shared budget, never on wall-clock.

It generalises the three fixed-bound re-run atoms — ``EscalatingRuntime`` (2×),
``Run._repair`` (+1), ``RetryPolicy`` (on-exception) — into one goal-driven operator.

**The stop signal is external (CL-1 safety).** The thing that decides "good enough" is
never the generator critiquing itself: it is a :class:`~crawfish.metrics.Rubric`
threshold, a typed predicate, or a *gated* :class:`~crawfish.verifier.Verifier` (CL-2)
that has earned the right to block. An assembly check forbids a :class:`VerifierStop`
whose critic Definition is the same content-hashed version as the ``body``.

**Determinism.** Exactly one stochastic leaf per iteration (the body ``Run.execute``,
plus the verifier's own leaf when a :class:`VerifierStop` is used); the loop counter,
stop check, no-progress test, and best-tracking are pure. **One shared**
:class:`~crawfish.core.context.CostBudget` is threaded into every inner ``Run`` — never
a fresh ``RunContext`` — and every call is preflighted against the remaining budget, so
the loop stops without exceeding the cap by more than one worst-case call. Feedback from
the prior attempt is fed back as a **FLUID** input (taint propagates; it never becomes
an instruction). The body stays frozen (eval mode); each iteration produces a fresh
frozen ``Output`` via :meth:`Output.derive`.

**Durability (CL-4).** Each iteration's frozen ``Output`` is checkpointed into the F-2
composite-key :class:`~crawfish.ledger.ExecutionLedger`, keyed by the deterministic
``loop_id`` (:func:`~crawfish.ledger.compute_loop_id`, never ``new_id()``) and the
``iter_index`` coordinate. On ``resume=True`` the completed iterations are loaded from
the ledger and the inner ``Run`` replays from its F-1 cassette under a replay runtime —
so a loop that crashed at iteration 3 of 5 resumes at iteration 4 re-paying **$0**.
Because the cassette key folds ``iter_index``, the replayed continuation is
content-hash-verified, not trusted. The checkpoint over (body output + verifier verdict)
is atomic: a crash between the two never double-charges or skips the verifier.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias

from crawfish.core.context import RunContext
from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue, Node, NodeKind, Parameter
from crawfish.definition.types import Definition
from crawfish.ledger import ExecutionLedger, compute_loop_id
from crawfish.metrics import Rubric
from crawfish.output import Output, output_content_sha
from crawfish.run import Run
from crawfish.runtime.base import AgentRuntime
from crawfish.verifier import GatedVerifier

__all__ = [
    "StopCondition",
    "RubricThreshold",
    "PredicateStop",
    "VerifierStop",
    "RefineResult",
    "Refine",
    "feature_loop",
]

# The FLUID input slot the prior attempt is fed back through. STATIC by construction —
# the key is a fixed literal, never derived from fluid input.
DEFAULT_FEEDBACK_KEY = "_refine_feedback"


# -- stop conditions --------------------------------------------------------
class StopCondition(ABC):
    """The EXTERNAL stop signal for a :class:`Refine` loop.

    A stop condition decides whether an iteration's frozen ``Output`` is "good enough"
    (:meth:`satisfied`) and ranks candidates so the loop can return its best attempt on
    exhaustion (:meth:`progress`). It is external on purpose: the generator never
    critiques itself (see :class:`VerifierStop`'s assembly check).
    """

    @abstractmethod
    async def satisfied(
        self, output: Output[JSONValue], ctx: RunContext, runtime: AgentRuntime
    ) -> bool:
        """Whether ``output`` clears the goal. May run a leaf (``VerifierStop``)."""

    @abstractmethod
    def progress(self, output: Output[JSONValue]) -> float:
        """A pure ranking score in ``[0, 1]`` — higher is closer to the goal.

        Used both for best-tracking (return the best attempt on exhaustion) and for the
        noise-aware no-progress test. Pure: no model call, no I/O.
        """


class RubricThreshold(StopCondition):
    """Stop when a :class:`~crawfish.metrics.Rubric` metric clears a threshold.

    ``rubric.score(output)[metric] >= at_least`` satisfies; :meth:`progress` returns the
    same metric clamped to ``[0, 1]``. Pure (the rubric scores frozen Output data),
    so it adds no stochastic leaf — the body ``Run`` remains the only model call.
    """

    def __init__(self, rubric: Rubric, *, metric: str, at_least: float) -> None:
        self.rubric = rubric
        self.metric = metric
        self.at_least = at_least

    async def satisfied(
        self, output: Output[JSONValue], ctx: RunContext, runtime: AgentRuntime
    ) -> bool:
        return self.progress(output) >= self.at_least

    def progress(self, output: Output[JSONValue]) -> float:
        score = self.rubric.score(output).get(self.metric, 0.0)
        return max(0.0, min(1.0, score))


# A typed predicate over a frozen Output. STATIC/trusted — supplied by the author.
StopPredicate = Callable[[Output[JSONValue]], bool]
ProgressFn = Callable[[Output[JSONValue]], float]


class PredicateStop(StopCondition):
    """Stop on a typed predicate over the frozen ``Output``.

    The predicate reads the Output as data; ``progress`` defaults to ``1.0`` when the
    predicate holds and ``0.0`` otherwise (override via ``progress`` for finer ranking).
    """

    def __init__(self, predicate: StopPredicate, *, progress: ProgressFn | None = None) -> None:
        self._predicate = predicate
        self._progress = progress

    async def satisfied(
        self, output: Output[JSONValue], ctx: RunContext, runtime: AgentRuntime
    ) -> bool:
        return bool(self._predicate(output))

    def progress(self, output: Output[JSONValue]) -> float:
        if self._progress is not None:
            return max(0.0, min(1.0, self._progress(output)))
        return 1.0 if self._predicate(output) else 0.0


class VerifierStop(StopCondition):
    """Stop when a **gated** :class:`~crawfish.verifier.Verifier` accepts the Output (CL-2).

    Only a :class:`~crawfish.verifier.GatedVerifier` is admitted: a critic must have
    earned the right to block (cleared the absolute-precision bar) before it can stop a
    loop, exactly as a :class:`~crawfish.nodes.sink.Sink` target is consequential. The
    verifier's critic call is the loop's second stochastic leaf per iteration (it
    replays via cassette under a mock/replay runtime).

    The critic emission is FLUID and parsed purely as data against the verifier's static
    closed label set — an unparseable emission falls to ``default``, never a silent pass.
    ``progress`` is pure: ``1.0`` once a verdict has accepted, else ``0.0`` (the verdict
    is binary; rank with a :class:`RubricThreshold` if a gradient is needed).
    """

    def __init__(self, verifier: GatedVerifier) -> None:
        if not verifier.can_block:
            # Defensive: GatedVerifier always can_block, but a future subclass must not
            # smuggle a non-gated critic into a stop position.
            raise ValueError("VerifierStop requires a gated verifier (one that can block)")
        self.verifier = verifier
        self._accepted = False

    async def satisfied(
        self, output: Output[JSONValue], ctx: RunContext, runtime: AgentRuntime
    ) -> bool:
        verdict = await self.verifier.verdict(output, ctx, runtime)
        self._accepted = self.verifier.accepts(verdict)
        return self._accepted

    def progress(self, output: Output[JSONValue]) -> float:
        return 1.0 if self._accepted else 0.0


# How one iteration produces its body Output. STATIC/trusted: supplied by the author or
# defaulted to a single Run of the body. Must thread the SHARED ctx so spend meters into
# the one budget.
ProduceFn: TypeAlias = Callable[
    [Output[JSONValue], int, RunContext, AgentRuntime], Awaitable[Output[JSONValue]]
]


# -- result -----------------------------------------------------------------
@dataclass(frozen=True)
class RefineResult:
    """The typed outcome of a :class:`Refine` loop.

    ``output`` is the accepted attempt (or the best-ranked one on exhaustion).
    ``refine_iters`` is the number of body executions actually *run this invocation*
    (replayed-on-resume iterations are not re-counted as fresh spend). ``spent_usd`` is
    the *true* delta charged to the shared budget over this invocation (Gap #3 closed).
    ``refine_stopped`` records why the loop ended.
    """

    output: Output[JSONValue]
    refine_iters: int
    spent_usd: float
    refine_stopped: Literal["satisfied", "exhausted", "no_progress", "stuck"]
    best_progress: float


class Refine(Node):
    """A bounded, metered, durable iterate-until-goal loop over a producing Definition.

    The body Definition is run, its frozen Output checked against ``until``
    (:class:`StopCondition`), and the loop repeats — feeding the prior attempt back as a
    FLUID input — until the condition is satisfied OR a bound is hit (``max_iters``,
    the shared budget, cooperative cancel, or noise-aware no-progress). It mutates
    nothing: every attempt is a fresh frozen Output, and the body stays frozen.
    """

    kind = NodeKind.AGGREGATOR  # reduce-shaped: many attempts -> one chosen Output.
    # The spec's intended NodeKind "refine" is recorded here for telemetry/CLI; the
    # core NodeKind enum is owned elsewhere, so we tag the operator without widening it.
    node_kind_tag = "refine"

    def __init__(
        self,
        body: Definition,
        until: StopCondition,
        *,
        max_iters: int,
        feedback_key: str = DEFAULT_FEEDBACK_KEY,
        no_progress_patience: int = 1,
        rubric_std: float = 0.0,
        on_stuck: Literal["abstain", "escalate", "return_best"] = "return_best",
        edge_id: str = "refine",
        name: str = "refine",
    ) -> None:
        if max_iters < 1:
            raise ValueError("max_iters must be >= 1")
        if no_progress_patience < 1:
            raise ValueError("no_progress_patience must be >= 1")
        # Assembly check (CL-1 safety): a VerifierStop's critic must be a DISTINCT
        # Definition version from the body — the generator may never critique itself.
        if isinstance(until, VerifierStop):
            critic = until.verifier.definition
            if critic.content_sha() == body.content_sha():
                raise ValueError(
                    "Refine stop signal must be external: the verifier's critic "
                    "Definition is the same version as the body (self-critique forbidden)"
                )
        self.id = new_id()
        self.name = name
        self.body = body
        self.until = until
        self.max_iters = max_iters
        self.feedback_key = feedback_key
        self.no_progress_patience = no_progress_patience
        self.rubric_std = rubric_std
        self.on_stuck = on_stuck
        self.edge_id = edge_id

    # -- durability hook (CL-4) --------------------------------------------
    def _checkpoint(
        self,
        ledger: ExecutionLedger,
        loop_id: str,
        item_id: str,
        visit: int,
        output: Output[JSONValue],
    ) -> None:
        """Persist one completed iteration's frozen Output into the F-2 ledger.

        Atomic over the iteration: the checkpoint is written only after the body Output
        (and, for a :class:`VerifierStop`, its verdict) is in hand, so a crash between
        the body and verifier calls leaves no half-checkpointed iteration — resume
        re-runs that iteration (replaying $0) rather than skipping the verifier. Only a
        frozen ``Output`` reference (its content sha) is recorded, never a mutable
        channel; the row carries ``org_id`` so a cross-tenant resume cannot see it.
        """
        ledger.checkpoint_iteration(
            loop_id, item_id, self.edge_id, visit, output_content_sha(output)
        )

    def _loop_id(self, item_lineage: str) -> str:
        """The deterministic loop identity (never ``new_id()``), per F-2.

        Derived purely from the body version, the item lineage, and the back-edge id, so
        two independent process invocations of the same loop re-derive the same id and
        resume re-charges $0 for completed iterations.
        """
        return compute_loop_id(self.body.content_sha(), item_lineage, self.edge_id)

    # -- execution ----------------------------------------------------------
    async def execute(
        self,
        seed: Output[JSONValue],
        ctx: RunContext,
        runtime: AgentRuntime,
        *,
        ledger: ExecutionLedger | None = None,
        resume: bool = False,
        produce: ProduceFn | None = None,
    ) -> RefineResult:
        """Run the loop on a ``seed`` Output until ``until`` is satisfied or a bound hits.

        ``seed`` is the initial input Output (its value/lineage/taint seed the first body
        run). ``ledger`` enables durable checkpointing (CL-4); with ``resume=True`` the
        already-committed iterations are loaded from it and re-run under the (replay)
        runtime at $0 before any fresh work. ``produce`` overrides how one iteration runs
        its body (defaults to a single :class:`~crawfish.run.Run` of ``body``); it must
        thread the *shared* ``ctx`` so spend meters into the one budget.
        """
        item_lineage = seed.lineage or seed.id
        item_id = item_lineage
        loop_id = self._loop_id(item_lineage)
        run_body = produce or self._default_produce

        # True spend is the delta on the SHARED budget over this invocation only — the
        # spent=0.0 gap is closed by reading the budget the concrete runtime charges.
        spent_at_entry = ctx.cost_budget.spent_usd

        completed: set[int] = set()
        if ledger is not None and resume:
            completed = ledger.completed_visits(loop_id, item_id, self.edge_id)

        best_output: Output[JSONValue] = seed
        best_progress = self.until.progress(seed)
        prev_output: Output[JSONValue] = seed
        stale_streak = 0
        iters_run = 0
        stopped: Literal["satisfied", "exhausted", "no_progress", "stuck"] = "exhausted"

        for visit in range(self.max_iters):
            ctx.cancel_token.raise_if_cancelled()

            replaying = visit in completed
            if not replaying:
                # Preflight: never START a metered call with no headroom. A None ceiling
                # is unbounded (local dev). This bounds the overshoot to one worst-case
                # call — remaining<=0 means we stop before the next charge.
                remaining = ctx.cost_budget.remaining_usd
                if remaining is not None and remaining <= 0.0:
                    stopped = "exhausted"
                    break

            output = await run_body(prev_output, visit, ctx, runtime)
            iters_run += 1

            # Check the external stop signal (a VerifierStop may add its own leaf here).
            satisfied = await self.until.satisfied(output, ctx, runtime)

            # Atomic checkpoint over (body output + verdict): both are now in hand, so a
            # crash before this point re-runs the iteration; after it, resume skips it.
            if ledger is not None:
                self._checkpoint(ledger, loop_id, item_id, visit, output)

            cur_progress = self.until.progress(output)
            if cur_progress >= best_progress:
                best_progress = cur_progress
                best_output = output

            if satisfied:
                stopped = "satisfied"
                best_output = output
                best_progress = cur_progress
                prev_output = output
                break

            # Noise-aware no-progress: an improvement inside the calibrated band
            # (``rubric_std``, F-8) is treated as no progress — compared on the ranking
            # delta, never byte-identical sha. Replayed iterations don't count toward
            # the stale streak (they re-pay nothing and carry no fresh signal).
            if not replaying:
                delta = cur_progress - self.until.progress(prev_output)
                if delta <= self.rubric_std:
                    stale_streak += 1
                else:
                    stale_streak = 0
                if stale_streak >= self.no_progress_patience:
                    stopped = "no_progress"
                    prev_output = output
                    break

            prev_output = output

        # Honest spend: the delta the concrete runtime charged to the shared budget.
        spent = ctx.cost_budget.spent_usd - spent_at_entry

        if stopped in ("no_progress", "exhausted") and self.on_stuck == "abstain":
            stopped = "stuck"

        return RefineResult(
            output=best_output,
            refine_iters=iters_run,
            spent_usd=spent,
            refine_stopped=stopped,
            best_progress=best_progress,
        )

    async def _default_produce(
        self,
        prior: Output[JSONValue],
        visit: int,
        ctx: RunContext,
        runtime: AgentRuntime,
    ) -> Output[JSONValue]:
        """Run one body iteration as a single leaf, feeding the prior attempt as FLUID.

        The prior attempt is bound under ``feedback_key`` as an ordinary (fluid) input —
        taint propagates, and the prompt compiler keeps it in the data block, never the
        instruction slot. The body Definition is frozen (eval mode); the shared ``ctx``
        is threaded so the one budget meters this call and the F-1 cassette key folds the
        ``iter_index`` coordinate for a distinct, replayable record per iteration.
        """
        inputs: dict[str, JSONValue] = {self.feedback_key: prior.value}
        for param in self.body.inputs:
            if param.required and param.default is None and param.name != self.feedback_key:
                inputs.setdefault(param.name, prior.value)
        run = Run(
            self.body,
            inputs,
            validate_input_types=False,
            validate_output_schema=False,
        )
        out = await run.execute(ctx, runtime)
        # Re-derive a fresh frozen Output carrying the prior lineage and unioned taint,
        # so each iteration is a content-addressed CoW step (never an in-place mutation).
        # ``produced_by`` is a DETERMINISTIC coordinate (body version + visit), never the
        # volatile per-instance ``Run.id``: a resume in a second process must reproduce a
        # bit-identical Output (its content sha is verified against the checkpoint), which
        # is impossible if the producer id is a fresh UUID each run.
        return out.derive(
            value=out.value,
            produced_by=f"{self.body.content_sha()}#{visit}",
            tainted=bool(out.tainted or prior.tainted),
            lineage=prior.lineage or prior.id,
        )


def feature_loop(
    body: Definition,
    *,
    until: StopCondition,
    max_iters: int,
    **kwargs: object,
) -> Refine:
    """Convenience alias matching the vision vocabulary: a feature-improvement loop.

    Identical to constructing :class:`Refine` directly; the keyword-only form reads as
    "loop this feature body until ``until``, but never past ``max_iters``".
    """
    return Refine(body, until, max_iters=max_iters, **kwargs)  # type: ignore[arg-type]


# The output schema a Refine result satisfies downstream (the chosen attempt carried as
# typed structural data alongside the stop reason).
REFINE_RESULT_SCHEMA: list[Parameter] = [
    Parameter(name="refine_iters", type="int"),
    Parameter(name="spent_usd", type="float"),
    Parameter(name="refine_stopped", type="str"),
]
