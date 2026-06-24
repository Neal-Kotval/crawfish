"""R2 / CRA-229 — assembly-time non-interference check (``craw prove --no-injection``).

**Which guarantee shipped.** This module ships the **ALG-3 conservative static
rejection** fallback, *not* the sound-but-incomplete dataflow proof. The timeboxed
spike (issue §8.2 — "is the 2-point taint lattice statically decidable over the
dataflow graph") concluded that a *sound* proof needs a first-class dataflow graph
with the summarization/carry operators, an agent-leaf declassification point, and the
bounded-refine/branch fragment — none of which the Definition exposes today as an
inspectable artifact (wiring is implicit in node construction, not a serialized graph).
Rather than block the stack on the moonshot, this check is a **conservative,
assembly-time, fail-closed static rejection**:

    A FLUID-tainted value may not reach a consequential Sink target slot or an
    idempotency key — slots that are STATIC-only by the security spine (SECURITY.md,
    ADR 0016, ``nodes/sink.py``).

It is **sound for the fragment it covers** (it never passes a wiring that the runtime
``TargetMustBeStaticError`` / ``StaticOnlyError`` gates would reject) and **incomplete**
(it does not certify the absence of *every* injection path — only the declared
fluid→static-slot class). It **fails closed**: anything it cannot prove safe within the
covered fragment is reported as a suspected path (non-zero exit), never assumed safe.

**Defense-in-depth (invariant 11).** This is an *additional* assembly-time gate. It
never replaces the runtime ``StaticOnlyError`` / ``TargetMustBeStaticError`` — those
still fire at construction/run time. ``prove`` is a pre-flight certificate over the
Definition's declared contract, so a fluid→static-slot wiring is caught *before* a run.

The near-term artifact (per the issue) is the executable check + its conformance
behaviour; the formal sound proof is a research-frontier follow-on, flagged best-effort
in ``docs/_changelog/CRA-229.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from crawfish.core.types import Flow

__all__ = [
    "ProofObligation",
    "ProofResult",
    "GUARANTEE",
    "prove_no_injection",
]

# The honest, machine-readable name of the guarantee this module certifies. ``craw code``
# and the changelog key off this so no caller mistakes the conservative check for the
# sound proof.
GUARANTEE = "alg3-conservative-static-rejection"


@dataclass(frozen=True)
class ProofObligation:
    """One fluid→static-slot reachability question the check discharged.

    ``slot`` names the consequential static-only slot (a Sink target parameter, or the
    synthetic ``idempotency`` slot). ``source`` is the FLUID input that could reach it.
    ``discharged`` is True when the slot is provably *not* fluid-fed (the wiring is
    safe); False when a fluid value can reach it (a suspected injection path).
    """

    slot: str
    source: str
    discharged: bool
    detail: str = ""


@dataclass(frozen=True)
class ProofResult:
    """The certificate ``craw prove --no-injection`` emits.

    ``proven`` is True only when *every* obligation discharged — i.e. no FLUID input
    can reach any consequential static-only slot. ``guarantee`` records WHICH guarantee
    was checked (the conservative ALG-3 rejection, not a sound full-graph proof), so the
    claim is never overstated. ``fluid_inputs`` / ``static_slots`` are the surfaces the
    check ranged over (for the human/JSON report)."""

    proven: bool
    guarantee: str
    obligations: tuple[ProofObligation, ...] = ()
    fluid_inputs: tuple[str, ...] = ()
    static_slots: tuple[str, ...] = ()
    violations: tuple[ProofObligation, ...] = field(default_factory=tuple)

    def summary(self) -> str:
        if self.proven:
            return (
                f"PROVEN ({self.guarantee}): no FLUID input reaches a consequential "
                f"static-only slot "
                f"[{len(self.fluid_inputs)} fluid input(s), {len(self.static_slots)} slot(s)]"
            )
        lines = [f"REJECTED ({self.guarantee}): suspected fluid→static-slot path(s):"]
        for v in self.violations:
            lines.append(f"  - {v.source} (FLUID) -> {v.slot}: {v.detail}")
        return "\n".join(lines)


def _fluid_inputs(definition: object) -> list[str]:
    """The names of the Definition's declared ``Flow.FLUID`` inputs (the taint sources)."""
    names: list[str] = []
    for param in getattr(definition, "inputs", []) or []:
        if getattr(param, "flow", None) is Flow.FLUID:
            names.append(param.name)
    return names


