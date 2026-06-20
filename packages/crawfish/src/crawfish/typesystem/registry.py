"""Type model & registry — structural typed IO.

``Parameter.type`` is a string name (e.g. ``"str"``, ``"list[PR]"``). This module
turns those names into resolved :class:`TypeDef`s and answers the one question the
wiring guarantee rests on: *can a value of producer type flow into consumer type?*

Compatibility is **structural**, not string equality:

* primitives match by name;
* ``list[A] -> list[B]`` iff ``A -> B`` (covariant);
* a non-optional ``A`` may feed ``Optional[A]``; ``Optional[A] -> Optional[B]`` iff ``A -> B``;
* records use **width subtyping**: a producer record satisfies a consumer record
  when it has (at least) every field the consumer requires, each compatible.

Every type round-trips through JSON-Schema so the console & registry read it
without Python.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field

__all__ = [
    "TypeKind",
    "TypeDef",
    "TypeRegistry",
    "default_registry",
]


class TypeKind(str, Enum):
    PRIMITIVE = "primitive"
    RECORD = "record"
    LIST = "list"
    OPTIONAL = "optional"


_PRIMITIVE_JSON_SCHEMA: dict[str, dict[str, object]] = {
    "str": {"type": "string"},
    "int": {"type": "integer"},
    "float": {"type": "number"},
    "bool": {"type": "boolean"},
    "null": {"type": "null"},
    "json": {},  # any JSON value
}


class TypeDef(BaseModel):
    """A resolved type. Built by the registry; not authored directly."""

    name: str  # canonical name, e.g. "str", "PR", "list[PR]"
    kind: TypeKind
    fields: dict[str, str] = Field(default_factory=dict)  # records: field -> type name
    item: str | None = None  # list/optional: element type name

    model_config = {"frozen": True}


_GENERIC_RE = re.compile(r"^(list|Optional)\[(.+)\]$")
_OPTIONAL_SUFFIX_RE = re.compile(r"^(.+)\?$")


class TypeRegistry:
    """Holds named types and answers structural compatibility.

    Unknown bare names resolve to *nominal* primitives (matched by name) so
    authoring stays ergonomic; records are registered explicitly to unlock
    field-subset rules.
    """

    def __init__(self) -> None:
        self._records: dict[str, TypeDef] = {}
        self._primitives: set[str] = set(_PRIMITIVE_JSON_SCHEMA)

    # -- registration -------------------------------------------------------
    def register_primitive(self, name: str) -> None:
        self._primitives.add(name)

    def register_record(self, name: str, fields: dict[str, str]) -> TypeDef:
        td = TypeDef(name=name, kind=TypeKind.RECORD, fields=dict(fields))
        self._records[name] = td
        return td

    def is_registered(self, name: str) -> bool:
        return name in self._records or name in self._primitives

    # -- resolution ---------------------------------------------------------
    def resolve(self, type_str: str) -> TypeDef:
        """Parse a type string into a :class:`TypeDef`, recursing into generics."""
        text = type_str.strip()

        m = _OPTIONAL_SUFFIX_RE.match(text)
        if m:
            return self._optional(m.group(1).strip())

        m = _GENERIC_RE.match(text)
        if m:
            head, inner = m.group(1), m.group(2).strip()
            if head == "list":
                self.resolve(inner)  # validate element parses
                return TypeDef(name=f"list[{inner}]", kind=TypeKind.LIST, item=inner)
            return self._optional(inner)

        # bare name: registered record, registered/known primitive, or nominal.
        if text in self._records:
            return self._records[text]
        return TypeDef(name=text, kind=TypeKind.PRIMITIVE)

    def _optional(self, inner: str) -> TypeDef:
        self.resolve(inner)
        return TypeDef(name=f"Optional[{inner}]", kind=TypeKind.OPTIONAL, item=inner)

    # -- compatibility ------------------------------------------------------
    def is_compatible(self, producer: str, consumer: str) -> bool:
        """Can a value of ``producer`` type flow into a ``consumer`` port?"""
        return self._compat(self.resolve(producer), self.resolve(consumer))

    def explain(self, producer: str, consumer: str) -> str | None:
        """``None`` if compatible, else a structural reason string."""
        if self.is_compatible(producer, consumer):
            return None
        return f"type '{producer}' is not structurally compatible with '{consumer}'"

    def _compat(self, p: TypeDef, c: TypeDef) -> bool:
        # A non-optional producer may feed an optional consumer.
        if c.kind is TypeKind.OPTIONAL:
            assert c.item is not None
            inner_c = self.resolve(c.item)
            if p.kind is TypeKind.OPTIONAL:
                assert p.item is not None
                return self._compat(self.resolve(p.item), inner_c)
            return self._compat(p, inner_c)

        if p.kind is TypeKind.OPTIONAL:
            # optional producer cannot satisfy a required (non-optional) consumer
            return False

        if p.kind is TypeKind.LIST or c.kind is TypeKind.LIST:
            if p.kind is not TypeKind.LIST or c.kind is not TypeKind.LIST:
                return False
            assert p.item is not None and c.item is not None
            return self._compat(self.resolve(p.item), self.resolve(c.item))  # covariant

        if p.kind is TypeKind.RECORD or c.kind is TypeKind.RECORD:
            if p.kind is not TypeKind.RECORD or c.kind is not TypeKind.RECORD:
                return False
            # width subtyping: producer must supply every field the consumer needs.
            for fname, ftype in c.fields.items():
                if fname not in p.fields:
                    return False
                if not self.is_compatible(p.fields[fname], ftype):
                    return False
            return True

        # both primitive (possibly nominal): match by name
        return p.name == c.name

    # -- json-schema --------------------------------------------------------
    def json_schema(self, type_str: str) -> dict[str, object]:
        return self._schema(self.resolve(type_str))

    def _schema(self, td: TypeDef) -> dict[str, object]:
        if td.kind is TypeKind.PRIMITIVE:
            return dict(_PRIMITIVE_JSON_SCHEMA.get(td.name, {"$ref": f"#/types/{td.name}"}))
        if td.kind is TypeKind.LIST:
            assert td.item is not None
            return {"type": "array", "items": self._schema(self.resolve(td.item))}
        if td.kind is TypeKind.OPTIONAL:
            assert td.item is not None
            return {"anyOf": [self._schema(self.resolve(td.item)), {"type": "null"}]}
        # record
        return {
            "type": "object",
            "properties": {
                fname: self._schema(self.resolve(ftype)) for fname, ftype in td.fields.items()
            },
            "required": list(td.fields),
        }


# Process-wide default registry. Plugins register their types here via the
# "crawfish.types" entry-point group.
default_registry = TypeRegistry()
