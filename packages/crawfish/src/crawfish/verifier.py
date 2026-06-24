"""Verifier — the gated external-signal critic (CL-2).

``Refine``'s safety rests on an external stop signal: a critic that can *block* a
loop is as consequential as a :class:`~crawfish.nodes.sink.Sink`, so a critic must
**earn** the right to gate. A :class:`Verifier` wraps a critic
:class:`~crawfish.definition.types.Definition` (its own version, knobs,
:class:`~crawfish.metrics.Rubric`) and exposes :meth:`verdict` over a CLOSED label
set with a MANDATORY ``default`` — mirroring
:class:`~crawfish.nodes.router.Classifier` (``router.py``): an unparseable critic
emission falls to ``default``, never a silent pass.

The gating authority is itself typed. A bare :class:`Verifier` can *describe* an
output but may not stop a loop. Only :meth:`Verifier.gated` admits one as a
:class:`GatedVerifier` (a usable ``VerifierStop`` source), and only **after** it
clears an **absolute precision** bar against a decision
:class:`~crawfish.eval.GoldenSet` via the F-3 :func:`~crawfish.eval.precision_gate`
— which **fails closed**: a never-benchmarked critic raises
:class:`~crawfish.eval.VerifierNotGated` rather than being admitted by default (the
CL-2 safety inversion). Below the bar the critic stays in ``warn``/``shadow`` and
cannot block.

**Determinism.** The critic call is a single leaf :class:`~crawfish.run.Run`
(replays via cassette under a mock/replay runtime); the label parse and precision
computation are pure. **Security.** The critic output reaching the verdict body is
FLUID (untrusted model output) — it is parsed *as data* against a static, trusted
label set, never executed as instruction; the label set / ``default`` / gating
authority are static and never derived from fluid input. Taint propagates from the
critic's :class:`~crawfish.output.Output` into the verdict's lineage.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum

from crawfish.core.context import RunContext
from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue, Parameter
from crawfish.definition.types import Definition
from crawfish.eval import GoldenSet, VerifierNotGated, load_baseline, precision_gate
from crawfish.metrics import Rubric
from crawfish.output import Output
from crawfish.run import Run
from crawfish.runtime.base import AgentRuntime
from crawfish.typesystem.registry import TypeRegistry, default_registry

__all__ = [
    "VerifierStage",
    "Verdict",
    "Verifier",
    "GatedVerifier",
]


class VerifierStage(str, Enum):
    """The shadow→warn→block lifecycle of a critic's gating authority.

    A critic earns authority by clearing the precision bar (see
    :meth:`Verifier.gated`). Below the bar it stays in ``SHADOW``/``WARN`` and
    **cannot** block a loop; only a :class:`GatedVerifier` reaches ``BLOCK``.
    """

    SHADOW = "shadow"  # observed only — verdict recorded, never acted on
    WARN = "warn"  # surfaced as a warning, still cannot stop a loop
    BLOCK = "block"  # gated: may stop a Refine loop (as consequential as a Sink)


@dataclass(frozen=True)
class Verdict:
    """The typed result of one verification: a closed-set label over an Output.

    ``label`` is always one of the verifier's declared ``labels`` (``default`` when
    the critic's emission did not parse). ``tainted`` carries the lineage of the
    verified Output: a verdict over fluid (untrusted) data is itself tainted, so a
    consequential consumer can refuse to treat a fluid-derived verdict as trusted
    ground truth.
    """

    label: str
    tainted: bool
    source_output_id: str
    lineage: str | None = None


def _normalise(text: str, labels: Sequence[str], default: str) -> str:
    """Map a critic's free-form emission to one of ``labels`` (``default`` on no match).

    Mirrors :func:`crawfish.nodes.router._normalise`: case-insensitive, whitespace-
    token matching in declared order (earlier labels win on ambiguity). The critic
    text is FLUID — it is read purely as data to *select* a static label; it never
    becomes an instruction. An unparseable emission yields ``default`` (never a
    silent pass).
    """
    tokens = {tok.strip(".,:;!?\"'()[]{}").lower() for tok in text.split()}
    for label in labels:
        if label.lower() in tokens:
            return label
    return default


class Verifier:
    """A critic over a closed label set — describes an Output, does not (yet) gate.

    Wraps a critic :class:`~crawfish.definition.types.Definition` (frozen,
    content-hashed) and an optional :class:`~crawfish.metrics.Rubric`. ``labels`` is
    the explicit, closed set the verdict may take and always includes ``default``.
    A bare ``Verifier`` is in :attr:`VerifierStage.WARN` (or ``SHADOW``) — it may
    emit verdicts but has **no authority to stop a loop**. Use :meth:`gated` to earn
    that authority.
    """

    def __init__(
        self,
        definition: Definition,
        *,
        labels: Sequence[str],
        default: str,
        accept_label: str,
        rubric: Rubric | None = None,
        stage: VerifierStage = VerifierStage.WARN,
        name: str = "verifier",
        registry: TypeRegistry | None = None,
    ) -> None:
        labels = list(labels)
        if default not in labels:
            raise ValueError(f"default label {default!r} must be in labels {labels}")
        if accept_label not in labels:
            raise ValueError(f"accept_label {accept_label!r} must be in labels {labels}")
        if stage is VerifierStage.BLOCK:
            # Block authority is conferred only by gated(); a Verifier cannot self-promote.
            raise ValueError("a bare Verifier cannot start in BLOCK; admit it via Verifier.gated()")
        self.id = new_id()
        self.name = name
        self.definition = definition
        self.labels = labels
        self.default = default
        self.accept_label = accept_label
        self.rubric = rubric
        # Widen from the BLOCK-excluded narrowed type: gated() promotes to BLOCK later.
        self.stage: VerifierStage = stage
        self.registry: TypeRegistry = registry or default_registry

    @property
    def can_block(self) -> bool:
        """Whether this verifier may stop a loop. Always ``False`` for a bare Verifier."""
        return self.stage is VerifierStage.BLOCK

    async def verdict(
        self,
        output: Output[JSONValue],
        ctx: RunContext,
        runtime: AgentRuntime,
    ) -> Verdict:
        """Run the critic on ``output`` and return a closed-set :class:`Verdict`.

        The critic runs as a single leaf :class:`~crawfish.run.Run` (its model call
        is the *only* stochastic primitive; it replays via cassette under a
        mock/replay runtime). Each call charges the shared ``ctx.cost_budget``
        through the runtime (a second emission per Refine iteration).

        The critic's emission is FLUID and is parsed purely as data against the
        static ``labels`` — unparseable ⇒ ``default``, never a silent pass. Taint
        propagates: a verdict over a tainted (fluid-derived) Output is tainted.
        """
        run = Run(
            self.definition,
            self._bind_inputs(output),
            validate_input_types=False,
            validate_output_schema=False,
            registry=self.registry,
        )
        result = await run.execute(ctx, runtime)
        # The critic's Output is fluid model text; parse it as DATA to select a label.
        label = _normalise(str(result.value), self.labels, self.default)
        # Taint follows the verified Output (its fluidity), unioned with the critic
        # run's own taint — either makes the verdict fluid-derived ground truth.
        tainted = bool(output.tainted or result.tainted)
        return Verdict(
            label=label,
            tainted=tainted,
            source_output_id=output.id,
            lineage=output.lineage,
        )

    def accepts(self, verdict: Verdict) -> bool:
        """Whether ``verdict`` is the accept (stop) label. Pure, no model call."""
        return verdict.label == self.accept_label

    def _bind_inputs(self, output: Output[JSONValue]) -> dict[str, JSONValue]:
        """Bind ``output`` into the critic Definition's input slots (mirrors Classifier).

        The item under verification is bound to every required slot to satisfy
        presence without forcing the caller to know the Definition's port names, and
        offered under ``"output"`` for prompts that expect it. Bound as fluid data.
        """
        bound: dict[str, JSONValue] = {"output": output.value}
        for param in self.definition.inputs:
            if param.required and param.default is None:
                bound[param.name] = output.value
        return bound

    @classmethod
    def gated(
        cls,
        definition: Definition,
        golden: GoldenSet,
        *,
        labels: Sequence[str],
        default: str,
        accept_label: str,
        min_precision: float,
        decide: VerdictDecider | None = None,
        store: object | None = None,
        baseline_name: str | None = None,
        rubric: Rubric | None = None,
        name: str = "verifier",
        registry: TypeRegistry | None = None,
    ) -> GatedVerifier:
        """Admit ``definition`` as a :class:`GatedVerifier` — only if it earns it.

        Measures the critic's **absolute precision** ``TP/(TP+FP)`` directly against
        the decision ``golden`` set (gate **c**, F-3 :func:`precision_gate`) and
        admits **only if** ``precision >= min_precision`` **and** a baseline exists.

        **Fails closed (the CL-2 safety inversion).** With *no baseline stored* this
        raises :class:`~crawfish.eval.VerifierNotGated` rather than admitting — an
        un-measured critic is never granted authority to block production by default.
        (Regression-protection, if wanted, is a *separate* gate call.) A
        sub-``min_precision`` critic likewise raises and stays in ``warn``/``shadow``.

        ``decide`` maps a critic's stored decision-case label to the boolean
        "positive decision" (e.g. *accept/stop*); ``golden``'s case labels carry the
        ground-truth positive. The computation is pure given the golden set (no model
        call): the cases were already labelled by the critic under replay. Baseline
        existence is read from ``store`` under ``baseline_name`` (defaults to
        ``name``); pass ``baseline_name`` to point at a named precision baseline.

        **Hardening (#11).** A gating authority is as consequential as a Sink: it may
        *stop* production work, so it must operate on a FROZEN (eval-mode) critic — a
        train-mode artifact has no stable content identity to attribute a block to. The
        critic is therefore put into eval mode (``tuner.eval`` — re-freeze to its canonical
        content sha) at admission; the resulting :class:`GatedVerifier` always wraps a
        frozen critic, and :func:`~crawfish.tuner.guard_consequential` is a no-op on it.
        """
        from crawfish.tuner import eval as _eval_mode

        # #11: a gating authority is consequential — admit only a FROZEN (eval-mode) critic.
        # Put the critic into eval mode so the admitted GatedVerifier always gates from a
        # frozen, content-stable artifact (mirrors LearningLoop/ServingLoop's eval-mode arms).
        definition = _eval_mode(definition)
        decider = decide or _default_decider(accept_label)
        cases = golden.cases()
        decisions = [decider(case.output) for case in cases]
        truths = [decider(case.label) for case in cases]

        # Baseline existence: a critic must have been benchmarked before it can gate.
        target_store = store if store is not None else getattr(golden, "_store", None)
        if target_store is None:
            raise VerifierNotGated(
                "gated() requires a Store to check for a precision baseline; "
                "the gate fails closed without one"
            )
        baseline_exists = (
            load_baseline(
                target_store,  # type: ignore[arg-type]
                baseline_name or name,
                org_id=getattr(golden, "_org", "local"),
            )
            is not None
        )

        # FAILS CLOSED: raises VerifierNotGated when no baseline / below the bar.
        precision = precision_gate(
            decisions,
            truths,
            min_precision=min_precision,
            baseline_exists=baseline_exists,
        )

        return GatedVerifier(
            definition,
            labels=labels,
            default=default,
            accept_label=accept_label,
            measured_precision=precision,
            rubric=rubric,
            name=name,
            registry=registry,
        )


# A decision function: map a stored decision-case value (the critic's label, or the
# ground-truth label) to the boolean "this is a positive decision" used by the
# precision gate. Static/trusted — supplied by the author, never derived from fluid.
VerdictDecider = Callable[[JSONValue], bool]


def _default_decider(accept_label: str) -> VerdictDecider:
    """Positive iff the stored value equals (or contains) the accept label.

    The decision GoldenSet stores each case's critic label and ground-truth label as
    plain values; the default reads a positive decision as "this is the accept
    (stop) label". Pure and deterministic.
    """

    def _decide(value: JSONValue) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() == accept_label.lower()
        return False

    return _decide


class GatedVerifier(Verifier):
    """A :class:`Verifier` that has EARNED the right to gate (stage ``BLOCK``).

    Constructed only by :meth:`Verifier.gated` after clearing the absolute-precision
    bar against a decision :class:`~crawfish.eval.GoldenSet`. As a ``VerifierStop``
    source it may stop a ``Refine`` loop when :meth:`accepts` holds; otherwise its
    verdict feeds forward as FLUID. ``measured_precision`` records the precision it
    cleared (for the ledger / re-gate audit).
    """

    def __init__(
        self,
        definition: Definition,
        *,
        labels: Sequence[str],
        default: str,
        accept_label: str,
        measured_precision: float,
        rubric: Rubric | None = None,
        name: str = "verifier",
        registry: TypeRegistry | None = None,
    ) -> None:
        # Bypass the base BLOCK guard: gating authority is conferred *here*, after the
        # precision gate in Verifier.gated() has already passed (fail-closed).
        super().__init__(
            definition,
            labels=labels,
            default=default,
            accept_label=accept_label,
            rubric=rubric,
            stage=VerifierStage.WARN,
            name=name,
            registry=registry,
        )
        self.stage = VerifierStage.BLOCK
        self.measured_precision = measured_precision

    @property
    def can_block(self) -> bool:
        """A gated verifier may stop a loop."""
        return True


# The output schema a Verifier's verdict satisfies downstream (the gated stop signal
# carried as typed, structural data — never a stringly-typed flag).
VERDICT_SCHEMA: list[Parameter] = [
    Parameter(name="label", type="str"),
    Parameter(name="tainted", type="bool"),
]
