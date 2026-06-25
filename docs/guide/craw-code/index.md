# craw code: author and operate a Crawfish project

`craw code` is the surface where an LLM authors and operates a Crawfish project for you. You
describe the agent team you want; the model scaffolds components, wires them, prices a run,
deploys it, and watches it — and every step it takes runs through the same `craw` CLI you
would run by hand. The CLI is the one execution path. The Claude Code plugin is ergonomics on
top of it, and the dashboard is a scrubbed read-model beside it. Nothing the agent does
escapes the CLI's gates.

!!! note "You will learn:"
    - What `craw code` is, and how its three pieces (CLI, plugin, dashboard) relate
    - The trust-collapse thesis — why agent-authored code needs new, *enforced* controls
    - A runnable quickstart: `init` → `new` → `describe` → `estimate` → `sync` → `dashboard`

## The three pieces

`craw code` is one verb family with three faces, and they are deliberately not equals:

| Piece | What it is | Why it exists |
| --- | --- | --- |
| **The CLI** (`craw code …`) | The single execution path. Every action — scaffold, reflect, price, run, deploy, approve — is a `craw code` verb that reads the project at invocation and emits a versioned `--json` envelope. | One auditable surface. The agent uses Bash and nothing else; the transcript records every call. |
| **The plugin** | A Claude Code plugin installed under `.claude/plugins/crawfish/`, carrying the authoring skills and meta-tools. | Ergonomics. It teaches the agent *how* to drive the CLI well; it never becomes a second way to run things. |
| **The dashboard** | A loopback web read-model over the `.crawfish/` ledger. | A human-readable view of runs and cost, scrubbed and org-scoped. It reads; it does not act. |

The CLI being the only execution path is the load-bearing decision (see
[the CLI page](cli.md)). It means the integration surface is always fresh, always one tool,
and always in the transcript — there is no hidden RPC an injected agent could use to slip
past a gate.

## The trust-collapse thesis

Crawfish's [security spine](../../architecture/SECURITY.md) was written for a world where a
**human** authored `definition.py`, `tools/*.py`, and `policies/*.py`. Compiling a project
imports that code in-process, as authoring-time-trusted, because a person stood behind it.

`craw code` puts an **LLM** in the author's chair — and that LLM may have read untrusted
(`Flow.FLUID`) data, a poisoned ticket or a malicious RAG hit, that is now steering what it
writes. The human author the trust assumption depended on is gone. So the spine can no longer
be a set of guidelines the author is expected to follow; **it must be enforced by
construction**, because a guideline is something an injected agent can be talked out of.

!!! warning "Trust boundary"
    Code authored by the agent is provenance-stamped ([CRA-266](../../reference/craw-code-provenance.md))
    and jailed at compile ([ADR 0010](../../architecture/decisions/0010-jailed-compile-agent-authored-code.md)).
    A consequential sink target or idempotency key derived from `Flow.FLUID` data is rejected
    by construction — it is never merely discouraged. See the [security model](security.md).

Almost every control is an existing seam wired into the new authoring path — the jail, the
scrubbing store, the consent gate, the secret broker — never a second, weaker execution path.

## Quickstart

Everything below runs on the mock runtime. There is no key to set and nothing to spend.

Scaffold a project and start its ledger:

```bash
craw code init triage-app --name triage-app --no-plugin
# scaffolds sources/ sinks/ definitions/ … + crawfish.toml, starts .crawfish/
cd triage-app
```

Author a component from a template:

```bash
craw code new definition triage
# writes definitions/triage/definition.py + instructions.md, then secret-shape lints it
```

Reflect its typed inputs and outputs — this compiles the component (jailed, if the agent
authored it) and projects only the typed shape, never live objects:

```bash
craw code describe definitions/triage --json
```

```json
{
  "schema": "craw.code.describe.v1",
  "component": "definitions/triage",
  "authored_by": "craw-code",
  "tainted": false,
  "inputs": [
    {"name": "project", "flow": "static", "type": "str"},
    {"name": "ticket_body", "flow": "fluid", "type": "str"}
  ],
  "outputs": [{"name": "triage", "flow": "static", "type": "Triage"}]
}
```

Price a run over five items — no model is called; the number is an honest band:

```bash
craw code estimate definitions/triage --items 5 --json
```

```json
{
  "schema": "craw.code.estimate.v1",
  "items": 5,
  "total_usd": 4.5,
  "expected_usd": 4.5,
  "worst_case_usd": 4.5,
  "within_budget": true
}
```

Reconcile the tree and run the assembly gate as a precondition:

```bash
craw code sync
# reconciles discovery + doctor, then asserts no fluid value reaches a static sink
```

Open the dashboard to watch runs and cost on loopback:

```bash
craw code dashboard --open
# binds 127.0.0.1 only; reads the .crawfish/ ledger through a scrubbing store
```

That is the whole loop in miniature: author, reflect, price, reconcile, observe. From here,
the [operate page](operate.md) covers running and optimizing, and
[review and approve](review-and-approve.md) covers the human gate that stands between a
proposal and a live promotion.

## See also

- [Author a project with craw code](authoring.md) — the file-by-file authoring flow
- [The craw code CLI](cli.md) — every verb, its flags, `--json` schema, and exit codes
- [Security model](security.md) — the trust-boundary collapse in depth
- [RFC 0001: craw code](../../rfcs/0001-craw-code.md) — the design rationale
