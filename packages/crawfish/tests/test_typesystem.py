"""CRA-132 acceptance: structural compatibility + JSON-schema round-trip."""

from __future__ import annotations

import pytest

from crawfish.typesystem import TypeRegistry


@pytest.fixture
def reg() -> TypeRegistry:
    r = TypeRegistry()
    r.register_record("PR", {"title": "str", "number": "int", "body": "str"})
    r.register_record("PRSummary", {"title": "str", "number": "int"})
    return r


def test_list_pr_compatible_with_list_pr(reg: TypeRegistry) -> None:
    assert reg.is_compatible("list[PR]", "list[PR]")


def test_str_not_compatible_with_list_pr(reg: TypeRegistry) -> None:
    assert not reg.is_compatible("str", "list[PR]")
    assert reg.explain("str", "list[PR]") is not None


def test_record_width_subtyping(reg: TypeRegistry) -> None:
    # producer PR has all of consumer PRSummary's fields -> compatible.
    assert reg.is_compatible("PR", "PRSummary")
    # consumer needs a field producer lacks -> not compatible.
    assert not reg.is_compatible("PRSummary", "PR")


def test_list_covariance(reg: TypeRegistry) -> None:
    assert reg.is_compatible("list[PR]", "list[PRSummary]")
    assert not reg.is_compatible("list[PRSummary]", "list[PR]")


def test_optional_widening(reg: TypeRegistry) -> None:
    assert reg.is_compatible("str", "Optional[str]")  # non-optional feeds optional
    assert not reg.is_compatible("Optional[str]", "str")  # optional can't feed required
    assert reg.is_compatible("Optional[PR]", "Optional[PRSummary]")


def test_json_schema_roundtrip(reg: TypeRegistry) -> None:
    assert reg.json_schema("str") == {"type": "string"}
    assert reg.json_schema("list[int]") == {"type": "array", "items": {"type": "integer"}}
    rec = reg.json_schema("PRSummary")
    assert rec["type"] == "object"
    assert set(rec["required"]) == {"title", "number"}  # type: ignore[arg-type]
