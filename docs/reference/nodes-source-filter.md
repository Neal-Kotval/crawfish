# Nodes: source and filter

A *source* pulls outside data in. A *filter* narrows that stream back down
before the expensive work begins. Together they are the front of a pipeline: the
ingress and the trim. Both live in `crawfish.nodes` and produce typed
[`Output`](nodes-aggregator.md) values that flow to the next node.

`Source` · `RepoSource` · `PullRequestSource` · `fan_out` · `Filter` ·
`title_contains` · `field_equals` · `field_matches` · `limit`

## Sources, runs, and fan-out

A pipeline is a chain of nodes, and the first node is always a *source*. It fetches
data from the outside world (a repo, a list of pull requests) and hands the rest of
the pipeline a typed [`Output`](nodes-aggregator.md): a value plus a record of the ports
it fills and where it came from.

Sources come in two shapes:

- A *single* source emits one Output that seeds one *run* (one pass of the
  pipeline over one item).
- A *multi* source emits an Output whose value is a list. That list is split into
  one Output per item, so each item gets its own independent run. That split, spreading
  one list into many parallel runs, is *fan-out*, performed by `fan_out`.

`RepoSource` is single (one repo). `PullRequestSource` is multi (a list of PRs).

The model runs once per run. A single source maps cleanly: one Output, one run. A
multi source returns one Output whose value is a list of N items, not yet N runs.
`fan_out` is the explode step that turns one list Output into N per-item
Outputs, each seeding its own run.

!!! note "Good to know"

    `fan_out` is conservative. If `multi` is `False`, or the value is not a list, it
    returns the input wrapped in a single-element list `[output]`, unchanged. Only a
    genuine multi-item list is split.

### Fan-out lineage is deterministic

Each fanned item needs a stable *lineage* key, an identity used downstream for
idempotency, so re-running the same input does the same thing once, not twice.
`fan_out` derives it without any randomness:

- If the item is a dict carrying an `"id"` (or, failing that, a `"number"`), that
  value, stringified, is the lineage.
- Otherwise it falls back to `f"{produced_by}#{i}"`, the producer id plus the item's
  index.

The same input therefore yields the same lineage on every re-run. That determinism is
what keeps idempotency keys stable, and why the example output below is reproducible.

### Fanned items are tainted

Every Output produced by `fan_out` is marked `tainted=True`. Per-item data from a multi
source is **fluid**: untrusted session data that crosses the prompt-injection boundary
(see the [security overview](../architecture/SECURITY.md)). It reaches the model as data
to read, never as instructions to obey. Marking it tainted at the fan-out point
propagates that distrust through the rest of the run.

!!! warning "Fluid data is untrusted"

    See [`NodeKind`](core-types.md) for where these nodes sit in the fixed set of roles,
    and `Flow.FLUID` in [core types](core-types.md) for the static-vs-fluid distinction.
    Credentials are held by reference, never by value: a source's `config` stores the
    *name* of the env var that holds the token (for example `"GITHUB_TOKEN"`), not the token
    itself. The real value is looked up only at fetch time, and never written into
    `config`, the Output, or any log.

## Filters narrow a list

A *filter* narrows a list. Hand a `Filter` an Output whose value is a list, and it
keeps only the items that pass a *predicate*, a one-item yes/no test, emitting a
fresh Output with the survivors in their original order. It never edits its input: an
Output is *frozen* (immutable), so a filter always derives a new one and the
upstream value stays intact for audit.

`Filter` is a node in its own right, not sugar. It carries its own `id`, `name`, and `kind`
(`NodeKind.FILTER`) like any other node, so it shows up in the pipeline graph instead of
hiding as a lambda. It is a pure, synchronous transform with no side effects, and since
`apply` derives a fresh Output, filters compose freely: the Output of one feeds
straight into the next.

Four helpers build ready-made filters for common dict-item cases. `title_contains`,
`field_equals`, and `field_matches` each build a per-item test. `limit` is the odd one
out: keeping "the first N" means counting, which a per-item test can't do, so it
returns a small internal `Filter` subclass whose `apply` slices `inp.value[:n]` instead
of testing items. Its stored predicate accepts everything, so a caller that inspects the
predicate still sees a valid `Filter`, and the contract holds.

!!! note "Good to know"

    The predicate helpers are defensive about shape. `title_contains` and `field_matches`
    check `isinstance(..., str)` before doing string work; all three use `item.get(field)`
    so a missing key is a non-match, not an error. A filter applied to ragged dicts narrows
    safely rather than raising.

## Example

A small in-memory batch of PR-like dicts, narrowed by a `field_equals` filter and then
a `limit`. Pure helpers, no source and no network.

```python
from crawfish.nodes.filter import field_equals, limit
from crawfish.output import Output
from crawfish.core.types import Parameter

# A small in-memory batch of PR-like dict items (no source, no network).
items = [
    {"number": 1, "title": "Fix login bug", "state": "open"},
    {"number": 2, "title": "Bump deps", "state": "closed"},
    {"number": 3, "title": "Add dark mode", "state": "open"},
    {"number": 4, "title": "Refactor cache", "state": "open"},
]
batch = Output(
    output_schema=[Parameter(name="number", type="int"), Parameter(name="title", type="str")],
    value=items,
    produced_by="src",
)

# Build two pure Filters: keep only open PRs, then cap at 2.
open_only = field_equals("state", "open")
first_two = limit(2)

# Filters are first-class Nodes: each carries an id/name/kind.
print(open_only.kind.value, open_only.name)
print(first_two.kind.value, first_two.name)

# Apply in sequence. Each derives a FRESH Output; the input is never mutated.
step1 = open_only.apply(batch)
step2 = first_two.apply(step1)

print(len(batch.value), "->", len(step1.value), "->", len(step2.value))
for pr in step2.value:
    print(pr["number"], pr["title"])

# The original batch is untouched (frozen Output, audit-safe).
print("input intact:", len(batch.value))
```

