"""Learning agents — eval-gated self-versioning (CRA-177).

An agent that improves its OWN instructions/knobs over time, *safely*. This is the
:class:`~crawfish.tuner.Tuner` (CRA-176) pointed at an agent's own Definition, with the
winner **promotion-gated** against a stored regression baseline and the whole base →
candidate → promoted lineage recorded as content-hashed
:class:`~crawfish.versioning.version.Version`\\ s so a bad promotion is fully **reversible**.

The composition (we do NOT re-implement search):

* :meth:`LearningLoop.improve` calls ``Tuner.tune`` to search the agent's own knob space
  (reusing the Tuner's mutators, deterministic order, regression-gate-vs-base, and the
  autonomy ceiling — ``cost_budget`` / ``cancel_token`` / ``max_trials``). The Tuner is the
  *engine*; the loop adds the *promotion policy* on top of its winner.
* The Tuner's winner is promoted ONLY if it (a) actually improved on the base in this run
  AND (b) passes :func:`~crawfish.eval.gate_against_baseline` — no regression vs the stored
  baseline. A regression is never promoted; the active version is unchanged.
* Every version in the lineage (the base, the promoted candidate) is a frozen, content-hashed
  artifact persisted through the ``Store``. :meth:`LearningLoop.rollback` re-activates any
  prior recorded version — promotion is reversible by construction.

Safety (load-bearing):

* Promotion is **eval-gated** — :func:`gate_against_baseline` + the Tuner's own
  ``is_regression`` guard, so a noisy/worse candidate can never silently replace a working
  agent.
* The loop is bounded by the **autonomy ceiling** it inherits from the Tuner
  (``cost_budget`` exhaustion / ``cancel_token`` / ``max_trials``); a ceiling breach returns
  a non-promoting outcome rather than spending unbounded model cost.
* A promoted version is **frozen + auditable** (recorded with its scores + provenance)
  before it becomes the active version.
* The loop mutates only STATIC Definition config (via the Tuner's pure mutators, which never
  invent text via a model). It can never cross the static/fluid boundary, so a promotion can
  never introduce a fluid Sink target; untrusted (fluid) content can never drive a promotion.

Determinism: ``improve`` is a thin policy over ``Tuner.tune`` — same ``base`` + ``seed`` ⇒
identical winner, identical baseline scores ⇒ identical promotion decision.
"""

from __future__ import annotations

from pydantic import BaseModel

from crawfish.core.context import RunContext
from crawfish.definition.types import Definition
from crawfish.eval import gate_against_baseline, load_baseline, save_baseline
from crawfish.runtime.base import AgentRuntime
from crawfish.store.base import Store
from crawfish.tuner import Tuner, TuneResult, _refreeze

__all__ = [
    "VersionRecord",
    "PromotionOutcome",
    "LearningLoop",
]


class VersionRecord(BaseModel):
    """One frozen, auditable point in an agent's version lineage.

    Persisted through the ``Store`` so the base → candidate → promoted history survives a
    process restart and a bad promotion can be rolled back to any prior ``sha``.
    """

    model_config = {"arbitrary_types_allowed": True}

    agent: str  # the learning-loop name this version belongs to
    sha: str  # the candidate's content-hash version sha (the lineage key)
    version: str  # the human-readable ``str(Version)`` (``major.minor-sha``)
    definition: Definition  # the frozen Definition at this point
    scores: dict[str, float]  # the benchmark scores that justified this version
    role: str  # "base" | "promoted"
    parent_sha: str | None = None  # the version this one was derived from (lineage edge)
    active: bool = False  # True iff this is the agent's currently-active version


class PromotionOutcome(BaseModel):
    """The result of one :meth:`LearningLoop.improve` cycle (the audit record)."""

    model_config = {"arbitrary_types_allowed": True}

    promoted: bool  # True iff a strictly-better, gate-clean candidate replaced the active one
    reason: str  # "promoted" | "no_improvement" | "gated" | "ceiling:<reason>"
    active: Definition  # the agent's active Definition AFTER this cycle (base if not promoted)
    base_sha: str  # the frozen version we tuned from (the lineage parent)
    candidate_sha: str  # the Tuner's winning version (== base_sha if it found nothing better)
    base_scores: dict[str, float]
    candidate_scores: dict[str, float]
    tune: TuneResult  # the full Tuner trial log (the search audit trail)


