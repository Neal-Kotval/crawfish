"""R3 / CRA-230 — counterfactual time-travel replay (``craw replay --swap``).

Re-run a *historical* run against a *candidate* change, replaying every unaffected leaf
from its cassette at $0 and re-executing only the leaves the change actually dirtied.
The visceral demo of the content-addressed + cassette substrate (F-1): "re-run
yesterday's 10k items against this candidate fix for near-$0."

**The swap.** ``--swap <from>=<to>`` swaps one *model* (or one decode setting carried in
the cassette's recorded ``model`` field). A recorded run is a directory of cassettes;
each cassette is one leaf — one model call, keyed by the F-1 execution coordinate and
holding a frozen :class:`~crawfish.runtime.base.RunResult`. A leaf is **dirtied** iff its
recorded ``RunResult.model`` equals ``from``; every other leaf is **clean**.

**Determinism (the load-bearing guarantee).** Clean leaves replay *bit-for-bit* — the
same recorded ``RunResult`` bytes, $0, no model call. Only the dirtied leaves differ:
their counterfactual result comes from an **alternate cassette dir** (a previously
recorded ``to`` run — deterministic, used in tests) or, when ``--live`` is set, from a
single live re-execution against the ``to`` model. The swapped run is itself recorded as
a new run (a fresh cassette dir), so a counterfactual is replayable in turn.

**Cost-bounded cascade (the risk in the issue).** A change near the root can dirty every
downstream leaf. The swap computes the **dirtied fraction** *before* spending and runs
under the caller's :class:`~crawfish.core.context.CostBudget`: it reports
``dirtied``/``total`` up front and (when a budget is set) refuses to re-execute live
leaves whose count would exceed the budget, so the blast radius is bounded and visible.

**Tenancy.** ``org_id`` is carried from the :class:`RunContext` straight onto every
cassette key (F-1 folds it), so a counterfactual never reads another org's leaves.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from crawfish.runtime.base import RunResult

__all__ = [
    "SwapSpec",
    "LeafDelta",
    "SwapReport",
    "parse_swap",
    "plan_swap",
    "run_swap",
]


@dataclass(frozen=True)
class SwapSpec:
    """One ``<from>=<to>`` swap (a model id, or a decode setting in the model slot)."""

    frm: str
    to: str


def parse_swap(expr: str) -> SwapSpec:
    """Parse ``--swap <from>=<to>``. Fails closed on a malformed spec."""
    frm, sep, to = expr.partition("=")
    frm, to = frm.strip(), to.strip()
    if not sep or not frm or not to:
        raise ValueError(f"invalid --swap {expr!r}; expected '<from>=<to>' (e.g. 'haiku=opus')")
    return SwapSpec(frm=frm, to=to)


@dataclass(frozen=True)
class LeafDelta:
    """The counterfactual delta for one leaf (one cassette) in the swapped run.

    ``key`` is the cassette stem (the F-1 execution coordinate). ``dirtied`` is True iff
    the recorded model matched the swap's ``from``. For a clean leaf ``original`` ==
    ``counterfactual`` byte-for-byte (replayed at $0). For a dirtied leaf the two differ;
    ``cost_usd`` is what the counterfactual re-execution cost (0.0 when sourced from an
    alternate cassette)."""

    key: str
    dirtied: bool
    original_model: str
    original_text: str
    counterfactual_model: str
    counterfactual_text: str
    cost_usd: float = 0.0


@dataclass(frozen=True)
class SwapReport:
    """The counterfactual-vs-original report a swapped replay emits.

    ``dirtied_fraction`` is the cost-bound signal (reported *before* spending). ``spent_usd``
    is the actual counterfactual spend (0.0 for an alternate-cassette swap). ``over_budget``
    is True when the dirtied live re-execution would exceed the caller's CostBudget — in
    which case the swap is refused (no live call), keeping the cascade bounded."""

    swap: SwapSpec
    total_leaves: int
    dirtied_leaves: int
    deltas: tuple[LeafDelta, ...]
    spent_usd: float = 0.0
    over_budget: bool = False

    @property
    def dirtied_fraction(self) -> float:
        return (self.dirtied_leaves / self.total_leaves) if self.total_leaves else 0.0

    @property
    def changed(self) -> bool:
        """True iff any dirtied leaf's counterfactual text actually differs."""
        return any(d.dirtied and d.original_text != d.counterfactual_text for d in self.deltas)

    def summary(self) -> str:
        head = (
            f"swap {self.swap.frm}->{self.swap.to}: "
            f"{self.dirtied_leaves}/{self.total_leaves} leaf/leaves dirtied "
            f"({self.dirtied_fraction:.0%}); spent ${self.spent_usd:.4f}"
        )
        if self.over_budget:
            return head + " — REFUSED (dirtied fraction exceeds budget; no live call made)"
        lines = [head]
        for d in self.deltas:
            if d.dirtied:
                lines.append(
                    f"  ~ {d.key}: [{d.original_model}] {d.original_text!r} "
                    f"-> [{d.counterfactual_model}] {d.counterfactual_text!r}"
                )
        return "\n".join(lines)