??? success "▶ Output"

    ```text
    filter field_equals
    filter limit
    4 -> 3 -> 2
    1 Fix login bug
    3 Add dark mode
    input intact: 4
    ```

## API reference

### `Source`

`class Source(Node, ABC, Generic[T])`: abstract pipeline ingress that fetches data
and emits a typed `Output`.

| Member | Type | Default | Notes |
| --- | --- | --- | --- |
| `outputs` | `list[Parameter]` | `[]` | Declared per-item port shape; subclasses override. |
| `multi` | `bool` | `False` | `True` when `fetch` returns a list Output to fan out. |

```python
def __init__(self, name: str, config: dict[str, JSONValue] | None = None) -> None
```

Sets `id` (a fresh [`new_id()`](core-types.md)), `name`, `kind = NodeKind.SOURCE`, and
copies `config` into `self.config` (empty dict if `None`).

```python
@abstractmethod
async def fetch(self, ctx: RunContext) -> Output[T]
```

Abstract. Subclasses fetch data and return an Output matching `outputs`.

```python
def fan_out(self, output: Output[T]) -> list[Output[JSONValue]]
```

Convenience method: calls the module-level `fan_out` with this source's `multi` flag
and `outputs` as the per-item schema.

### `fan_out`

```python
def fan_out(
    output: Output[JSONValue],
    *,
    multi: bool,
    item_schema: list[Parameter] | None = None,
) -> list[Output[JSONValue]]
```

Splits a multi-item Output into one Output per item. Returns `[output]` unchanged when
`multi` is `False` or `output.value` is not a list. Otherwise each item becomes its own
Output with `value` set to the item, `produced_by` preserved, `output_schema` set to
`item_schema` (or the input's schema if `item_schema is None`), `tainted=True`, and a
deterministic `lineage` (the item's `"id"`/`"number"`, else `f"{produced_by}#{i}"`).

### `RepoSource`

`class RepoSource(Source[dict[str, JSONValue]])`: single source describing one
repository. Deterministic and network-free. `multi = False`.

`outputs`: one `Parameter(name="repo", type="str", flow=Flow.STATIC)`.

`config` keys: `repo` (the static repo identifier, e.g. `"owner/name"`) and `auth` (a
secret *reference*, the env-var name holding the token). `fetch` returns
`Output(value={"repo": repo}, ...)` where `repo` is `config.get("repo", "")`.

### `PullRequestSource`

`class PullRequestSource(Source[list[dict[str, JSONValue]]])`: multi source emitting a
list of pull requests. Deterministic and network-free. `multi = True`.

`outputs`: `Parameter(name="number", type="int")` and `Parameter(name="title",
type="str")`.

`config` keys: `repo` (static repo identifier), `items` (a fixture list of PR dicts),
and `auth` (optional secret reference). `fetch` returns the list from
`config.get("items", [])`, coerced to `[]` if it is not a list.

### `Filter`

`class Filter(Node, Generic[T])`: a pure, synchronous node that narrows a list Output
by a predicate.

```python
def __init__(self, predicate: Callable[[T], bool], name: str = "filter") -> None
```

Sets `id`, `name`, `kind = NodeKind.FILTER`, and stores `predicate`.

```python
def apply(self, inp: Output[list[T]]) -> Output[list[T]]
```

Returns a freshly derived Output keeping, in original order, only items for which
`predicate(item)` is truthy. The input Output is never mutated.

### `title_contains`

```python
def title_contains(needle: str, name: str = "title_contains") -> Filter[JSONValue]
```

Returns a `Filter` keeping dict items whose `"title"` field is a `str` containing
`needle` (case-sensitive substring).

### `field_equals`

```python
def field_equals(field: str, value: JSONValue, name: str = "field_equals") -> Filter[JSONValue]
```

Returns a `Filter` keeping dict items where `item.get(field) == value`.

### `field_matches`

```python
def field_matches(field: str, pattern: str, name: str = "field_matches") -> Filter[JSONValue]
```

Returns a `Filter` keeping dict items whose `field` is a `str` that `pattern` matches
via `re.search` (the pattern is compiled once). A non-string or missing field is a
non-match.

### `limit`

```python
def limit(n: int, name: str = "limit") -> Filter[JSONValue]
```

Returns a `Filter` (an internal `_Limit` subclass) whose `apply` keeps at most the
first `n` items: a list slice, not a per-item test.

## See also

- [Nodes: aggregator](nodes-aggregator.md): fold the per-item runs back into one.
- [Nodes: router and sink](nodes-router-sink.md): branch the stream, then write the result out.
- [Core types](core-types.md): `NodeKind`, `Parameter`, and the `Flow.FLUID` boundary.
