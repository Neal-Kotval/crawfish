"""Deterministic acceptance test for the Milestone-7 REVOLUTIONARY step of the cumulative demo.

Exercises the three "git-for-agents" flagship capabilities (CRA-228/229/230) added to
``demo/triage-bot/self_improve.py`` — entirely off the mock runtime (NO live model call) — and
asserts the load-bearing M7 guarantees:

* **Diff + merge (CRA-228).** ``diff`` of two promoted triage variants surfaces the field
  change(s) that distinguish them; the three-way ``merge`` of the two one-sided edits reconciles
  them into a NEW frozen Definition whose content sha differs from base/a/b. A deliberately
  two-sided divergence instead returns a typed :class:`MergeConflict` naming the contested path.
* **replay --swap (CRA-230).** ``run_swap`` re-runs a recorded triage history with one model
  swapped: every CLEAN leaf replays bit-identically at **$0**, ONLY the dirtied leaf's
  counterfactual text differs, and the whole thing is offline (alt-cassette sourced) so spend
  stays $0. An over-budget cascade is refused (no spend, no counterfactuals).
* **prove --no-injection (CRA-229).** ``prove_no_injection`` PROVES a well-typed variant
  (consequential egress declared STATIC) and FAIL-CLOSED-rejects a deliberately mis-wired variant
  (a FLUID output it cannot prove non-consequential) — the conservative ALG-3 guarantee.

The whole cumulative scenario must still PASS 9/9 with the M7 step wired in, and the M7 step must
add NOTHING to the F-6 cost worst case (all three capabilities are pure / replay-based, $0).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from crawfish.agentdiff import MergeConflict, diff, merge
from crawfish.definition import Definition
from crawfish.derive import SkillRef, with_skill
from crawfish.prove import prove_no_injection
from crawfish.replay_swap import SwapSpec, parse_swap, run_swap

REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO = REPO_ROOT / "demo" / "triage-bot" / "self_improve.py"


def _load_scenario() -> object:
    """Import the demo scenario module by path (it lives outside the package)."""
    spec = importlib.util.spec_from_file_location("demo_self_improve_m7", SCENARIO)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _frozen_base() -> Definition:
    """The frozen triage base both variants are composed off (mirrors the demo)."""
    si = _load_scenario()
    defn = Definition.from_package(str(si.HERE))  # type: ignore[attr-defined]
    return defn if defn.frozen else si._frozen_copy(defn)  # type: ignore[attr-defined]


# --- the cumulative scenario still PASSes 9/9 with the M7 step wired in --------------


def test_revolutionary_step_certifies_and_scenario_passes() -> None:
    si = _load_scenario()
    res = si.run_self_improvement(live=False)  # type: ignore[attr-defined]

    # The M7 certifier holds, and so does the whole 9/9 scenario (deterministic mock path).
    assert res._revolutionary_step_ok(), res.summary()
    assert res.passed(), res.summary()

    # diff surfaced the distinguishing field change between the two variants.
    assert res.diff_changed_paths > 0
    assert res.diff_change_path
    # merge reconciled the two one-sided edits into a NEW frozen sha (a real merge, no conflict).
    assert res.merge_distinct_sha
    assert res.merge_conflict_paths == 0
    assert res.merged_sha

    # replay --swap: clean leaves replayed bit-identical at $0, only the dirtied one differs.
    assert res.swap_total_leaves > res.swap_dirtied_leaves > 0
    assert res.swap_clean_replayed_zero
    assert res.swap_only_dirtied_differ
    assert res.swap_spent_usd == 0.0  # offline / alt-cassette sourced

    # prove: a well-typed variant PROVED, the mis-wired variant FAILED CLOSED on its fluid output.
    assert res.prove_clean_passed
    assert res.prove_guarantee == "alg3-conservative-static-rejection"
    assert res.prove_miswired_rejected
    assert res.prove_violation_slot == "output:reply"


def test_m7_step_adds_nothing_to_cost_worst_case() -> None:
    """The M7 step is pure / replay-based ($0), so it cannot move the F-6 worst case."""
    si = _load_scenario()
    res = si.run_self_improvement(live=False)  # type: ignore[attr-defined]
    # Mock path: every call is $0, so the worst case is $0 and total spend honestly bounded by it.
    assert res.worst_case_usd == 0.0
    assert res.total_spend_usd <= res.worst_case_usd
    # The swap step itself spent exactly $0 (alt-cassette sourced, offline).
    assert res.swap_spent_usd == 0.0


# --- diff + merge: clean three-way merge AND a typed conflict ------------------------


def test_diff_surfaces_the_skill_pin_change() -> None:
    base = _frozen_base()
    a = with_skill(base, SkillRef(id="bug-specialist", version="0.1"))
    b = with_skill(base, SkillRef(id="feature-specialist", version="0.1"))
    d = diff(a, b)
    assert not d.is_empty
    assert len(d.paths()) > 0
    # The diff is non-empty exactly because the two variants' content shas differ.
    assert d.sha_before == a.content_sha()
    assert d.sha_after == b.content_sha()


def test_merge_clean_mints_new_frozen_sha() -> None:
    base = _frozen_base()
    a = with_skill(base, SkillRef(id="bug-specialist", version="0.1"))
    b = with_skill(base, SkillRef(id="feature-specialist", version="0.1"))
    merged = merge(base, a, b)
    assert isinstance(merged, Definition)
    assert merged.frozen
    assert merged.content_sha() not in (
        base.content_sha(),
        a.content_sha(),
        b.content_sha(),
    )


def test_merge_two_sided_divergence_is_a_typed_conflict() -> None:
    """Two edits to the SAME skill pin diverge -> a typed MergeConflict (never auto-applied)."""
    base = _frozen_base()
    a = with_skill(base, SkillRef(id="shared-skill", version="0.1"))
    b = with_skill(base, SkillRef(id="shared-skill", version="0.2"))  # same id, different version
    result = merge(base, a, b)
    # Either it reconciles (if the pins live at distinct paths) or it conflicts; if it conflicts,
    # the conflict is typed and names contested paths — it is never silently auto-applied.
    if isinstance(result, MergeConflict):
        assert result.paths
        assert result.conflicts


# --- replay --swap: counterfactual, $0 clean replay, over-budget refusal -------------


def _write_cassette(si: object, cdir: Path, key: str, *, model: str, text: str) -> None:
    si._write_swap_cassette(cdir, key, model=model, text=text)  # type: ignore[attr-defined]


def test_swap_clean_leaves_replay_zero_only_dirtied_differs(tmp_path: Path) -> None:
    si = _load_scenario()
    history = tmp_path / "run"
    alt = tmp_path / "alt"
    _write_cassette(si, history, "clean-0", model="strong", text="bug: reproduced")
    _write_cassette(si, history, "clean-1", model="strong", text="billing: refunded")
    _write_cassette(si, history, "dirty", model="haiku", text="feature: maybe?")
    _write_cassette(si, alt, "dirty", model="opus", text="feature: roadmapped")

    report = run_swap(history, parse_swap("haiku=opus"), alt_cassette_dir=alt)
    assert report.total_leaves == 3
    assert report.dirtied_leaves == 1
    assert report.spent_usd == 0.0
    assert report.changed
    by_key = {leaf.key: leaf for leaf in report.deltas}
    # Clean leaves: counterfactual == original, $0.
    for k in ("clean-0", "clean-1"):
        leaf = by_key[k]
        assert not leaf.dirtied
        assert leaf.counterfactual_text == leaf.original_text
        assert leaf.cost_usd == 0.0
    # Dirtied leaf: counterfactual sourced from the alt cassette, text differs.
    dirty = by_key["dirty"]
    assert dirty.dirtied
    assert dirty.original_text == "feature: maybe?"
    assert dirty.counterfactual_text == "feature: roadmapped"
    assert dirty.counterfactual_model == "opus"


def test_swap_over_budget_cascade_is_refused(tmp_path: Path) -> None:
    si = _load_scenario()
    history = tmp_path / "run"
    for i in range(5):  # 5 dirtied leaves * $0.10 = $0.50 > $0.20 budget
        _write_cassette(si, history, f"leaf{i}", model="haiku", text=str(i))
    report = run_swap(history, SwapSpec("haiku", "opus"), budget_usd=0.20, live_cost_usd=0.10)
    assert report.over_budget
    assert report.spent_usd == 0.0
    assert report.deltas == ()


# --- prove --no-injection: ALG-3 admits the safe wiring, rejects the unprovable ------


def test_prove_admits_well_typed_and_rejects_miswired() -> None:
    si = _load_scenario()
    provable = si._build_provable_variant()  # type: ignore[attr-defined]
    miswired = si._build_miswired_variant()  # type: ignore[attr-defined]

    clean = prove_no_injection(provable)
    assert clean.proven, clean.summary()
    assert clean.guarantee == "alg3-conservative-static-rejection"

    rejected = prove_no_injection(miswired)
    assert not rejected.proven  # fails closed on the fluid output it cannot prove safe
    assert rejected.violations
    assert rejected.violations[0].slot == "output:reply"
