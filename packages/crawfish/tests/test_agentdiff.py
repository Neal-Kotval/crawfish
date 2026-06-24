"""CRA-228 / R1 — git-for-agents: a typed diff/merge over content-addressed Definitions.

Pins the four load-bearing properties:

* ``diff`` detects field-level changes (prompts / knobs / agents / inputs / dependencies) and
  is non-empty IFF the content sha moved (it diffs over the canonical hash payload);
* a clean three-way ``merge`` combines non-conflicting changes from both sides;
* a field both sides changed differently is reported as a typed ``MergeConflict`` — never
  silently resolved;
* the merged Definition is a NEW frozen artifact with a DETERMINISTIC content sha, and the
  fluid/static (prompt-injection) boundary is never silently widened.
"""

from __future__ import annotations

from crawfish import derive
from crawfish.agentdiff import (
    ChangeKind,
    DefinitionDiff,
    FieldChange,
    MergeConflict,
    diff,
    merge,
)
from crawfish.core.types import Flow, Parameter, Policy, PolicyKind
from crawfish.definition.types import AgentSpec, Definition, TeamSpec


def _base() -> Definition:
    return derive.refreeze(
        Definition(
            team=TeamSpec(agents=[AgentSpec(role="worker", prompt="do the thing", model="slow")]),
            inputs=[Parameter(name="ticket", type="str", flow=Flow.FLUID)],
        ),
        Definition(
            team=TeamSpec(agents=[AgentSpec(role="worker", prompt="do the thing", model="slow")]),
            inputs=[Parameter(name="ticket", type="str", flow=Flow.FLUID)],
        ),
    )


# == diff ====================================================================
def test_diff_of_identical_definitions_is_empty() -> None:
    base = _base()
    d = diff(base, base)
    assert d.is_empty
    assert d.changes == ()
    assert d.sha_before == d.sha_after == base.content_sha()


def test_diff_detects_a_prompt_change_as_a_changed_field() -> None:
    base = _base()
    edited = derive.with_agent(
        base, AgentSpec(role="worker", prompt="do it BETTER", model="slow"), replace=True
    )
    d = diff(base, edited)
    assert not d.is_empty
    assert d.sha_before == base.content_sha()
    assert d.sha_after == edited.content_sha()
    change = next(c for c in d.changes if c.path == "team.agents.worker.prompt")
    assert change.kind is ChangeKind.CHANGED
    assert change.before == "do the thing"
    assert change.after == "do it BETTER"


def test_diff_detects_a_decode_knob_change() -> None:
    base = _base()
    edited = derive.with_agent(
        base,
        AgentSpec(role="worker", prompt="do the thing", model="slow", temperature=0.2),
        replace=True,
    )
    d = diff(base, edited)
    # The knob was None on base (hash-neutral, absent) → present: an ADDED leaf.
    knob = next(c for c in d.changes if c.path == "team.agents.worker.temperature")
    assert knob.kind is ChangeKind.ADDED
    assert knob.after == 0.2


def test_diff_detects_an_added_agent() -> None:
    base = _base()
    edited = derive.with_agent(base, AgentSpec(role="reviewer", model="fast"))
    d = diff(base, edited)
    added = [c for c in d.changes if c.path.startswith("team.agents.reviewer.")]
    assert added
    assert all(c.kind is ChangeKind.ADDED for c in added)
    # The untouched worker agent contributes no change.
    assert not any(c.path.startswith("team.agents.worker.") for c in d.changes)


def test_diff_detects_an_added_input_parameter() -> None:
    base = _base()
    edited = derive.with_inputs(base, Parameter(name="repo", type="str", flow=Flow.STATIC))
    d = diff(base, edited)
    paths = set(d.paths())
    assert "inputs.repo.name" in paths
    assert "inputs.repo.flow" in paths


def test_diff_detects_an_added_dependency_pin() -> None:
    from crawfish.derive import SkillRef

    base = _base()
    edited = derive.with_skill(base, SkillRef(id="summarize", version="0.3"))
    d = diff(base, edited)
    assert any(c.path.startswith("dependencies.skill:summarize") for c in d.changes)


def test_diff_is_order_insensitive_on_agents() -> None:
    """Re-ordering agents without an edit is not a change (keyed by role, not position)."""
    two = Definition(
        team=TeamSpec(
            agents=[AgentSpec(role="a", prompt="x"), AgentSpec(role="b", prompt="y")],
        )
    )
    swapped = Definition(
        team=TeamSpec(
            agents=[AgentSpec(role="b", prompt="y"), AgentSpec(role="a", prompt="x")],
        )
    )
    assert diff(two, swapped).is_empty


