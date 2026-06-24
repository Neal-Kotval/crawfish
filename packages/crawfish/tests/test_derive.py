"""CRA-223 (DV-0) + CRA-224 (AL-DV1) — the shared copy-on-write derive path.

DV-0 pins that the extraction is behaviour-preserving: the Tuner and ``crawfish.derive``
share ONE content-hash path (the same function objects, byte-identical hashing). AL-DV1
pins the copy-on-write composition law: every ``with_*`` returns a NEW FROZEN Definition,
the receiver is never mutated, structural equality ⇒ equal sha (idempotent), any knob diff
⇒ distinct sha, and a summon enters identity by a pinned snapshot (reference-not-embed).
"""

from __future__ import annotations

import pytest

from crawfish import derive
from crawfish.core.types import Flow, Parameter, Policy, PolicyKind
from crawfish.definition.types import AgentSpec, Definition, TeamSpec
from crawfish.versioning.version import FrozenError, Version


def _base() -> Definition:
    return Definition(
        team=TeamSpec(agents=[AgentSpec(role="worker", prompt="do the thing", model="slow")]),
    )


# == DV-0 — the shared content-hash path is one path ========================
def test_tuner_reexports_the_same_function_objects() -> None:
    """The Tuner's private names ARE ``crawfish.derive``'s — no second hashing path."""
    import crawfish.tuner as tuner

    assert tuner._refreeze is derive.refreeze
    assert tuner._with_agents is derive.with_agents
    assert derive._content_sha is derive.content_sha
    assert derive._refreeze is derive.refreeze


def test_content_sha_delegates_to_canonical_definition_law() -> None:
    base = _base()
    assert derive.content_sha(base) == base.content_sha()


def test_refreeze_is_byte_identical_to_canonical_sha() -> None:
    """The re-frozen version sha is exactly the canonical content sha (golden pin)."""
    base = _base()
    frozen = derive.refreeze(base, base.model_copy(deep=True))
    assert frozen.frozen is True
    assert frozen.version.sha == base.content_sha()


# == AL-DV1 — copy-on-write composition =====================================
def test_with_agent_returns_new_frozen_and_leaves_base_unchanged() -> None:
    base = derive.refreeze(_base(), _base())
    out = derive.with_agent(base, AgentSpec(role="reviewer", model="fast"))

    assert out.frozen is True
    assert out.version.sha != base.version.sha
    # base untouched: still one agent, still its original sha.
    assert [a.role for a in base.team.agents] == ["worker"]
    assert [a.role for a in out.team.agents] == ["worker", "reviewer"]


def test_with_agent_replace_swaps_same_role() -> None:
    base = derive.refreeze(_base(), _base())
    out = derive.with_agent(base, AgentSpec(role="worker", model="fast"), replace=True)
    assert [a.role for a in out.team.agents] == ["worker"]
    assert out.agent("worker") is not None
    assert out.agent("worker").model == "fast"  # type: ignore[union-attr]


def test_composition_is_idempotent_same_knobs_same_sha() -> None:
    """Two structurally-identical compositions ⇒ equal sha; any knob diff ⇒ distinct."""
    base = derive.refreeze(_base(), _base())
    a = derive.with_agent(base, AgentSpec(role="reviewer", model="fast"))
    b = derive.with_agent(base, AgentSpec(role="reviewer", model="fast"))
    c = derive.with_agent(base, AgentSpec(role="reviewer", model="slow"))
    assert a.version.sha == b.version.sha
    assert a.version.sha != c.version.sha


def test_composition_is_composable() -> None:
    base = derive.refreeze(_base(), _base())
    out = derive.with_inputs(
        derive.with_agent(base, AgentSpec(role="reviewer")),
        Parameter(name="q", type="str", flow=Flow.FLUID),
    )
    assert out.frozen is True
    assert [a.role for a in out.team.agents] == ["worker", "reviewer"]
    assert [p.name for p in out.inputs] == ["q"]


def test_with_on_receiver_never_raises_but_mutating_result_does() -> None:
    """``with_*`` copies first (no FrozenError); the returned frozen object rejects mutation."""
    base = derive.refreeze(_base(), _base())
    out = derive.with_agent(base, AgentSpec(role="reviewer"))  # no raise — copies first
    with pytest.raises(FrozenError):
        out.injected_prompts = []  # mutating the returned frozen object IS rejected


def test_with_skill_pins_a_version_and_versions_the_agent() -> None:
    base = derive.refreeze(_base(), _base())
    out = derive.with_skill(base, derive.SkillRef(id="summarize", version="0.3"))
    assert out.frozen is True
    assert out.version.sha != base.version.sha
    # the skill enters identity by pinned ref folded into dependencies (reference-not-embed).
    assert any("summarize" in d.id and d.version == "0.3" for d in out.dependencies)
    # a different pinned version diverges the sha.
    other = derive.with_skill(base, derive.SkillRef(id="summarize", version="0.4"))
    assert other.version.sha != out.version.sha


def test_with_context_stores_only_a_summon_ref_and_checksum_tracks_pin() -> None:
    """``with_context`` embeds no mutable content; checksum moves iff the pin moves."""
    base = derive.refreeze(_base(), _base())
    # A stable summonable identity so only its *pinned version* varies between cases.
    wiki_v1 = Definition(id="wiki", version=Version(major=1, minor=0))
    out1 = derive.with_context(base, wiki_v1)
    assert out1.frozen is True
    # only a ref is stored — the summoned body is NOT embedded.
    assert any("summon:" in d.id for d in out1.dependencies)

    # same pinned version ⇒ same checksum (idempotent).
    out1b = derive.with_context(base, Definition(id="wiki", version=Version(major=1, minor=0)))
    assert out1.export().checksum == out1b.export().checksum

    # a different pinned summon version ⇒ different checksum.
    wiki_v2 = Definition(id="wiki", version=Version(major=2, minor=0))
    out2 = derive.with_context(base, wiki_v2)
    assert out2.export().checksum != out1.export().checksum


def test_with_context_default_mode_is_readonly() -> None:
    base = derive.refreeze(_base(), _base())
    out = derive.with_context(base, Definition(version=Version(major=1, minor=0)))
    assert any("readonly" in d.id for d in out.dependencies)


def test_with_policy_folds_static_config_into_the_sha() -> None:
    base = derive.refreeze(_base(), _base())
    out = derive.with_policy(base, Policy(name="pii_redaction", kind=PolicyKind.GUARDRAIL))
    assert out.frozen is True
    assert out.version.sha != base.version.sha
    assert [p.name for p in out.assets.policies] == ["pii_redaction"]


def test_summon_ref_and_skill_ref_are_frozen_value_types() -> None:
    ref = derive.SummonRef(id="wiki", version="1.0", mode=derive.SummonMode.READONLY.value)
    assert ref.mode == "readonly"
    with pytest.raises(Exception):  # pydantic frozen — any mutation rejected  # noqa: B017, PT011
        ref.id = "other"  # type: ignore[misc]
