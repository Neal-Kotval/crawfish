"""CRA-101 acceptance: Output round-trips, is immutable, and gates wiring."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from crawfish.core import Flow, Parameter
from crawfish.output import Output, WireError, check_wire, output_satisfies_inputs
from crawfish.store import SqliteStore


def _pr_output() -> Output[dict[str, object]]:
    return Output(
        output_schema=[
            Parameter(name="title", type="str"),
            Parameter(name="number", type="int"),
        ],
        value={"title": "Fix bug", "number": 7},
        produced_by="source-1",
    )


def test_output_roundtrips_json() -> None:
    o = _pr_output()
    again = Output.model_validate_json(o.model_dump_json())
    assert again.value == o.value
    assert again.produced_by == "source-1"
    assert [p.name for p in again.output_schema] == ["title", "number"]


def test_output_is_immutable_once_produced() -> None:
    o = _pr_output()
    with pytest.raises(ValidationError):
        o.value = {"title": "tampered", "number": 0}


def test_derive_makes_fresh_output() -> None:
    o = _pr_output()
    d = o.derive(value={"title": "Fix bug", "number": 7}, produced_by="filter-1")
    assert d.id != o.id
    assert d.produced_by == "filter-1"
    assert o.produced_by == "source-1"  # upstream untouched


def test_wire_accepts_compatible_inputs() -> None:
    o = _pr_output()
    inputs = [Parameter(name="title", type="str", flow=Flow.FLUID)]
    assert output_satisfies_inputs(o, inputs)
    check_wire(o, inputs)  # no raise


def test_wire_rejects_type_mismatch() -> None:
    o = _pr_output()
    inputs = [Parameter(name="title", type="list[PR]")]  # str cannot feed list[PR]
    assert not output_satisfies_inputs(o, inputs)
    with pytest.raises(WireError):
        check_wire(o, inputs)


def test_wire_rejects_missing_required_field() -> None:
    o = _pr_output()
    inputs = [Parameter(name="author", type="str", required=True)]
    with pytest.raises(WireError):
        check_wire(o, inputs)


def test_optional_missing_field_is_ok() -> None:
    o = _pr_output()
    inputs = [Parameter(name="author", type="str", required=False, default=None)]
    assert output_satisfies_inputs(o, inputs)


def test_output_persists_via_store() -> None:
    store = SqliteStore()
    o = _pr_output()
    o.persist(store)
    assert store.get_record("output", o.id) is not None