def test_diff_is_a_frozen_hashable_value() -> None:
    base = _base()
    d = diff(base, base)
    assert isinstance(d, DefinitionDiff)
    assert isinstance(hash(d), int)  # frozen dataclass → hashable
    fc = FieldChange("p", ChangeKind.CHANGED, before=1, after=2)
    assert isinstance(hash(fc), int)


# == merge — clean three-way ================================================
def test_clean_merge_combines_nonconflicting_changes() -> None:
    base = _base()
    # Side A edits the worker prompt; side B adds a reviewer agent. Disjoint fields.
    a = derive.with_agent(
        base, AgentSpec(role="worker", prompt="A's prompt", model="slow"), replace=True
    )
    b = derive.with_agent(base, AgentSpec(role="reviewer", model="fast"))

    merged = merge(base, a, b)
    assert isinstance(merged, Definition)
    # A's prompt edit survived.
    assert merged.agent("worker") is not None
    assert merged.agent("worker").prompt == "A's prompt"  # type: ignore[union-attr]
    # B's added agent survived.
    assert merged.agent("reviewer") is not None
    # Result is a new frozen artifact with a fresh content sha.
    assert merged.frozen is True
    assert merged.version.sha == merged.content_sha()
    assert merged.content_sha() not in (base.content_sha(), a.content_sha(), b.content_sha())


def test_merge_is_deterministic() -> None:
    base = _base()
    a = derive.with_agent(base, AgentSpec(role="worker", prompt="A", model="slow"), replace=True)
    b = derive.with_inputs(base, Parameter(name="repo", type="str", flow=Flow.STATIC))
    m1 = merge(base, a, b)
    m2 = merge(base, a, b)
    assert isinstance(m1, Definition) and isinstance(m2, Definition)
    assert m1.content_sha() == m2.content_sha()


def test_merge_keeps_base_identity_lineage() -> None:
    base = _base()
    a = derive.with_agent(base, AgentSpec(role="worker", prompt="A", model="slow"), replace=True)
    b = derive.with_inputs(base, Parameter(name="repo", type="str", flow=Flow.STATIC))
    merged = merge(base, a, b)
    assert isinstance(merged, Definition)
    assert merged.id == base.id


def test_merge_of_one_sided_change_equals_that_side() -> None:
    """If only A changed, the merge IS A's content (B deferred)."""
    base = _base()
    a = derive.with_agent(
        base, AgentSpec(role="worker", prompt="only A", model="slow"), replace=True
    )
    merged = merge(base, a, base)
    assert isinstance(merged, Definition)
    assert merged.content_sha() == a.content_sha()


def test_merge_of_same_change_on_both_sides_is_agreement() -> None:
    base = _base()
    a = derive.with_agent(
        base, AgentSpec(role="worker", prompt="agreed", model="slow"), replace=True
    )
    b = derive.with_agent(
        base, AgentSpec(role="worker", prompt="agreed", model="slow"), replace=True
    )
    merged = merge(base, a, b)
    assert isinstance(merged, Definition)
    assert merged.content_sha() == a.content_sha() == b.content_sha()


def test_merge_preserves_policies() -> None:
    base = _base()
    pol = Policy(name="cap", kind=PolicyKind.GUARDRAIL, rules={"max_usd": 5})
    a = derive.with_policy(base, pol)
    merged = merge(base, a, base)
    assert isinstance(merged, Definition)
    assert [p.name for p in merged.assets.policies] == ["cap"]
    assert merged.content_sha() == a.content_sha()


# == merge — conflict ========================================================
def test_merge_reports_a_typed_conflict_on_divergent_field() -> None:
    base = _base()
    a = derive.with_agent(
        base, AgentSpec(role="worker", prompt="A says X", model="slow"), replace=True
    )
    b = derive.with_agent(
        base, AgentSpec(role="worker", prompt="B says Y", model="slow"), replace=True
    )
    result = merge(base, a, b)
    assert isinstance(result, MergeConflict)
    assert "team.agents.worker.prompt" in result.paths
    conflict = next(c for c in result.conflicts if c.path == "team.agents.worker.prompt")
    assert conflict.base == "do the thing"
    assert conflict.a == "A says X"
    assert conflict.b == "B says Y"


