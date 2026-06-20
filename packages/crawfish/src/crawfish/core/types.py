"""Shared core types — the connective tissue every other primitive imports.

These settle two foundational decisions: how data is typed (static vs. fluid
``Parameter``s) and what counts as a node (the ``Node`` ABC and ``NodeKind``).
Nothing node-specific belongs here; keep it thin and stable.
"""

from __future__ import annotations

from abc import ABC
from enum import Enum
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from crawfish.core.ids import new_id

# JSON-serialisable value. Kept as Any because Pydantic validates concrete
# shapes at the boundaries (Parameter.type carries the real type information).
JSONValue = Any
T = TypeVar("T")

__all__ = [
    "JSONValue",
    "T",
    "new_id",
    "Flow",
    "Parameter",
    "NodeKind",
    "Node",
    "PolicyKind",
    "Policy",
]


class Flow(str, Enum):
    """Whether a parameter is set once per batch or varies per item.

    ``FLUID`` is also the prompt-injection boundary: fluid values reach the model
    as session *data*, never concatenated into instructions (enforced in the
    Definition compiler / runtime).
    """

    STATIC = "static"  # set once at batch start (e.g. a repo link)
    FLUID = "fluid"  # changes per item as data streams (e.g. a ticket body)


class Parameter(BaseModel):
    """A typed parameter on an input/output boundary.

    ``type`` is a string name resolved against the type registry
    (:mod:`crawfish.typesystem`); it is intentionally language-neutral so the
    console and registry can read port shapes without importing Python.
    """

    name: str
    type: str  # e.g. "str", "list[PR]"; resolved via the type registry
    required: bool = True
    default: JSONValue | None = None
    flow: Flow = Flow.FLUID  # static (set once) vs fluid (per-item)


class NodeKind(str, Enum):
    SOURCE = "source"
    BATCH = "batch"
    SINK = "sink"
    FILTER = "filter"
    AGGREGATOR = "aggregator"
    ROUTER = "router"


class Node(ABC):
    """Anything that can sit in a pipeline.

    Concrete nodes set ``id``/``name``/``kind`` in ``__init__``. This is an ABC
    (not a Pydantic model) because nodes carry behaviour, not just data.
    """

    id: str
    name: str
    kind: NodeKind


class PolicyKind(str, Enum):
    GUARDRAIL = "guardrail"  # what an agent may/may not do, spend caps, content
    ROUTING = "routing"  # which model runs under which conditions
    PERMISSION = "permission"  # which sources / sinks / data an agent may touch


class Policy(BaseModel):
    """Importable rule bundle: guardrails, model-routing, permissions."""

    name: str
    kind: PolicyKind
    rules: dict[str, JSONValue] = Field(default_factory=dict)
