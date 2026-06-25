# Authoring a Crawfish Definition — file by file (CRA-256)

This is the **source of truth** for authoring a Crawfish Definition directory. The plugin
authoring skills (`crawfish-authoring/*`, CRA-258..264) are *derived from* the sections
here, and the validation eval (CRA-265, `craw code validate-authoring`) checks an authored
Definition against the assertions each section states. Teaching and checking both read this
one document, so they never drift.

A Definition is a **directory** the compiler (`crawfish.definition.compiler.load_definition`)
turns into one typed object. Under `craw code` the *author may be the agent*, so every
import-bearing file is compiled through the **jailed** path
(`crawfish.definition.jailed.load_definition_jailed`, CRA-267): folder-scoped, network-denied,
fail-closed, with taint propagated onto each file's provenance row.

## The security spine, restated for authoring

Every section below that can touch a sink, a secret, or a fluid value repeats the relevant
rule inline. The whole spine in one place
([`docs/architecture/SECURITY.md`](../../../architecture/SECURITY.md)):

- **Fluid is untrusted data, never instructions.** A `Flow.FLUID` value (a ticket body, a
  diff, anything per-item) reaches the model as *data*; it is never concatenated into an
  instruction and never derives a consequential setting (rule 1).
- **Consequential sink targets & idempotency keys are static-only.** A destination — and the
  idempotency key — comes from `Flow.STATIC` config, never from a fluid or model-derived
  value (rules 2, 3). A consequential *output* parameter is therefore declared
  `Flow.STATIC`; declaring it `Flow.FLUID` fails the assembly gate (ALG-3) closed.
- **Secrets resolve by reference.** A credential is an env-var *name* (`auth="GITHUB_TOKEN"`),
  never an inline value, never in a prompt or `config`, never logged (rule 4).
- **Host-side code is tainted from fluid inputs.** A value derived from a fluid input stays
  tainted and can never silently become a static sink target or idempotency key (rule 5).
- **The supply chain is pinned.** Agent-added capabilities (a new MCP, a new dependency)
  re-enter the consent gate (`craw code grant`, CRA-277); the plugin bundle is pinned
  (rule 6).

## The file map

One section per Definition file kind. Each names the skill it feeds and the eval assertions
it backs. The machine-checkable form of these rules lives in
[`authoring-spec.toml`](authoring-spec.toml) (loaded by `test_authoring_spec.py` and the
validation eval).

| File / dir            | Section                                  | Skill (CRA)                          |
|-----------------------|------------------------------------------|--------------------------------------|
| `definition.py`       | [definition-py](definition-py.md)        | `crawfish-authoring-definition-py` (258)   |
| `instructions.md`, `agents/*.md` | [instructions-agents](instructions-agents.md) | `crawfish-authoring-instructions-agents` (259) |
| `tools/*.py`          | [tools-py](tools-py.md)                  | `crawfish-authoring-tools-py` (260)        |
| `mcp/*.py`            | [mcp-py](mcp-py.md)                      | `crawfish-authoring-mcp-py` (261)          |
| `policies/*.py`, `skills/*.md` | [policies-skills](policies-skills.md) | `crawfish-authoring-policies-skills` (262) |
| knowledge (`with_context`/`Wiki`) | [knowledge](knowledge.md)    | `crawfish-authoring-knowledge` (263)       |
| `fixtures/`, evals    | [fixtures-evals](fixtures-evals.md)      | `crawfish-authoring-fixtures-evals` (264)  |

The complete, gate-clean worked example every section points at is the golden project under
[`demo/craw-code-golden/`](../../../../demo/craw-code-golden) (CRA-257). It exercises every
file kind, `load_definition_jailed`s clean, passes the assembly gate (its consequential
`triage` output is `Flow.STATIC`), and runs green under the mock.

## How a directory becomes a Definition (the compile contract)

| You author                    | The compiler produces                              |
|-------------------------------|----------------------------------------------------|
| `instructions.md` (+ `agents/*.md`) | `TeamSpec.agents` (role = front-matter `role` or filename stem) |
| `tools/*.py`                  | a tool named after the **filename stem** (must be a callable) |
| `mcp/*.py`                    | `DefinitionAssets.mcp` (module-level `MCPConnection` instances) |
| `policies/*.py`               | `DefinitionAssets.policies` (module-level `Policy` instances) |
| `skills/*.md`                 | `DefinitionAssets.skills`                          |
| `definition.py`               | typed `inputs`/`outputs`, `dependencies`, `lead`/`coordination` |
| `pyproject.toml`              | the Definition `id` (name) and `version`           |

A broken binding — an agent referencing an unknown tool, policy, or `delegates_to` role —
**fails at load time** with `DefinitionLoadError`. Author so the directory loads clean.
