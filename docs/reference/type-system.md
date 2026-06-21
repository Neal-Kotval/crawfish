# Type system

The engine that decides whether two ports can connect. It turns a parameter's string type
name (`"str"`, `"list[PR]"`) into a resolved type, then answers the one question wiring
rests on: *can a value of the producer's type flow into the consumer's port?* It lives in
`crawfish.typesystem`.

`TypeKind` · `TypeDef` · `TypeRegistry` · `default_registry`

## Types are strings the registry gives meaning to

Every [parameter](core-types.md#parameter) on a node carries a `type` as a **string name**,
not a Python type object. The type system does two jobs with those strings: it **resolves** a
name into a structured description, and it decides **compatibility** — whether one resolved
type can satisfy another.

Compatibility is **structural**, never by spelling. Two types match because of their *shape*,
not because their names happen to be equal. The system understands four shapes (`TypeKind`):

- **Primitive** — an atom like `str`, `int`, `bool`. The built-ins are `str`, `int`, `float`,
  `bool`, `null`, and `json` (any JSON value). Any unregistered bare name is also treated as a
  primitive, matched by name — so `"PR"` works without setup.
- **Record** — a named bundle of fields, each field itself a type name (`Ticket` =
  `{id: str, body: str}`). You register these explicitly.
- **List** — a homogeneous sequence, written `list[X]`.
- **Optional** — a value that may be absent, written `X?` or `Optional[X]`.

A `TypeRegistry` holds the named records and primitives and answers these questions.
`default_registry` is the single process-wide registry the rest of the framework uses unless
you hand it your own.

## Width subtyping

The headline rule for records is **width subtyping**: a producer record satisfies a consumer
record when it carries *at least* every field the consumer asks for, each one compatible. A
richer record can always stand in for a narrower one — extra fields are harmless. The reverse
fails: a record missing a field the consumer requires cannot satisfy it.

## Structural, not nominal

Compatibility never depends on Python class identity or string equality. The desktop console
and the unit registry must read a node's port shapes *without importing Python*, so the answer
has to be decidable from the type names alone. That is the structural-registry decision in
[ADR 0002](../architecture/decisions/0002-structural-type-registry.md): types compare by shape,
resolved through a registry, never by `==` on the strings. This is what lets
[`parameters_compatible`](core-types.md#parameters_compatible) wire `"list[PR]"` to a record
with the right fields.

## How resolution parses a name

`resolve` is a small recursive-descent parser over the type string, tried in this order:

1. A trailing `?` (`"str?"`) → an **Optional** wrapping the inner name.
2. A generic `list[...]` or `Optional[...]` → a **List** (item validated by recursing) or an
   **Optional**.
3. A bare name that is a registered record → that **Record**'s `TypeDef`.
4. Any other bare name → a nominal **Primitive** named for the string.

Step 4 is the ergonomic fallthrough: an unknown name like `"PR"` resolves to a primitive
matched by name, so authoring a pipeline needs no registration until you want field-subset
rules. Registering a record with `register_record` is precisely what unlocks width subtyping
for that name.

!!! note "Good to know"

    An unregistered name still *resolves* — nominally, as a primitive matched by name. It just
    can't do field-subset checks until you register it as a record. So `is_registered("PR")`
    can be `False` while `resolve("PR")` succeeds.

## The compatibility rules

`is_compatible(producer, consumer)` resolves both names and walks the shapes. The directional
rules, in the order they are checked:

- **Optional consumer** — a plain (non-optional) producer may feed an `Optional` consumer;
  `Optional[A]` feeds `Optional[B]` iff `A` feeds `B`.
- **Optional producer into a required consumer** — rejected. A maybe-absent value cannot
  satisfy a port that demands a value.
- **Lists are covariant** — `list[A]` feeds `list[B]` iff `A` feeds `B`. A list on one side and
  a non-list on the other never match.
- **Records use width subtyping** — for every field the consumer needs, the producer must have
  that field and its type must be compatible. A record never matches a non-record.
- **Primitives** match by canonical name (this is where nominal primitives like `PR` compare).

`explain(producer, consumer)` returns `None` when compatible, otherwise a one-line structural
reason — useful for surfacing *why* a wire was rejected.

## JSON-Schema round-trip

`json_schema(type_str)` emits a standard JSON-Schema fragment for any resolved type:
primitives map to their schema (`str` → `{"type": "string"}`), lists to `{"type": "array",
"items": ...}`, optionals to `{"anyOf": [..., {"type": "null"}]}`, and records to a `"object"`
with `properties` and a `required` list of every field. A nominal type with no known schema
emits a `{"$ref": "#/types/<name>"}` placeholder. This is the bridge that lets the console read
type shapes without Python.

## The default registry

`default_registry` is one `TypeRegistry` instance created at import time. Plugins register
their types into it via the `crawfish.types` entry-point group, and
[`parameters_compatible`](core-types.md#parameters_compatible) falls back to it when no registry
is passed. Construct your own `TypeRegistry` for isolation (tests, a sandboxed tenant); share
`default_registry` for the normal process-wide view.

## Example

Register a narrow record and a wider one, resolve a generic, and watch width subtyping decide
compatibility — extra fields satisfy a port needing fewer; a missing field does not.

```python
import json
from crawfish.typesystem.registry import TypeRegistry, default_registry

reg = TypeRegistry()

# A record the consumer needs, plus a wider producer record (one extra field).
reg.register_record("Ticket", {"id": "str", "body": "str"})
reg.register_record("RichTicket", {"id": "str", "body": "str", "priority": "int"})

# Resolve a generic over the record.
td = reg.resolve("list[Ticket]")
print(td.kind.value, td.name, td.item)

# Width subtyping: a record with EXTRA fields satisfies one needing fewer.
print(reg.is_compatible("RichTicket", "Ticket"))   # extra field -> ok
print(reg.is_compatible("Ticket", "RichTicket"))   # missing field -> no

# Lists ride the same rule, covariantly.
print(reg.is_compatible("list[RichTicket]", "list[Ticket]"))

# explain() gives a reason only on failure.
print(reg.explain("RichTicket", "Ticket"))
print(reg.explain("Ticket", "RichTicket"))

# Optional widening: a plain str feeds Optional[str], but not the reverse.
print(reg.is_compatible("str", "str?"))
print(reg.is_compatible("str?", "str"))

# json_schema round-trips a record for the console (no Python needed).
print(json.dumps(reg.json_schema("Ticket"), sort_keys=True))

# is_registered: a registered record vs an unregistered (but resolvable) name.
print(reg.is_registered("Ticket"), reg.is_registered("PR"))

# The process-wide singleton is a TypeRegistry.
print(type(default_registry).__name__)
```

??? success "▶ Output"

    ```text
    list list[Ticket] Ticket
    True
    False
    True
    None
    type 'Ticket' is not structurally compatible with 'RichTicket'
    True
    False
    {"properties": {"body": {"type": "string"}, "id": {"type": "string"}}, "required": ["id", "body"], "type": "object"}
    True False
    TypeRegistry
    ```

## API reference

### `TypeKind`

`class TypeKind(str, Enum)` — the four shapes a resolved type can take.

| Member | Value | Meaning |
| --- | --- | --- |
| `TypeKind.PRIMITIVE` | `"primitive"` | An atom (`str`, `int`, …) or a nominal name, matched by name. |
| `TypeKind.RECORD` | `"record"` | A named bundle of fields; uses width subtyping. |
| `TypeKind.LIST` | `"list"` | A homogeneous sequence; covariant in its item. |
| `TypeKind.OPTIONAL` | `"optional"` | A possibly-absent value. |

### `TypeDef`

`class TypeDef(BaseModel)` — a resolved type. Built by the registry, not authored directly.
`frozen=True`, so an instance rejects mutation.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `name` | `str` | — (required) | Canonical name, e.g. `"str"`, `"PR"`, `"list[PR]"`. |
| `kind` | `TypeKind` | — (required) | Which of the four shapes this is. |
| `fields` | `dict[str, str]` | `{}` | Records only: field name → type name. |
| `item` | `str \| None` | `None` | List/optional only: the element type name. |

### `TypeRegistry`

`class TypeRegistry` — holds named types and answers structural compatibility. A fresh registry
starts with the six built-in primitives (`str`, `int`, `float`, `bool`, `null`, `json`) and no
records.

```python
def register_primitive(self, name: str) -> None
```

Add `name` to the known-primitive set. (Unknown names already resolve nominally, so this is
mainly for `is_registered` bookkeeping.)

```python
def register_record(self, name: str, fields: dict[str, str]) -> TypeDef
```

Register a record type. `fields` maps each field name to its type name. Returns the built
`TypeDef`. This is what unlocks width subtyping for `name`.

```python
def is_registered(self, name: str) -> bool
```

`True` if `name` is a registered record or a known primitive. Note a name can still *resolve*
(nominally) while being unregistered.

```python
def resolve(self, type_str: str) -> TypeDef
```

Parse a type string into a `TypeDef`, recursing into generics. Handles `X?`, `Optional[X]`,
`list[X]`, registered records, and nominal-primitive fallthrough.

```python
def is_compatible(self, producer: str, consumer: str) -> bool
```

`True` if a value of `producer` type can flow into a `consumer` port. Directional
(producer → consumer); applies the optional/list/record/primitive rules above.

```python
def explain(self, producer: str, consumer: str) -> str | None
```

`None` if compatible, else a structural reason string of the form
`type '<producer>' is not structurally compatible with '<consumer>'`.

```python
def json_schema(self, type_str: str) -> dict[str, object]
```

Emit a JSON-Schema fragment for the resolved type — primitives, `array`, `anyOf … null`, or
`object` with `properties` + `required`.

### `default_registry`

`default_registry: TypeRegistry` — the single process-wide registry instance created at import
time. Plugins register types into it via the `crawfish.types` entry-point group; it is the
fallback registry for [`parameters_compatible`](core-types.md#parameters_compatible).

## See also

- [Core types](core-types.md) — where `Parameter.type` strings come from and how wiring uses them.
- [Output & wiring](output-and-wiring.md) — connecting one node's output to the next.
