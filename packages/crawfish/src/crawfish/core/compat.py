"""``parameters_compatible`` — the type-match check Batches use to decide wiring.

Resolves through the structural type registry (CRA-132), not string equality
(per the CRA-99 gap review).
"""

from __future__ import annotations

from crawfish.core.types import Parameter
from crawfish.typesystem.registry import TypeRegistry, default_registry

__all__ = ["parameters_compatible"]


def parameters_compatible(
    out: Parameter,
    in_: Parameter,
    registry: TypeRegistry | None = None,
) -> bool:
    """True if an output ``out`` can wire into an input ``in_``.

    A value flows producer → consumer, so types are checked structurally in that
    direction. An optional/defaulted input may go unfilled, but a *required*
    input must receive a structurally compatible value.
    """
    reg = registry or default_registry
    return reg.is_compatible(out.type, in_.type)