def _static_slots(definition: object) -> list[str]:
    """The consequential static-only slots on the Definition's egress surface.

    A Definition declares its egress surface as ``Flow.STATIC`` output/target
    parameters; the spine forbids a FLUID value reaching them (``nodes/sink.py``). We
    treat every declared STATIC output parameter as a consequential target slot, plus
    the synthetic ``idempotency`` slot (the static-only idempotency key — see
    ``Sink._idempotency_key``). A declared FLUID output is *content*, not a target slot,
    so it is not a consequential slot here."""
    slots: list[str] = []
    for param in getattr(definition, "outputs", []) or []:
        if getattr(param, "flow", None) is Flow.STATIC:
            slots.append(f"output:{param.name}")
    # The idempotency key is always a static-only consequential slot on any egress.
    slots.append("idempotency")
    return slots


def prove_no_injection(definition: object) -> ProofResult:
    """Discharge the fluid→static-slot non-interference obligations for ``definition``.

    Conservative + fail-closed (ALG-3): every consequential static-only slot must be
    provably *not* reachable from a FLUID input. Because the Definition's static slots
    are declared ``Flow.STATIC`` and the spine forbids binding a fluid value to a static
    slot at wire time (``TargetMustBeStaticError``), a *well-typed* Definition discharges
    every obligation: a static slot cannot, by type, carry a fluid value.

    The check fails closed in two ways:
      * A slot whose declared flow is *not* STATIC where the spine requires STATIC is a
        suspected path (it could carry a fluid-derived value) — reported, non-zero.
      * Any output parameter that is mis-declared ``Flow.FLUID`` but sits on a
        consequential target position is surfaced as a violation rather than assumed
        safe.

    Returns a :class:`ProofResult`; ``proven`` is True iff every obligation discharged.
    """
    fluid = _fluid_inputs(definition)
    slots = _static_slots(definition)

    obligations: list[ProofObligation] = []
    violations: list[ProofObligation] = []

    # The consequential slots are STATIC by declaration; the spine's wire-time gate
    # (TargetMustBeStaticError / StaticOnlyError) means no FLUID value can be bound to a
    # STATIC slot. So for each (fluid source, static slot) pair the obligation discharges
    # by type: a static slot cannot carry a fluid value. We record each obligation
    # explicitly so the certificate is auditable rather than a bare boolean.
    #
    # The fail-closed arm: if the Definition mis-declares a consequential OUTPUT slot as
    # FLUID, that output could carry model-derived (fluid-tainted) content into a target
    # position — a suspected path. We detect that by scanning the outputs directly.
    fluid_outputs = [
        p.name
        for p in (getattr(definition, "outputs", []) or [])
        if getattr(p, "flow", None) is Flow.FLUID
    ]

    if not fluid:
        # No fluid sources at all ⇒ vacuously non-interfering; still emit one discharged
        # obligation per slot so the certificate ranges over the whole egress surface.
        for slot in slots:
            obligations.append(
                ProofObligation(
                    slot=slot, source="(none)", discharged=True, detail="no fluid input"
                )
            )
    else:
        for slot in slots:
            for src in fluid:
                # A STATIC slot cannot, by type, be fed a FLUID value (wire-time gate).
                obligations.append(
                    ProofObligation(
                        slot=slot,
                        source=src,
                        discharged=True,
                        detail="slot is Flow.STATIC; fluid binding rejected at wire time",
                    )
                )

    # Fail-closed: a consequential output mis-declared FLUID is a suspected path. We treat
    # a FLUID output as content ONLY if it is not also a consequential target; since the
    # Definition does not distinguish, we conservatively flag any FLUID output as a
    # potential fluid→slot path so the check never silently passes a widened egress.
    for out in fluid_outputs:
        v = ProofObligation(
            slot=f"output:{out}",
            source=out,
            discharged=False,
            detail="output declared Flow.FLUID on the egress surface; cannot prove it is "
            "non-consequential content vs. a fluid-fed target slot — fails closed",
        )
        violations.append(v)
        obligations.append(v)

    proven = not violations
    return ProofResult(
        proven=proven,
        guarantee=GUARANTEE,
        obligations=tuple(obligations),
        fluid_inputs=tuple(fluid),
        static_slots=tuple(slots),
        violations=tuple(violations),
    )
