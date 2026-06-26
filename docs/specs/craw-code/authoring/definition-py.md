# `definition.py` — typed IO + team shape

> Feeds `crawfish-authoring-definition-py` (CRA-258). Golden:
> [`demo/craw-code-golden/definition.py`](../../../../demo/craw-code-golden/definition.py).

`definition.py` declares the Definition's **typed boundary** — its `inputs` and `outputs` as
`Parameter`s — and the **team shape** (`lead` / `coordination`). It is the spine's primary
surface: this is where you decide what is trusted config and what is untrusted data.

## inputs / outputs are `Parameter`s, each static or fluid

```python
from __future__ import annotations
from crawfish.core import Flow, Parameter

inputs = [
    Parameter(name="project", type="str", flow=Flow.STATIC),   # set once at batch start
    Parameter(name="ticket_body", type="str"),                 # default → FLUID (per-item)
]
outputs = [Parameter(name="triage", type="Triage", flow=Flow.STATIC)]
lead = "lead"
```

- **`Flow.STATIC`** is the deliberate, consequential choice: author config that is set once
  at batch start — a project id, a sink destination, an idempotency input.
- **Fluid is the default.** Omit `flow` and a `Parameter` is `Flow.FLUID`: untrusted,
  per-item session data. **A Flow.FLUID value reaches the model as data, never as
  instructions**, and never derives a consequential setting.

## The consequential output is static-only

A consequential **output** parameter is declared `Flow.STATIC`. **Consequential sink
targets, idempotency keys, and consequential outputs are static-only**; the assembly gate
(ALG-3, `assert_build_safe`) treats a `Flow.FLUID` output as a suspected fluid-fed target slot
and **fails closed**. In the golden, `triage` is the team's structured decision written into a
static slot, so it is `Flow.STATIC` and the build gate discharges it — exactly the
correction the scaffolded hero example applies. (Free-text *content* an agent merely returns,
with no consequential destination, may stay fluid; a value bound for an egress slot may not.)

The rule, restated: **never derive a static slot from a fluid value.** A `with_*` composition
op (`with_inputs`, `with_policy`, `with_context`) never widens fluidity — it carries each
`Parameter`'s flow through unchanged.

## Team shape

`lead = "lead"` names the coordinator role; with more than one agent the compiler infers
`Coordination.LEAD`. Set `coordination` explicitly (`single` / `lead` / `sequential`) to
override. The `lead` and every `delegates_to` target must be a real team role — an unknown
role fails at load with `DefinitionLoadError`.
