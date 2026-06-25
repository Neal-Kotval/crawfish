"""Optimize / version-lineage view (CRA-254) — pass-rates, deltas, promotion lineage.

RFC §7 bullets 3–4: per-component eval pass-rate, per-metric delta vs the stored baseline,
``winner`` sha, ``stopped_reason``, and the ``learn`` promotion/rollback lineage. The optimizer
verbs already write these to the Store (the :class:`~crawfish.learning.VersionRecord` lineage
under ``learning:<name>``, scored per version); this view reads them **back through the Store
protocol** (``list_records``) — never a direct table read, never SQL.

Scrubbed surface only; metric *labels* and any ``detail`` are model-derivable → carried tainted
and encoded by the renderer (UNFILED-XSS). ``stopped_reason`` / sha are stable identifiers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from crawfish.store.base import Store

__all__ = [
    "OPTIMIZE_SCHEMA",
    "LineageEvent",
    "EvalSummary",
    "ComponentOptimizeStatus",
    "optimize_status",
]

OPTIMIZE_SCHEMA = "craw.code.dashboard.optimize.v1"

#: The Store kind prefix the learning lineage is recorded under (``learning:<agent>``).
_LEARNING_PREFIX = "learning:"


class LineageEvent(BaseModel):
    """One promotion or rollback edge in a component's version lineage."""

    event: str  # "promote" | "rollback"
    sha: str = ""
    parent: str | None = None
    to: str | None = None  # the sha rolled back to (rollback only)
    ts: float = 0.0


class EvalSummary(BaseModel):
    """A component's last eval pass-rate and per-metric deltas vs the stored baseline."""

    pass_rate: float = 0.0
    baseline_pass_rate: float = 0.0
    metric_deltas: dict[str, float] = Field(default_factory=dict)


class ComponentOptimizeStatus(BaseModel):
    """Per-component optimize status: last eval, winner sha, stop reason, lineage timeline."""

    component: str
    last_eval: EvalSummary = Field(default_factory=EvalSummary)
    winner_sha: str = ""
    stopped_reason: str = ""
    lineage: list[LineageEvent] = Field(default_factory=list)


def _lineage_for(
    store: Store, agent: str, *, org_id: str
) -> tuple[list[LineageEvent], str, EvalSummary]:
    """Project one agent's ``learning:<agent>`` records to (lineage, winner_sha, eval summary).

    Pure Python over typed ``VersionRecord`` rows read via the Store protocol. The lineage is
    ordered by record appearance with promotions and pointer-move rollbacks; the winner is the
    active (or newest promoted) version; the eval summary deltas the winner's scores against the
    base version's scores (the regression baseline).
    """
    from crawfish.learning import VersionRecord

    rows = [
        VersionRecord.model_validate(r)
        for r in store.list_records(f"{_LEARNING_PREFIX}{agent}", org_id=org_id)
    ]
    if not rows:
        return [], "", EvalSummary()

    base = next((r for r in rows if r.role == "base"), rows[0])
    promoted = [r for r in rows if r.role == "promoted"]
    winner = next((r for r in rows if r.active), promoted[-1] if promoted else base)

    lineage: list[LineageEvent] = []
    for r in promoted:
        lineage.append(LineageEvent(event="promote", sha=r.sha, parent=r.parent_sha))
    # A rollback is an active pointer that points at a non-newest promoted sha (or the base):
    # the active version is older than the newest promoted candidate.
    if promoted and winner.sha != promoted[-1].sha:
        lineage.append(LineageEvent(event="rollback", to=winner.sha))

    pass_rate = float(winner.scores.get("pass_rate", 0.0))
    baseline_pass = float(base.scores.get("pass_rate", 0.0))
    deltas = {
        metric: round(value - float(base.scores.get(metric, 0.0)), 6)
        for metric, value in winner.scores.items()
        if metric != "pass_rate"
    }
    return (
        lineage,
        winner.sha,
        EvalSummary(pass_rate=pass_rate, baseline_pass_rate=baseline_pass, metric_deltas=deltas),
    )


def optimize_status(
    store: Store,
    components: list[str],
    *,
    org_id: str = "local",
    stopped_reasons: dict[str, str] | None = None,
) -> list[ComponentOptimizeStatus]:
    """Build the per-component optimize status for ``components`` (CRA-254).

    ``stopped_reasons`` (component → reason) carries the verb-emitted ``stopped_reason`` verbatim
    (``budget`` / ``cancelled`` / ``max_trials`` …); absent, it is empty. Each component's lineage
    + winner + eval delta is read from its ``learning:<component>`` lineage via the Store protocol.
    """
    reasons = stopped_reasons or {}
    out: list[ComponentOptimizeStatus] = []
    for component in components:
        lineage, winner_sha, summary = _lineage_for(store, component, org_id=org_id)
        out.append(
            ComponentOptimizeStatus(
                component=component,
                last_eval=summary,
                winner_sha=winner_sha,
                stopped_reason=reasons.get(component, ""),
                lineage=lineage,
            )
        )
    return out
