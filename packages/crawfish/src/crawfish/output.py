"""Output — the typed, self-describing envelope between nodes (CRA-101).

An ``Output`` carries a value, the schema of that value, and the id of the node
that produced it. It is **immutable once produced** (frozen): Filters and other
transforms derive a *fresh* Output via :meth:`derive`, keeping the upstream value
intact for audit. Wiring two nodes is allowed only when an upstream Output's schema
satisfies the downstream node's required inputs (structural check, CRA-132).
"""

from __future__ import annotations

from typing import Generic

from pydantic import BaseModel, Field

from crawfish.core.compat import parameters_compatible
from crawfish.core.ids import new_id
from crawfish.core.types import JSONValue, Parameter, T
from crawfish.typesystem.registry import TypeRegistry

__all__ = ["Output", "output_satisfies_inputs", "check_wire", "WireError"]


class WireError(TypeError):
    """Raised when an upstream Output cannot wire into a downstream node's inputs."""


class Output(BaseModel, Generic[T]):
    """The unit of data flowing between nodes. Frozen once produced."""

    id: str = Field(default_factory=new_id)
    output_schema: list[Parameter] = Field(default_factory=list)  # shape of `value`
    value: T
    produced_by: str  # node id that emitted it
    # Taint: True when this value derives from fluid (untrusted) input. A tainted
    # value must never be treated as trusted downstream (CRA-114). Propagates
    # through `derive`.
    tainted: bool = False

    model_config = {"frozen": True}

    def derive(
        self,
        *,
        value: JSONValue,
        produced_by: str,
        output_schema: list[Parameter] | None = None,
        tainted: bool | None = None,
    ) -> Output[JSONValue]:
        """Create a fresh Output from this one (the immutable-derivation path).

        Taint propagates: a value derived from a tainted Output stays tainted
        unless explicitly overridden.
        """
        return Output(
            value=value,
            produced_by=produced_by,
            output_schema=output_schema if output_schema is not None else list(self.output_schema),
            tainted=self.tainted if tainted is None else tainted,
        )

    def persist(self, store: object, *, org_id: str = "local") -> None:
        """Persist this Output through the ``Store`` seam."""
        # Imported lazily / typed loosely to avoid a hard import cycle with store.
        store.put_record(  # type: ignore[attr-defined]
            "output", self.id, self.model_dump(mode="json"), org_id=org_id
        )


def output_satisfies_inputs(
    output: Output[object],
    inputs: list[Parameter],
    *,
    registry: TypeRegistry | None = None,
) -> bool:
    """True if ``output``'s schema can satisfy every *required* downstream input.

    Each required input must be matched by name to a parameter in the output's
    schema whose type is structurally compatible (producer → consumer).
    """
    by_name = {p.name: p for p in output.output_schema}
    for want in inputs:
        have = by_name.get(want.name)
        if have is None:
            if want.required and want.default is None:
                return False
            continue
        if not parameters_compatible(have, want, registry):
            return False
    return True


def check_wire(
    output: Output[object],
    inputs: list[Parameter],
    *,
    registry: TypeRegistry | None = None,
) -> None:
    """Raise :class:`WireError` if ``output`` cannot wire into ``inputs``."""
    if not output_satisfies_inputs(output, inputs, registry=registry):
        names = {p.name for p in output.output_schema}
        wanted = {p.name: p.type for p in inputs}
        raise WireError(f"output (schema fields {sorted(names)}) cannot satisfy inputs {wanted}")