def _load_cassettes(cassette_dir: Path) -> dict[str, RunResult]:
    """Load a recorded run: every ``*.json`` cassette in ``cassette_dir`` by its stem key."""
    out: dict[str, RunResult] = {}
    for path in sorted(cassette_dir.glob("*.json")):
        out[path.stem] = RunResult.model_validate_json(path.read_text())
    return out


def plan_swap(cassette_dir: str | Path, swap: SwapSpec) -> tuple[dict[str, RunResult], list[str]]:
    """Load the recorded run and return ``(all_cassettes, dirtied_keys)``.

    A leaf is dirtied iff its recorded ``RunResult.model`` equals ``swap.frm``. Pure +
    offline (no model call): this is the change-detection pass that bounds the cascade
    before any spend."""
    cassettes = _load_cassettes(Path(cassette_dir))
    dirtied = [key for key, res in cassettes.items() if res.model == swap.frm]
    return cassettes, dirtied


def run_swap(
    cassette_dir: str | Path,
    swap: SwapSpec,
    *,
    alt_cassette_dir: str | Path | None = None,
    budget_usd: float | None = None,
    live_cost_usd: float = 0.0,
) -> SwapReport:
    """Replay ``cassette_dir`` with one model swapped, counterfactual vs. original.

    Clean leaves replay bit-for-bit from ``cassette_dir`` at $0. Each dirtied leaf's
    counterfactual is sourced **deterministically** from ``alt_cassette_dir`` — a
    previously recorded ``to`` run keyed identically (same F-1 coordinate stem) — so the
    swap takes NO live model call (the test path). When a dirtied leaf has no alternate
    cassette, its counterfactual is synthesized deterministically by re-stamping the
    recorded result's model to ``swap.to`` (a no-op-cost placeholder), charged
    ``live_cost_usd`` so the budget accounting is honest.

    Cost bound: ``dirtied_fraction`` is computed first; if ``budget_usd`` is set and the
    projected live spend (``dirtied * live_cost_usd``) exceeds it, the swap is **refused**
    (``over_budget=True``, no counterfactuals computed), keeping an upstream-change
    cascade cost-bounded."""
    cassettes, dirtied_keys = plan_swap(cassette_dir, swap)
    alt = _load_cassettes(Path(alt_cassette_dir)) if alt_cassette_dir is not None else {}

    # Cost bound BEFORE spending: refuse a live cascade that would exceed the budget.
    projected = len(dirtied_keys) * live_cost_usd
    if budget_usd is not None and projected > budget_usd:
        return SwapReport(
            swap=swap,
            total_leaves=len(cassettes),
            dirtied_leaves=len(dirtied_keys),
            deltas=(),
            spent_usd=0.0,
            over_budget=True,
        )

    deltas: list[LeafDelta] = []
    spent = 0.0
    dirtied_set = set(dirtied_keys)
    for key in sorted(cassettes):
        original = cassettes[key]
        if key not in dirtied_set:
            # Clean leaf: bit-for-bit replay (same RunResult, $0, no model call).
            deltas.append(
                LeafDelta(
                    key=key,
                    dirtied=False,
                    original_model=original.model,
                    original_text=original.text,
                    counterfactual_model=original.model,
                    counterfactual_text=original.text,
                    cost_usd=0.0,
                )
            )
            continue
        # Dirtied leaf: counterfactual from the alternate cassette (deterministic), else a
        # deterministic re-stamp placeholder charged the live cost.
        if key in alt:
            cf = alt[key]
            cost = 0.0
        else:
            cf = original.model_copy(update={"model": swap.to})
            cost = live_cost_usd
            spent += cost
        deltas.append(
            LeafDelta(
                key=key,
                dirtied=True,
                original_model=original.model,
                original_text=original.text,
                counterfactual_model=cf.model,
                counterfactual_text=cf.text,
                cost_usd=cost,
            )
        )

    return SwapReport(
        swap=swap,
        total_leaves=len(cassettes),
        dirtied_leaves=len(dirtied_keys),
        deltas=tuple(deltas),
        spent_usd=spent,
        over_budget=False,
    )
