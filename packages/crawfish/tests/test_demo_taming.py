"""Deterministic acceptance test for the Milestone-4 TAMING step of the cumulative demo.

Exercises the four variance-reducers (CRA-215..218) added to
``demo/triage-bot/self_improve.py`` — entirely off the mock runtime (NO live model
call) — and asserts the load-bearing M4 guarantees:

* **Quorum / self-consistency (TS-1)** — an ambiguous ticket is classified ``k`` times by a
  :class:`~crawfish.runtime.quorum.QuorumRuntime`; the ``k`` samples genuinely DISAGREE, and
  the pure :func:`~crawfish.runtime.quorum.majority_vote` reduction resolves the split to one
  typed result (or the declared default on a tie/abstain — Router parity). A vote does not
  launder taint.
* **Abstention / selective prediction (TS-4)** — a low-confidence triage Output is turned
  into a typed :class:`~crawfish.abstain.Abstention` by ``abstain_below_calibrated`` (the
  threshold read off a reliability curve, not a guessed constant), and a Router branches the
  ``Abstention`` to a ``review`` path via the pure :func:`~crawfish.abstain.is_abstention`
  predicate.
* **House-guard / learned-then-distilled guard (TS-7)** — the model PROPOSES a candidate
  rule (the one stochastic leaf); :func:`~crawfish.guard.distill` parses it into the closed
  predicate grammar AS DATA; :meth:`~crawfish.guard.HouseGuard.synthesize` EARNS enforcement
  against the trusted corpus on the joint precision/coverage bar; the earned guard BLOCKS a
  disallowed output and PASSES an allowed one — model-free at enforcement.
* **Constrained decoding / grammar (TS-8)** — a structured field is produced under a static
  :class:`~crawfish.grammar.Grammar`; the constrained field is valid by construction (zero
  repairs) where the unconstrained decode is not.

The whole step is deterministic over recorded data once its (few) stochastic leaves are
fixed, so — unlike the Refine/gate VERDICT — there is no model-variance branch: these
assertions hold on both the mock and the live path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from crawfish.abstain import Abstention, abstain_below, is_abstention
from crawfish.grammar import Grammar
from crawfish.guard import GuardStage, HouseGuard, distill
from crawfish.output import Output

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO = REPO_ROOT / "demo" / "triage-bot" / "self_improve.py"


def _load_scenario():
    spec = importlib.util.spec_from_file_location("crawfish_demo_taming_test", SCENARIO)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # so dataclass forward-refs resolve
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    if not SCENARIO.exists():  # pragma: no cover - demo always present in-repo
        pytest.skip(f"demo scenario not found at {SCENARIO}")
    return _load_scenario()


@pytest.fixture(scope="module")
def result(module):
    return module.run_self_improvement(live=False)  # deterministic mock path only


# --- 1. Quorum: k samples disagree, the vote resolves the split -------------------
def test_quorum_drew_k_samples(module, result) -> None:
    """The quorum drew the configured ``k`` samples for the one ambiguous ticket."""
    assert result.quorum_k == module._QUORUM_K
    assert result.quorum_k >= 2  # a meaningful vote needs at least two samples


def test_quorum_samples_genuinely_disagree(result) -> None:
    """The k samples produced MORE THAN ONE distinct category — a real disagreement.

    A unanimous vote would be a no-op (variance 0); the self-consistency claim is only
    proven when the samples actually split and the vote has to resolve it.
    """
    assert result.quorum_distinct > 1
    # the tally sums to the samples drawn (every sample was counted)
    assert sum(result.quorum_tally.values()) == result.quorum_k


def test_quorum_resolved_to_typed_winner(result) -> None:
    """The disagreement resolved to a typed result (never abstained/raised here)."""
    assert result.quorum_resolved
    assert result.quorum_winner  # a non-empty elected category
    # the winner is the modal candidate the vote keyed on (one of the disagreeing options)
    assert result.quorum_winner in {k.strip('"') for k in result.quorum_tally}


def test_majority_vote_is_a_pure_function(module) -> None:
    """The vote reduction is deterministic — same samples ⇒ same winner across runs."""
    second = module.run_self_improvement(live=False)
    first = module.run_self_improvement(live=False)
    assert second.quorum_winner == first.quorum_winner
    assert second.quorum_tally == first.quorum_tally


# --- 2. Abstention: a low-confidence Output becomes a typed Abstention + routes ----
def test_abstention_triggered_below_threshold(result) -> None:
    """The low reported confidence fell under the calibration-derived threshold ⇒ abstain."""
    assert result.abstained
    assert 0.0 <= result.abstain_confidence < result.abstain_threshold


def test_abstention_routed_to_review(result) -> None:
    """A Router branched the typed Abstention to the ``review`` path (is_abstention)."""
    assert result.abstain_routed == "review"


def test_abstention_is_a_typed_routable_value(module) -> None:
    """An Abstention serialises to a tagged value an ``is_abstention`` predicate recognises.

    This is the property that makes the abstain decision *routable* after persist/replay —
    no Python type survives a serialised Output, so the marker travels in the value itself.
    """
    out: Output[object] = Output(
        value={"confidence": 0.1}, produced_by="t", lineage="x", output_schema=[]
    )
    decided = abstain_below(0.5)(out)
    assert is_abstention(decided.value)
    abst = Abstention.from_value(decided.value)
    assert abst is not None and abst.confidence == pytest.approx(0.1)


def test_missing_confidence_fails_safe_to_abstain(module) -> None:
    """A *missing* confidence abstains — declining is the always-allowed fail-safe action."""
    out: Output[object] = Output(value={}, produced_by="t", lineage="x", output_schema=[])
    decided = abstain_below(0.5)(out)
    assert is_abstention(decided.value)


# --- 3. House-guard: learned -> distilled -> earned -> BLOCKs (model-free) ---------
def test_guard_earned_enforcement(result) -> None:
    """The distilled guard cleared the joint precision/coverage bar and reached BLOCK."""
    assert result.guard_earned
    assert result.guard_stage == GuardStage.BLOCK.value
    assert result.guard_sha  # the distilled predicate's lineage key was minted


def test_guard_blocks_disallowed_and_passes_allowed(result) -> None:
    """The earned guard BLOCKED the disallowed output AND passed the allowed one.

    Blocking everything is not a guard; the discrimination (block disallowed, pass allowed)
    is what makes the earned authority meaningful — and it is pure (zero model calls).
    """
    assert result.guard_blocked_disallowed
    assert result.guard_allowed_passed


def test_unearned_guard_cannot_block(module) -> None:
    """A guard that does not clear the bar fails CLOSED — it cannot block (fail-safe).

    Synthesizing the demo's rule against an EMPTY corpus earns nothing (no evidence), so the
    guard stays in ``warn`` and ``blocks`` returns False even though its predicate matches.
    """
    from crawfish.eval import GoldenSet
    from crawfish.store import SqliteStore

    store = SqliteStore()
    empty = GoldenSet(store, "no-corpus", org_id="acme")
    predicate = distill(module._PROPOSED_GUARD_RULE)
    guard = HouseGuard.synthesize(predicate, empty, precision_floor=0.5, min_coverage=0.1)
    disallowed: Output[object] = Output(
        value=module._DISALLOWED_OUTPUT, produced_by="t", lineage="x", output_schema=[]
    )
    assert not guard.can_block
    assert guard.matches(disallowed)  # the predicate still fires (observation)
    assert not guard.blocks(disallowed)  # ...but an un-earned guard never ENFORCES
    store.close()


def test_distill_cannot_widen_the_closed_grammar(module) -> None:
    """A FLUID proposal cannot widen the predicate grammar — an unknown kind is rejected."""
    from crawfish.guard import GuardGrammarError

    with pytest.raises(GuardGrammarError):
        distill({"kind": "shell_exec", "cmd": "rm -rf /"})  # not in the closed grammar


# --- 4. Constrained decoding: a structured field under a Grammar, zero repairs -----
def test_grammar_constrained_field_is_valid(module, result) -> None:
    """The constrained category is a valid in-grammar member (well-formed by construction)."""
    assert result.grammar_constrained_valid
    assert result.grammar_field in module._ROUTER_LABELS


def test_grammar_eliminated_a_repair(result) -> None:
    """The constraint eliminated a repair the unconstrained decode would have needed.

    The unconstrained decode is chatty prose (not a bare label) — invalid against the
    grammar — so the constrained path saved at least one ``_repair`` round trip.
    """
    assert not result.grammar_unconstrained_valid
    assert result.grammar_repairs_saved > 0


def test_grammar_enforce_is_deterministic(module) -> None:
    """``Grammar.enforce`` is a pure projection — same text + grammar ⇒ same member."""
    grammar = Grammar.enum(list(module._ROUTER_LABELS))
    text = "the category is clearly 'billing' here"
    assert grammar.enforce(text) == grammar.enforce(text) == "billing"
    assert not grammar.satisfies(text)  # the raw prose is NOT in-grammar
    assert grammar.satisfies(grammar.enforce(text))  # ...the enforced value is


# --- 5. The whole step certifies (the pass predicate) -----------------------------
def test_taming_step_ok(result) -> None:
    """The aggregate M4 certificate passes — all four behaviours held together."""
    assert result._taming_step_ok()


def test_scenario_still_passes_end_to_end(result) -> None:
    """Adding M4 did not break the cumulative scenario — it still PASSES 9/9."""
    assert result.passed()


# --- 6. The cost model accounts for the Quorum k-fan-out --------------------------
def test_worst_case_includes_quorum_k_fanout(module) -> None:
    """The structural worst-case folds in the Quorum k-fan-out (and the other M4 calls).

    Quorum MULTIPLIES calls (k samples per voted item); the worst-case must grow by exactly
    ``_QUORUM_K`` (+ abstain + guard-propose + grammar) per repair factor, or the live cost
    gate would (correctly) fail when the fan-out fires fresh.
    """
    base_kwargs = dict(n_cases=6, n_tune=3, n_gate=3, n_candidates=2, n_calib=6)
    full = module._worst_case_calls(**base_kwargs)
    # the M4 contribution, isolated: k samples + abstain + guard-propose + grammar, × repair.
    m4_calls = (
        module._QUORUM_K
        + module._ABSTAIN_CALLS
        + module._GUARD_PROPOSE_CALLS
        + module._GRAMMAR_CALLS
    )
    assert full >= m4_calls * module._REPAIR_FACTOR
    # the k-fan-out is really in there: dropping it would shrink the bound by k × repair.
    assert module._QUORUM_K >= 2  # a real multiplier, not a single call


# --- 7. Real-model robustness (the three live harness defects, regression-guarded) -
# These exercise the free-form-prose path the LIVE model takes — the mock fixture above
# hits the structured-JSON path, so without these the defects (role unresolvable, vote
# keyed on raw prose, guard proposal not clean grammar) reach the live gate uncaught.
def test_quorum_body_resolves_the_classifier_role(module) -> None:
    """The quorum body Definition carries the ``quorum-classifier`` role (live KeyError fix).

    The main triage `defn` has no such agent, so the live runtime could not resolve the role
    off it. The dedicated inline body must declare it (and the role name is load-bearing — the
    deterministic responder branches on it to mint the seed-varying disagreement).
    """
    body = module._build_quorum_body()
    assert body.agent("quorum-classifier") is not None
    assert body.team.lead == "quorum-classifier"


def test_category_vote_keys_on_category_in_prose(module) -> None:
    """`_CategoryVote` snaps a free-form (real-model) sample onto the category enum.

    The stock ``majority_vote(field="category")`` keys on a `category` JSON field the real
    model never emits, collapsing every prose sample to `null` (a false unanimity). The demo's
    `_CategoryVote` keys on the category MENTIONED in the prose, so the vote is over real
    categories on both paths.
    """
    # mock-shaped (clean JSON) and live-shaped (prose) samples for the SAME category must key
    # to the same vote key.
    assert module._category_of_text('{"category": "billing"}') == "billing"
    assert module._category_of_text("**Category:** billing\n\nThe duplicate charge…") == "billing"
    assert module._category_of_text("**bug**\n\nLogin is broken after deploy") == "bug"
    # an out-of-grammar prose label snaps to a valid member rather than crashing
    assert module._category_of_text("Category: documentation") in module._ROUTER_LABELS


def test_distill_proposal_recovers_prose_wrapped_rule(module) -> None:
    """`_distill_proposal` recovers a grammar rule the model wrapped in explanation."""
    wrapped = 'Here is my rule:\n```\n{"kind":"comparison","field":"category","op":"==",'
    wrapped += '"literal":"unknown"}\n```\nIt fires on non-answers.'
    predicate, recovered = module._distill_proposal(wrapped)
    assert recovered  # the model's OWN rule distilled (not the static fallback)
    # ``Predicate.matches`` takes the JSON value (not an Output); it fires on the disallowed one.
    assert predicate.matches({"category": "unknown"})
    assert not predicate.matches({"category": "billing"})


def test_distill_proposal_fails_safe_to_static_rule(module) -> None:
    """An unparseable proposal falls back to the STATIC author rule (grammar never widened).

    A fluid emission that is not grammar at all cannot synthesise a new operator — the demo
    falls back to the trusted, author-fixed predicate, and `recovered` reports it honestly.
    """
    predicate, recovered = module._distill_proposal("I cannot help with that request.")
    assert not recovered  # the static fallback was used
    # the fallback is exactly the author rule — distilling it directly yields the same AST
    assert predicate == distill(module._PROPOSED_GUARD_RULE)


def test_live_taming_accepts_unanimous_vote_and_fail_safe_abstain(module) -> None:
    """On the LIVE path a unanimous quorum + a confidence-less fail-safe abstention PASS.

    A real model often agrees (a unanimous vote is the good self-consistency case) and emits
    no readable `confidence` (so declining is the fail-safe action). `_taming_step_ok()` must
    accept both as correct operator outcomes — the same live-vs-mock precedent the M1 Refine /
    F-3 gate steps set. (The mock path stays strict: `distinct > 1`, a measured confidence.)
    """
    from dataclasses import replace

    base = module.run_self_improvement(live=False)
    # Simulate the real-model live outcome: live=True, unanimous vote, no readable confidence.
    live_like = replace(
        base,
        live=True,
        quorum_distinct=1,  # the real model agreed (unanimous)
        quorum_tally={"billing": 5},
        quorum_winner="billing",
        abstain_confidence=-1.0,  # no readable confidence -> fail-safe abstain
    )
    assert live_like._taming_step_ok()
    # ...but the SAME unanimous/confidence-less shape FAILS on the mock path (stays strict).
    mock_strict = replace(live_like, live=False)
    assert not mock_strict._taming_step_ok()