class LearningLoop:
    """A self-improving agent: the Tuner + an eval-gated, versioned promotion policy.

    The loop owns one named lineage of an agent's Definitions in the ``Store``. Each
    :meth:`improve` runs the Tuner over the *active* Definition's own knobs, then promotes
    the winner only if it beats the baseline (regression-gated). Promotion is recorded as a
    new frozen ``VersionRecord``; :meth:`rollback` re-activates any prior one.
    """

    def __init__(
        self,
        name: str,
        tuner: Tuner,
        store: Store,
        *,
        org_id: str = "local",
        tolerance: float = 0.0,
    ) -> None:
        self.name = name
        self.tuner = tuner
        self.store = store
        self.org_id = org_id
        self.tolerance = tolerance

    # -- lineage persistence (Store-backed, reversible) ---------------------
    @property
    def _kind(self) -> str:
        return f"learning:{self.name}"

    @property
    def _baseline_name(self) -> str:
        return f"learning:{self.name}"

    def _record(self, rec: VersionRecord) -> None:
        self.store.put_record(self._kind, rec.sha, rec.model_dump(mode="json"), org_id=self.org_id)

    def _get(self, sha: str) -> VersionRecord | None:
        raw = self.store.get_record(self._kind, sha, org_id=self.org_id)
        return None if raw is None else VersionRecord.model_validate(raw)

    def history(self) -> list[VersionRecord]:
        """The full version lineage for this agent (the recorded set of versions)."""
        return [
            VersionRecord.model_validate(r)
            for r in self.store.list_records(self._kind, org_id=self.org_id)
        ]

    def active(self) -> VersionRecord | None:
        """The agent's currently-active version record, if any has been recorded."""
        for rec in self.history():
            if rec.active:
                return rec
        return None

    def _set_active(self, sha: str) -> None:
        """Flip the active flag to ``sha`` (exactly one active version at a time)."""
        for rec in self.history():
            want = rec.sha == sha
            if rec.active != want:
                rec.active = want
                self._record(rec)

    def _record_base(self, base: Definition, base_scores: dict[str, float]) -> str:
        """Record the tuned-from base as a frozen version; return its content sha.

        The Tuner re-freezes the base internally; we reconstruct that same frozen artifact
        here (via the Tuner's own ``_refreeze``) so the lineage edge (``parent_sha``) points
        at a real, retrievable version a rollback can return to. Idempotent: a base already
        in the lineage is not re-written. Also seeds the regression baseline on first use.
        """
        base_frozen = _refreeze(base, base.model_copy(deep=True))
        base_sha = str(base_frozen.version.sha or "")
        if self._get(base_sha) is None:
            self._record(
                VersionRecord(
                    agent=self.name,
                    sha=base_sha,
                    version=str(base_frozen.version),
                    definition=base_frozen,
                    scores=base_scores,
                    role="base",
                    parent_sha=None,
                    active=self.active() is None,  # active only if the lineage was empty
                )
            )
        if load_baseline(self.store, self._baseline_name, org_id=self.org_id) is None:
            save_baseline(self.store, self._baseline_name, base_scores, org_id=self.org_id)
        return base_sha

    def _not_promoted(self, reason: str, parent_sha: str, result: TuneResult) -> PromotionOutcome:
        active = self.active()
        return PromotionOutcome(
            promoted=False,
            reason=reason,
            active=active.definition if active is not None else result.best,
            base_sha=parent_sha,
            candidate_sha=str(result.best.version.sha or ""),
            base_scores=result.base_scores,
            candidate_scores=result.best_scores,
            tune=result,
        )

    # -- the learning cycle -------------------------------------------------
    async def improve(
        self,
        base: Definition,
        ctx: RunContext,
        runtime: AgentRuntime,
        *,
        seed: int = 0,
    ) -> PromotionOutcome:
        """Run one eval-gated self-versioning cycle over ``base``'s own knobs.

        Delegates the search to ``Tuner.tune`` (inheriting its mutators, determinism and
        autonomy ceiling), then applies the promotion policy: promote the winner ONLY if it
        improved in this run AND passes the stored regression baseline. On promotion, the new
        frozen version is recorded + activated and the baseline advances; otherwise the active
        version is untouched. Same ``base`` + ``seed`` ⇒ same outcome.
        """
        result = await self.tuner.tune(base, ctx, runtime, seed=seed)

        # Persist the tuned-from base so the lineage is complete + the baseline is seeded.
        parent_sha = self._record_base(base, result.base_scores)

        # -- autonomy ceiling: a ceiling breach with no improvement is never a promotion --
        if result.stopped_reason in ("budget", "cancelled", "max_trials") and not result.improved:
            return self._not_promoted(f"ceiling:{result.stopped_reason}", parent_sha, result)

        # -- the Tuner found nothing better than the base ------------------
        if not result.improved:
            return self._not_promoted("no_improvement", parent_sha, result)

        # -- eval gate: never promote a regression vs the stored baseline ---
        cand = result.best
        cand_sha = str(cand.version.sha or "")
        cand_scores = result.best_scores
        gate_clean = gate_against_baseline(
            self.store,
            self._baseline_name,
            cand_scores,
            tolerance=self.tolerance,
            org_id=self.org_id,
        )
        if not gate_clean:
            return self._not_promoted("gated", parent_sha, result)

        # -- promote: record the frozen candidate, activate it, advance the baseline ------
        self._record(
            VersionRecord(
                agent=self.name,
                sha=cand_sha,
                version=str(cand.version),
                definition=cand,  # already frozen by the Tuner's _refreeze
                scores=cand_scores,
                role="promoted",
                parent_sha=parent_sha,
                active=False,  # _set_active flips exactly one active flag
            )
        )
        self._set_active(cand_sha)
        save_baseline(self.store, self._baseline_name, cand_scores, org_id=self.org_id)

        return PromotionOutcome(
            promoted=True,
            reason="promoted",
            active=cand,
            base_sha=parent_sha,
            candidate_sha=cand_sha,
            base_scores=result.base_scores,
            candidate_scores=cand_scores,
            tune=result,
        )

    # -- reversibility ------------------------------------------------------
    def rollback(self, sha: str) -> Definition:
        """Re-activate a prior recorded version (reverse a promotion).

        Returns the now-active frozen Definition. The regression baseline is reset to the
        rolled-back version's scores so subsequent ``improve`` cycles are gated against the
        version actually in force. Raises ``KeyError`` if ``sha`` is not in the lineage.
        """
        rec = self._get(sha)
        if rec is None:
            raise KeyError(f"no version {sha!r} in lineage for agent {self.name!r}")
        self._set_active(sha)
        save_baseline(self.store, self._baseline_name, rec.scores, org_id=self.org_id)
        return rec.definition
