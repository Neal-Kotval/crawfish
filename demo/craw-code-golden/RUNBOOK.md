# craw-code-golden — the reference Definition (CRA-257)

The complete, gate-clean worked example authored exactly to the file-by-file authoring
playbook ([`docs/specs/craw-code/authoring/`](../../docs/specs/craw-code/authoring/README.md)).
Every section of the spec points here; the validation eval (CRA-265) loads it as the canonical
positive fixture, and the Wave-6 demo reuses it.

## What it exercises (every Definition file kind)

| File / dir                | Demonstrates                                                |
|---------------------------|-------------------------------------------------------------|
| `definition.py`           | typed IO — STATIC `project`, FLUID `ticket_body`, STATIC consequential `triage` record output |
| `instructions.md`         | the lead prompt; `delegates_to`, a tool binding; fluid-as-data |
| `agents/classifier.md`    | a subagent binding a `policy`                               |
| `agents/summarizer.md`    | a single-purpose subagent                                  |
| `tools/normalize_ticket.py` | a callable whose name == filename stem; taint-aware       |
| `mcp/github.py`           | an `MCPConnection`, `auth` by reference, a `tools` allowlist |
| `policies/spend_guard.py` | a module-level `Policy` (static consequential config)       |
| `skills/triage-rubric.md` | a bundled skill                                            |
| `knowledge.py`            | `Wiki` + `with_context` — tainted, pinned-by-hash knowledge |
| `fixtures/*.json`         | `{"inputs": {...}}` test inputs for `craw test`             |

## It is build-gate clean

The consequential `triage` output is declared `Flow.STATIC`, so the assembly gate
(`assert_build_safe` → ALG-3) discharges it: no FLUID value can reach a static-only sink slot.

```bash
craw code describe demo/craw-code-golden            # typed-IO + capability-kind projection
craw code sync --dir demo/craw-code-golden          # reconcile + assembly-gate precondition
craw test demo/craw-code-golden --fixtures fixtures # mock-by-default, deterministic
```

`craw code describe` surfaces capability **kinds** only (`has_mcp_connection`,
`declares_secret_ref`) — never the env-var name, egress host, or sink target.

## Security shape (the spine, embodied)

- Fluid `ticket_body` is untrusted data the prompts analyze, never an instruction surface.
- The consequential output and the MCP auth reference are static / by-reference.
- Agent-authored import-bearing files (`definition.py`, `tools/`, `mcp/`, `policies/`) compile
  through the jail (CRA-267), fail-closed, with taint on each provenance row.
- Adding `mcp/github.py` is a new capability and re-enters the consent gate (`craw code grant`).
