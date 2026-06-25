# Core types

The types every other piece of Crawfish is built on: how data is typed, what counts as a
node, and how rule bundles travel. They live in `crawfish.core` and stay thin. Nothing here
knows about a specific node, runtime, or backend.

`Flow` · `Parameter` · `NodeKind` · `Node` · `PolicyKind` · `Policy` ·
`parameters_compatible` · `new_id` · `JSONValue`

## Pipelines, nodes, and parameters

A pipeline is a chain of steps: a source pulls in data, a batch fans it out to an agent,
an aggregator reduces the results, and so on. Each step is a **node**. Nodes wire together
by matching what one node emits to what the next one accepts.

A **parameter** describes one slot of data crossing that boundary: its `name`, its `type`
(a string like `"str"` or `"list[PR]"`), and whether it is required. Two parameters connect
when the producer's type fits the consumer's. That check is `parameters_compatible`.

## Static vs fluid

Every parameter has a **flow** that says where its value comes from:

- **Static**: set once at the start of a batch, the same for every item (a repo link, a
  target board).
- **Fluid**: changes per item as data streams through (a ticket body, a PR diff).

Flow is more than a label. It is the line between trusted configuration and untrusted input.

!!! warning "Fluid data is untrusted"

    Fluid values are the prompt-injection boundary. They reach the model as data to *read*,
    never as instructions to *obey*. The [security model](../architecture/SECURITY.md)
    enforces this. For the same reason, consequential sink targets and idempotency keys must
    be static. Rule of thumb: if a value came from outside your control, it is fluid. A new
    `Parameter` is fluid unless you say otherwise.

## Policies

A **policy** is a named, importable bundle of rules. There are three kinds: spend caps and
content limits (*guardrails*), which model runs when (*routing*), and what an agent may
touch (*permissions*). A policy is data you attach to a pipeline, not code.

## How `parameters_compatible` decides

A value flows producer → consumer, so the check is directional:

```text
parameters_compatible(out, in_)  ==  registry.is_compatible(out.type, in_.type)
```

It resolves both type strings through the [type registry](type-system.md) (the process-wide
[`default_registry`](type-system.md#default_registry) unless you pass your own) and asks
whether a value of the output type can satisfy the input type. It answers only the type
question. Whether a *required* input actually got filled is checked later, where bindings
are applied.

!!! note "Good to know"

    `Parameter.type` is a **string**, not a Python type object, so the desktop console and
    the unit registry can read a node's ports without importing Python. The string resolves
    against the structural [type system](type-system.md), never by plain string equality, so
    `"list[PR]"` and a record with the right fields compare by shape, not by name.

## Why `Node` is an ABC

`Node` is an abstract base class because nodes carry **behaviour**, not just data.
`Parameter` and `Policy`, by contrast, are Pydantic models holding pure data. That split is
a project-wide convention: Pydantic for data shapes, ABCs for behavioural nodes. Concrete
nodes set their `id`, `name`, and `kind` in `__init__`. The allowed kinds are fixed by
`NodeKind`.

The three enums here (`Flow`, `NodeKind`, `PolicyKind`) all subclass `(str, Enum)`, so the
member's value *is* the string (`Flow.FLUID == "fluid"`). Pydantic can coerce raw strings
into members at the boundary and serialise them back without ceremony.

## Example

Wire two ports, build a guardrail policy, and read a fluid default. All pure, no runtime
needed.

```python
from crawfish import Parameter, Flow, parameters_compatible, Policy, PolicyKind, new_id

# An output that emits a list of PRs, and an input that wants them.
pr_list   = Parameter(name="prs",   type="list[PR]", flow=Flow.FLUID)
wants_prs = Parameter(name="items", type="list[PR]", required=True)
print(parameters_compatible(pr_list, wants_prs))   # structurally compatible

# A bare string cannot satisfy an input that wants a list.
text = Parameter(name="body", type="str")
print(parameters_compatible(text, wants_prs))

# A policy is just named, typed data you attach to a pipeline.
cap = Policy(name="spend-cap", kind=PolicyKind.GUARDRAIL, rules={"max_usd": 5})
print(cap.kind.value, cap.rules["max_usd"])

# Parameters default to fluid (untrusted); ids are opaque UUID4 strings.
print(Parameter(name="x", type="str").flow.value)
print(len(new_id()))
```

??? success "▶ Output"

    ```text
    True
    False
    guardrail 5
    fluid
    36
    ```

## API reference

### `Flow`

`class Flow(str, Enum)`: whether a parameter is set once per batch or varies per item.

| Member | Value | Meaning |
| --- | --- | --- |
| `Flow.STATIC` | `"static"` | Set once at batch start (e.g. a repo link). |
| `Flow.FLUID` | `"fluid"` | Changes per item as data streams (e.g. a ticket body). **The prompt-injection boundary.** Reaches the model as data, never instructions. |

### `Parameter`

`class Parameter(BaseModel)`: a typed parameter on an input/output boundary.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `name` | `str` | (required) | Port name. |
| `type` | `str` | (required) | Type name resolved via the [type registry](type-system.md), e.g. `"str"`, `"list[PR]"`. |
| `required` | `bool` | `True` | A required input must be filled with a compatible value. |
| `default` | `JSONValue \| None` | `None` | Value used when an optional input is unfilled. |
| `flow` | `Flow` | `Flow.FLUID` | Static vs fluid. **Defaults to fluid**, untrusted unless declared static. |

### `NodeKind`

`class NodeKind(str, Enum)`: the fixed set of node roles:
`SOURCE`, `BATCH`, `SINK`, `FILTER`, `AGGREGATOR`, `ROUTER` (values are the lowercase names).

### `Node`

`class Node(ABC)`: the abstract base anything in a pipeline implements. Attributes set
by concrete subclasses: `id: str`, `name: str`, `kind: NodeKind`. Carries behaviour, so
it is an ABC rather than a model.

### `PolicyKind`

`class PolicyKind(str, Enum)`:

| Member | Value | Governs |
| --- | --- | --- |
| `PolicyKind.GUARDRAIL` | `"guardrail"` | What an agent may do: spend caps, content. |
| `PolicyKind.ROUTING` | `"routing"` | Which model runs under which conditions. |
| `PolicyKind.PERMISSION` | `"permission"` | Which sources/sinks/data an agent may touch. |

### `Policy`

`class Policy(BaseModel)`: an importable rule bundle.

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `name` | `str` | (required) | Policy name. |
| `kind` | `PolicyKind` | (required) | Which class of rule this bundles. |
| `rules` | `dict[str, JSONValue]` | `{}` | The rule payload; shape depends on `kind`. |

### `parameters_compatible`

```python
def parameters_compatible(
    out: Parameter,
    in_: Parameter,
    registry: TypeRegistry | None = None,
) -> bool
```

`True` if a value produced at `out` can wire into the input `in_`. Checks `out.type`
against `in_.type` structurally, in the producer → consumer direction, through
`registry` (defaults to `default_registry`).

### `new_id`

`def new_id() -> str`: a fresh opaque identifier (a UUID4 string, 36 chars) for any
framework object.

### `JSONValue`

`JSONValue = Any`: the type alias for a JSON-serialisable value. Kept as `Any` because
Pydantic validates concrete shapes at the boundaries (`Parameter.type` carries the real
type information).

## See also

- [Type system](type-system.md): how those `type` strings resolve and compare by shape.
- [Output & wiring](output-and-wiring.md): connecting one node's output to the next.
- [Definition](definition.md): authoring the agents and teams that fill these nodes.
