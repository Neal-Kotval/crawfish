"""CRA-99 acceptance: shared core types validate, round-trip, and compat works."""

from __future__ import annotations

from crawfish.core import Flow, Parameter, Policy, PolicyKind, parameters_compatible


def test_parameter_roundtrips_json() -> None:
    p = Parameter(name="repo", type="str", flow=Flow.STATIC)
    again = Parameter.model_validate_json(p.model_dump_json())
    assert again == p


def test_parameter_defaults_to_fluid() -> None:
    assert Parameter(name="body", type="str").flow is Flow.FLUID


def test_static_and_fluid_distinguishable() -> None:
    static = Parameter(name="repo", type="str", flow=Flow.STATIC)
    fluid = Parameter(name="body", type="str")
    assert static.flow is not fluid.flow


def test_policy_roundtrips_json() -> None:
    pol = Policy(name="caps", kind=PolicyKind.GUARDRAIL, rules={"max_usd": 5})
    assert Policy.model_validate_json(pol.model_dump_json()) == pol


def test_parameters_compatible_str_to_str() -> None:
    out = Parameter(name="a", type="str")
    in_ = Parameter(name="b", type="str")
    assert parameters_compatible(out, in_)


def test_parameters_incompatible_str_to_list_pr() -> None:
    out = Parameter(name="a", type="str")
    in_ = Parameter(name="b", type="list[PR]")
    assert not parameters_compatible(out, in_)


def test_parameter_json_schema_export() -> None:
    # Pydantic gives the canvas/executor a JSON-schema for free.
    schema = Parameter.model_json_schema()
    assert schema["properties"]["flow"]["default"] == "fluid"