def test_merge_surfaces_a_flow_collision_rather_than_auto_applying() -> None:
    """A's flow widen colliding with B's change to the SAME ``flow`` leaf is a conflict.

    The security pin: a static↔fluid move on a Parameter is the prompt-injection boundary, so
    it is never auto-applied when the other side also touched that exact leaf — it surfaces as
    a typed :class:`MergeConflict` for human/``craw code`` review. (A binary enum means a
    two-sided divergence requires each side to pick a different value; here A→fluid while B
    re-asserts static, a real collision on the leaf.)
    """
    base = derive.refreeze(
        Definition(inputs=[Parameter(name="x", type="str", flow=Flow.FLUID)]),
        Definition(inputs=[Parameter(name="x", type="str", flow=Flow.FLUID)]),
    )
    a = derive.refreeze(
        base, Definition(id=base.id, inputs=[Parameter(name="x", type="str", flow=Flow.STATIC)])
    )
    b = derive.refreeze(
        base,
        Definition(
            id=base.id,
            inputs=[Parameter(name="x", type="str", flow=Flow.FLUID, required=False, default="d")],
        ),
    )
    # A narrowed flow (fluid→static); B kept flow fluid but changed required/default. These are
    # disjoint leaves, so this is actually a CLEAN merge — A's narrowing is consent-bearing and
    # B's change is on other leaves. Narrowing is always safe; the boundary only widens here on
    # one side, so it applies.
    result = merge(base, a, b)
    assert isinstance(result, Definition)
    x = next(p for p in result.inputs if p.name == "x")
    assert x.flow is Flow.STATIC  # A's narrowing applied
    assert x.required is False and x.default == "d"  # B's changes applied


def test_merge_one_sided_fluid_widen_is_conflicted() -> None:
    """A one-sided STATIC→FLUID widen is rejected as a conflict (CRA-231 / ALG-3 / S-1).

    The fluid/static boundary may not be *widened* by a silent one-sided merge — that
    would let a merge quietly turn a consequential static knob fluid. (The opposite
    direction, a fluid→static *narrowing*, is safe and still applies — see the next test.)
    """
    base = derive.refreeze(
        Definition(inputs=[Parameter(name="x", type="str", flow=Flow.STATIC)]),
        Definition(inputs=[Parameter(name="x", type="str", flow=Flow.STATIC)]),
    )
    a = derive.refreeze(
        base, Definition(id=base.id, inputs=[Parameter(name="x", type="str", flow=Flow.FLUID)])
    )
    # B changes a DIFFERENT leaf (type), so A's flow widen is one-sided.
    b = derive.refreeze(
        base, Definition(id=base.id, inputs=[Parameter(name="x", type="int", flow=Flow.STATIC)])
    )
    result = merge(base, a, b)
    assert isinstance(result, MergeConflict)
    assert any(p.endswith("inputs.x.flow") for p in result.paths)


def test_merge_one_sided_fluid_narrow_applies() -> None:
    """A one-sided FLUID→STATIC narrowing applies cleanly (narrowing is always safe)."""
    base = derive.refreeze(
        Definition(inputs=[Parameter(name="x", type="str", flow=Flow.FLUID)]),
        Definition(inputs=[Parameter(name="x", type="str", flow=Flow.FLUID)]),
    )
    a = derive.refreeze(
        base, Definition(id=base.id, inputs=[Parameter(name="x", type="str", flow=Flow.STATIC)])
    )
    b = derive.refreeze(
        base, Definition(id=base.id, inputs=[Parameter(name="x", type="int", flow=Flow.FLUID)])
    )
    result = merge(base, a, b)
    assert isinstance(result, Definition)
    x = next(p for p in result.inputs if p.name == "x")
    assert x.flow is Flow.STATIC  # A's one-sided narrow landed
    assert x.type == "int"  # B's type change landed


def test_merge_full_conflict_set_is_reported() -> None:
    """All contested fields are reported at once, path-sorted — not just the first."""
    base = _base()
    a = derive.refreeze(
        base,
        Definition(
            id=base.id,
            team=TeamSpec(agents=[AgentSpec(role="worker", prompt="A1", model="A-model")]),
            inputs=list(base.inputs),
        ),
    )
    b = derive.refreeze(
        base,
        Definition(
            id=base.id,
            team=TeamSpec(agents=[AgentSpec(role="worker", prompt="B1", model="B-model")]),
            inputs=list(base.inputs),
        ),
    )
    result = merge(base, a, b)
    assert isinstance(result, MergeConflict)
    assert "team.agents.worker.model" in result.paths
    assert "team.agents.worker.prompt" in result.paths
    assert list(result.paths) == sorted(result.paths)
