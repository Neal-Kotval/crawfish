# RFC 0001 — `craw code`

**Status:** Implemented (`craw-code/integration`) · **Author:** Neal · **Date:** 2026-06-24
**Affects:** developer experience, Claude Code integration, the `craw` CLI surface, the event ledger / dashboard

---

## 1. Problem

Crawfish is a capable framework — `Source → Filter → Batch → Aggregator → Router →
Sink`, authored as a directory of files and run locally. Phase 1 (the local trust loop)
shipped. But two things keep it from being *used*:

1. **It's hard to drive.** The CLI is rich (`run`, `dev`, `eval`, `tune`, `refine`,
   `learn`, `guard`, `deploy`, …), but a human has to know the model, the flags, the
   layout, and the security rules to get anything done. The on-ramp is steep.
2. **It's hard to stand up per project.** Every project needs its components authored
   (definitions, pipelines, sources, sinks), wired, and kept healthy. That's a lot of
   bootstrap before the framework earns its keep.

`craw code` closes both gaps by putting an agent in the driver's seat. Claude Code, given
the right knowledge and tools, **authors and evolves a Crawfish project for you** — it
scaffolds the layout, writes components, runs and evaluates them, reads the ledger, and
surfaces the whole fleet of agent activity in a dashboard. The framework becomes
self-generating: Claude builds on it continuously using its context about how Crawfish
works.

## 2. Scope and non-goals

In scope: the integration layer that lets Claude Code drive and extend a Crawfish project,
the knowledge it needs, and the visualization surface for watching many runs.

**Non-goals.** `craw code` does **not** reimplement the engine, the optimization plane, the
tameness layer, or the Store. Those exist. It does not fork the runtime model. It does not
introduce a second execution path — it drives the one that already ships.

## 3. Two decisions, settled

### 3.1 Plugin (+ dashboard), not a fork

The pull toward forking Claude Code is visualization — "herding lots of agent activity."
But that need is **monitoring** (run status, fan-out progress, cost burn, eval pass
rates), which is orthogonal to the terminal agent loop. We don't need to own the loop to
render a fleet view, and we already have the data source: the **event ledger** under
`.crawfish/`.

| Option | Verdict | Why |
| --- | --- | --- |
| Fork Claude Code | **No** | Buys UI control at the cost of perpetually rebasing on a fast-moving upstream — for a dashboard we can build *beside* it. |
| Claude Code **plugin** | **Yes** | Ships the MCP/skills/commands that give Claude the knowledge and tools. Rides the upstream update train. |
| Standalone **dashboard** | **Yes** | `craw dashboard` already exists; it tails the ledger. This is the herding surface, decoupled from Claude Code internals. |

**Decision: plugin + standalone dashboard.** A fork is a fallback we adopt only once we
have hard evidence the plugin can't express something core — not a starting point.

### 3.2 CLI as the contract, not per-app MCP

How should Claude *operate* a Crawfish project? The repo already answers this. The `craw`
CLI's `--json` output is explicitly **"the integration surface"** — a versioned,
snapshot-tested payload (`craw.<cmd>.v<N>`) built to be parsed by downstream tools. We are
not choosing an interface; we are choosing whether to add a second one.

The deciding factor is that `craw code` is **self-generating**: Claude is *continuously
editing* the project and then calling into it. That regime is hostile to a per-app MCP and
friendly to the CLI.

| | Per-app MCP tools | The `craw` CLI |
| --- | --- | --- |
| **Freshness** | Tool registry goes stale the moment Claude edits a component; needs `listChanged` + mid-session rescans, and still lags the filesystem. | Reads the project at invocation. **Never stale** — author a file, call it on the next line. |
| **Context cost** | Many apps × many functions = dozens of tools cluttering context. | One tool (Bash) regardless of project size. |
| **Trust / reproducibility** | Opaque tool call. | The exact command appears in the transcript — copy-pasteable, auditable. This *is* the local-trust-loop story. |
| **Maintenance** | A second integration surface to keep in lockstep with the CLI. | One execution path. Humans and Claude hit the same code. |
| **Structured I/O** | Native. | Recovered via `--json` (already versioned and snapshot-tested). |

**Decision: CLI-first.** Claude drives Crawfish by invoking `craw … --json` over Bash and
authoring components as files. Authoring is text editing (Read/Write/Edit already excel);
operating is `--json` CLI calls.

**Optional later veneer.** If we want typed entry points, add a *thin* MCP of ~4 **fixed**
meta-tools (`run`, `call`, `eval`, `describe`) that shell out to the CLI — the project
component is an *argument*, not a tool. Fixed arity sidesteps both staleness and bloat.
This is a nice-to-have; the CLI is the spine, and any MCP is a veneer over it. (Consistent
with the architecture rule that the product model imports protocols, never a backend.)

## 4. What `craw code` actually is

A small surface layered on the existing framework:

```text
craw code
├── plugin            # Claude Code plugin: skills + commands + (optional) thin MCP
│   ├── skills/       # the mental model: layout, when to fan-out vs loop, the security spine
│   └── commands/     # /craw-init, /craw-new, /craw-eval … thin wrappers over `craw …`
├── craw code <verb>  # the agent/dev-time CLI namespace (scaffold + orchestrate)
└── dashboard         # fleet view over the event ledger (extends `craw dashboard`)
```

Nothing here re-implements the engine. The plugin is knowledge + ergonomics; the CLI
namespace is scaffolding + orchestration; the dashboard is a reader over the ledger.

### 4.1 Naming: `craw code` vs `craw`

The prefix should **disambiguate**, not decorate. Split by *who acts and when*:

- **`craw code <verb>`** — the **agent / dev-time** surface: `craw code init`,
  `craw code new`, `craw code sync`, `craw code dashboard`. This is the Claude-Code-
  integrated product. `craw code init` does *more* than a bare `craw init`: it scaffolds
  the canonical layout **and** installs the plugin/skill bundle, wires the agent loop, and
  starts the ledger the dashboard reads. The infix is meaningful, not ceremony.
- **`craw <verb>`** — the **runtime** surface a deployed pipeline or power user touches:
  `craw run`, `craw eval`, `craw deploy`. Unchanged.

The trap to avoid is two parallel trees with overlapping verbs (`craw run` *and*
`craw code run`) — that just makes people ask "which one?" One front door per verb:
`craw code` owns scaffolding and the agent loop; `craw` owns execution.

> **Open question (O-1):** is `craw code` the **brand for the whole product** (with `craw`
> as the buried runtime most users never type), or a **co-equal surface**? This drives
> whether `craw code` subsumes everything or stays narrow. Recommendation: brand-umbrella,
> narrow command set — most users only ever type `craw code …`.

### 4.2 A note on `.crawfish/` vs authored components

One alignment point. In the canonical layout, **authored** components live in
`definitions/`, `pipelines/`, `sources/`, `sinks/`, `tools/`, `observers/`, `policies/`.
The **`.crawfish/`** directory is *generated machine state* — locks, the execution ledger,
cassettes, the deploy registry — and must never be hand-edited (`craw doctor` flags
tampering).

So "Claude evolves the project" means **Claude authors into the seven component folders**,
and **`.crawfish/` is the ledger the dashboard reads** — the two never mix. `craw code
init` scaffolds the authored tree; the agent loop writes into it; the ledger fills as runs
execute. Keeping intent and machine-state separate is exactly the existing invariant, and
`craw code` upholds it.

## 5. The self-generating loop

```text
            ┌──────────────────────────────────────────────┐
            │  Claude Code  (knowledge via plugin skills)   │
            └──────────────────────────────────────────────┘
   author │ Read/Write/Edit            operate │ Bash: `craw … --json`
          ▼                                     ▼
   definitions/  pipelines/  sources/  ──▶  craw dev / run / eval / tune / refine
   sinks/  tools/  observers/                       │ records
          ▲                                         ▼
          └────────── reads ledger ◀──────  .crawfish/  (ledger, registry, cassettes)
                                                    │
                                                    ▼
                                        craw code dashboard  (fleet view)
```

Claude authors a component, runs it deterministically (`craw dev`, mock runtime), reads the
`--json` result and the ledger, iterates, then promotes to `--live` under a `--budget`.
Every step is a transcript line the user can see and reproduce.

## 6. CLI surface (`craw code`)

`craw code` adds a thin agent/dev-time namespace. Each verb composes existing `craw`
machinery; none re-implements it. All inherit the existing shared flags (`--json`,
`--seed`, `--budget`, `--org`, `--model`, `--live`).

| Command | Composes | What it does |
| --- | --- | --- |
| `craw code init <dir>` | `craw init` + plugin install | Scaffold the canonical layout, install the plugin/skill bundle, start the ledger, print next steps. |
| `craw code new <kind> <name>` | scaffolding | Author a new component (`definition`, `pipeline`, `source`, `sink`, …) from a template into the right folder. |
| `craw code describe <component>` | compiler reflection | Dump a component's typed inputs/outputs as JSON, so Claude self-serves the param schema **on demand and never stale** (this is the schema MCP would surface, without the registry). |
| `craw code sync` | `craw doctor` + `craw list` | Reconcile authored tree with discovery; report drift; the agent's "where am I" call. |
| `craw code run <component>` | `craw dev` / `craw run` | Run a component (mock by default, `--live` to go real). Thin alias for the agent's common path. |
| `craw code dashboard` | `craw dashboard` | Launch the fleet view over the ledger (see §7). |

`craw code describe` is the load-bearing addition: it recovers the one genuine ergonomic
advantage MCP had (typed schemas surfaced for the model) while staying filesystem-fresh,
because it reflects the component at call time rather than caching a registry.

## 7. Dashboard — the herding surface

The dashboard is a **reader over the event ledger**, served on localhost. It is where the
"lots of agent activity" need is met without a fork.

What it shows, all sourced from `.crawfish/` (ledger + registry):

- **Runs in flight** — per-pipeline, with fan-out (`Batch`) progress: N of M items done.
- **Cost burn vs budget** — actuals against each run's `CostBudget` band
  (`total_usd` / `expected_usd` / `worst_case_usd` — note the lower-bound field in
  `crawfish/cost.py` is `total_usd`, not `lower_usd`).
- **Eval / tune / refine status** — pass rates, per-metric deltas vs baseline, trial logs,
  `winner` shas, `stopped_reason`.
- **Version lineage and rollbacks** — `learn` promotions and pointer-move rollbacks from
  the audit trail.

Because the ledger already records all of this deterministically, the dashboard is a view,
not a new source of truth. It extends `craw dashboard` rather than replacing it.

> **Open question (O-2):** terminal TUI, local web UI, or both? Web is the stronger
> herding surface (multi-run, charts); a TUI keeps everything in one pane. Recommendation:
> local web (`craw code dashboard` opens a browser tab), TUI as a later convenience.

## 8. Knowledge the plugin must teach

The skills bundle is not optional polish — it encodes the rules that keep Claude from
building something unsafe or unidiomatic:

- **The pipeline mental model** — what a Definition/pipeline is, and *when to reach for
  batch fan-out vs an aggregator vs a refine loop*.
- **The security spine — load-bearing.** `Flow.FLUID` inputs are **untrusted session
  data** (the prompt-injection boundary): they reach the model as data, never as
  instructions. Consequential **sink targets and idempotency keys are static-only**.
  Secrets resolve by reference, are never logged or in-prompt. If this isn't *taught*,
  Claude will happily wire a fluid input into a sink target — a prompt-injection vector.
  The plugin must make these rules impossible to miss.
- **Determinism discipline** — mock-by-default, `--seed` carries all randomness, `--live`
  is explicit and budgeted. Claude should iterate on the mock and promote deliberately.
- **Reading the ledger** — how to interpret `craw inspect` / `craw logs` / `--json`
  payloads to decide the next move.

## 9. Build order (dependency-ordered)

0. **M0 — Trust & test foundations.** Authorship provenance + taint, jailed compile of
   agent-authored code, and a deterministic record/replay harness for the authoring loop.
   *Born of the agent-authoring trust collapse (§12); everything else keys on it.*
1. **M1 — CLI legibility.** Stable `--json` + exit codes, `craw code describe` (schema
   reflection), plus the hardening verbs/contracts: schema-version negotiation, the
   `craw.error.v1` envelope, `describe` redaction, assembly-gate-in-`run`, `craw code
   estimate`, org_id threading.
2. **M2 — Scaffolding** (`init`, `new`, `sync`, `map`, `adopt`). One command to a working
   project; secrets-by-reference templates; consent re-entry for agent-added MCP; tree
   locking; idempotent init.
3. **M3 — Plugin skills + commands** (mental model + security spine + determinism). Plus
   plugin pin/integrity and `craw code explain`.
4. **M3a — Authoring playbook.** The file-by-file definition-contents skills (separate
   doc/issues).
5. **M4 — Dashboard** over the ledger — through the `ObserverSurface`/`Store` seam, output
   -encoded against tainted-ledger XSS, org-scoped, with aggregate cost-vs-ceiling.
6. **M4.5 — Operate plane.** `craw code optimize` (tune/refine/learn orchestrator),
   `deploy` + `fleet`, `cancel`/`resume`. The "herd lots of agent activity" half.
7. **M6 — HITL, feedback & debug.** The human approval/promotion gate, `craw code review`
   (ledger→authoring feedback), `craw code diagnose`. Closes the self-generating loop.
8. **M5 — (Optional) thin MCP veneer** — only if typed entry points prove worth a second
   surface after the CLI path is solid.

## 10. Open questions

- **O-1** — `craw code` as brand-umbrella vs co-equal surface (§4.1). **Resolved:
  co-equal surface.** Built as a first-class `craw code <verb>` subcommand family (a new
  `crawfish.code` subpackage with an auto-discovered verb registry), not merely a brand
  umbrella over loose commands.
- **O-2** — dashboard delivery: web vs TUI vs both (§7). **Resolved: web.** The M6/M4.5
  interactive controls (approval queue, cancel/resume) need affordances a TUI handles
  poorly. (Shipped as a loopback-only, scrubbed read-model over `ObserverSurface` — ADR 0011.)
- **O-3** — does the plugin ship the thin MCP from day one, or stay CLI-only? **Resolved:
  CLI/plugin-first, with an opt-in thin MCP veneer (M5).** The veneer is a *fixed* set of
  meta-tools that shell out to `craw code <verb> --json`; it adds no new authority and the
  CLI remains the one execution path. It is not enabled by default.
- **O-4** — relationship to the existing **Claude Code export** path. **Resolved:
  complement, not collision** (recorded as **ADR 0012**). `craw code adopt` subsumes
  `craw export --claude-code` as its plugin-install step; the plugin owns `.claude/`
  *plugin* assets (under a reserved `crawfish-*` prefix) while export owns *per-Definition*
  subagent files — disjoint namespaces, preserving the `.claude`-excluded-from-`sha`
  invariant.

## 11. Definition of done

Consistent with the repo's bar: `ruff` + `mypy` clean, `pytest` green and deterministic
(no live model calls — fixtures / record-replay), the **security spine upheld** (fluid
inputs never reach a sink target via the agent loop), the demo (`demo/triage-bot/`)
exercises `craw code` end to end, and docs updated.

## 12. Hardening — security & architecture gaps

This section folds in a three-lens gap review (security, architecture/build, missing
features). Each gap is tracked as a Linear issue under the `craw code` project where one
could be filed (IDs noted); the rest are recorded here pending filing.

### 12.1 The root cause: the agent-authoring trust collapse

The framework's security model was written for a world where a **human** authored
`definition.py`, `tools/*.py`, and `policies/*.py` — the compiler treats that code as
*authoring-time trusted* and imports it in-process (`docs/reference/definition.md`).
`craw code` puts an **LLM** in the author's chair, and that LLM may be steered by fluid
(untrusted) data it has read. So a boundary the framework assumed is gone. SECURITY.md
already anticipates this (rule on "a Definition or guard the `craw code` loop produced"
must pass the assembly gate, and an un-benchmarked guard cannot gate) — but the plan must
*enforce* it, not merely *teach* it. A skill is a guideline an injected agent can be
talked out of; the mitigations below are enforcement. Crucially, nearly all of them are
**wiring existing seams** (the jail, `ScrubbingStore`, the consent gate, `ObserverSurface`,
`CancelToken`, the secret-broker approval queue, `crawfish.lock`) into the new authoring
path — consistent with the RFC's "drive the one execution path that already ships."

### 12.2 Security gaps

| Gap | Sev | Mitigation (seam reused) | Where |
| --- | --- | --- | --- |
| Authorship provenance + taint — nothing distinguishes human- from agent-written components | Urgent | Per-file provenance rows in `.crawfish/`; fold `authored_by` into content identity; agent-authored-under-fluid-context is `tainted` (taint rules, rule 9) | M0 · **CRA-266** |
| Agent-authored code compiled as trusted = arbitrary code execution in the orchestrator | Urgent | Jailed compile via `run_out_of_process`/`select_jail()`, read-only project dir, `allow_net=False`, taint via `JailResult` | M0 · **CRA-267** |
| `--live` reachable on agent-authored consequential components with no human review of the *content* | Urgent | Promotion/approval gate `craw code promote` reusing the secret-broker approval queue, keyed on `(component, sha)`, fail-closed | M6 · *to file* |
| Dashboard renders tainted ledger text → stored XSS / SSRF beacon on localhost | High | Context-aware output-encode every `tainted` field; strict CSP (`default-src 'none'`); red-team payload in the behavioural gate | M4 · *to file* |
| `craw code describe` leaks secret refs / egress hosts / sink destinations into the agent's context | High | Typed-shape-only projection; route through `ScrubbingStore` redaction; surface capability *kind*, not destination; `craw.code.describe.v1` snapshot-tested | M1 · **CRA-271** |
| Agent-added MCP server / dep bypasses the install-time consent gate | High | Re-enter consent on agent-authored `MCPConnection`/`DefinitionRef`; `Grant` + lockfile pin; `DenyConsent` default | M2 · **CRA-277** |
| Assembly gate (`assert_build_safe`) skipped in the edit→run loop where it matters most | High | Invoke `assert_build_safe` + precision gate as a precondition of `craw code run`/`sync`; red-team test | M1 · **CRA-272** |
| The plugin's own skill/MCP bundle (the source of the security rules) is unpinned | Medium | Pin + content-digest the bundle in `crawfish.lock`; `craw doctor` re-verifies; optional publisher signature | M3 · *to file* |
| Scaffolding templates that model inline secrets/destinations teach the wrong shape | Medium | Reference-only credential slots; static-only destinations; secret-shaped-literal lint; templates fail closed | M2 · **CRA-276** |

### 12.3 Architecture & build gaps

| Gap | Sev | Mitigation | Where |
| --- | --- | --- | --- |
| `--json` schema skew between plugin and independently-upgraded CLI | Urgent | Version negotiation (`schema_major/minor`), structured `schema_skew`, subset check, forward-compatible parsers | M1 · **CRA-269** |
| Plugin not pinned/lockstepped to the framework version it wraps | Urgent | `requires_crawfish` range + integrity hash in `crawfish.lock`; `sync` compat check fails closed | M2/M3 · *to file (see CRA-279 --upgrade)* |
| Dashboard reading `.crawfish/` invites importing a concrete `SqliteStore` (violates "import protocols, not backends") | Urgent | Data exclusively via `ObserverSurface(store, org_id)` + `Store` protocol; aggregations in Python over scrubbed rows; loopback bind (ADR 0008) | M4 · *to file* |
| Half-written Definition compiled mid-edit → wrong content sha, corrupt run identity | High | Advisory lock via the Store borrow primitive; `tree_busy` refusal; `craw doctor` torn-tree check | M2 · **CRA-278** |
| No structured, recoverable error surface for the agent loop | High | `craw.error.v1` envelope (`code`, `retryable`, `remediation`); security rejections `retryable:false` | M1 · **CRA-270** |
| `craw code init` not idempotent/re-entrant — could clobber the ledger | High | Reconcile-not-overwrite; never touch ledger/registry; `--upgrade` repin; `dirty_init` on tamper | M2 · **CRA-279** |
| O-4 export overlap unresolved | Medium | ADR: `adopt` subsumes export; disjoint `.claude/` namespaces (§10) | M3a · *to file* |
| `org_id` not threaded through the new surface or dashboard → cross-tenant leakage | Medium | `--org` on every verb; `ObserverSurface` constructed per-org; two-org isolation test | M1/M4 · **CRA-275** |
| Agent-driven authoring loop is untestable without live calls | Medium | Record/replay harness over recorded tool-call transcripts + `MockRuntime`; golden authoring-session fixture | M0 · **CRA-268** |
| `describe` recompiles per call → unbounded hot-path latency; standalone usability unstated | Medium | Single-component reflection cached by content sha under `.crawfish/`; assert/test standalone-over-Bash | M1 · **CRA-274** |

### 12.4 Missing features (the "operate / self-generating" half)

The original plan over-indexed on **authoring** and **monitoring**; the operate, optimize,
and feedback half of the promise needed its own homes — milestones **M4.5** and **M6**.

| Feature | Sev | What to build | Where |
| --- | --- | --- | --- |
| Optimization plane as agent loops | Urgent | `craw code optimize <component>` wrapping `tune`/`refine`/`learn` (scaffold `tune.toml`, seed baseline, drive loop under budget) + an M3a "optimizing a component" skill | M4.5/M3a · *to file* |
| Close the self-generating loop | Urgent | `craw code review [--since]` — aggregate ledger/observer events into an agent-readable "what needs attention" digest with a suggested next authoring action | M6 · *to file* |
| Project-wide cost preview + budget governance | Urgent | `craw code estimate` (no live call) + a `[budget]` ceiling the dashboard renders and that halts agent `--live` calls | M1 · **CRA-273** |
| Whole-project discovery map | High | `craw code map [--json]` — component graph, flow-tagged IO, pipeline topology, consequential sinks, deployed supervisors, version lineage | M2 · *to file (CRA cap)* |
| Operate whole pipelines | High | `craw code deploy <pipeline>` (+ default observers) and `craw code fleet` (list/stop/restart/tail); a "Fleet" dashboard view | M4.5 · *to file* |
| Human-in-the-loop approval | High | `craw code propose`/`apply` — stage a typed diff + cost estimate, human approves before anything consequential/`--live`; reject → `learn --rollback` (unifies with the §12.2 promotion gate) | M6 · *to file* |
| Migrate an existing project | Medium | `craw code adopt [<dir>]` — install plugin/ledger, `map`, validate; subsumes `craw export --claude-code` | M2 · *to file (CRA cap)* |
| Debug a failed run | Medium | `craw code diagnose <run_id>` — ledger record + DLQ + observer events + failing IO → structured root cause; point at `craw replay --swap` to test a fix near-$0 | M6 · *to file* |
| Onboarding / in-loop help | Medium | Guided first-pipeline flow on `init`; `craw code explain <topic>` reading the shipped skills/docs | M2/M3 · *to file (CRA cap)* |
| Resume/cancel in-flight fan-out | Medium | `craw code cancel`/`resume` over the existing `CancelToken`/resume path; dashboard stop/resume buttons | M4.5 · *to file* |

### 12.5 Sequencing note

The highest-leverage items are **M0** (provenance, jailed compile, test harness — every
later mitigation keys on them), the **M1 contracts** (schema negotiation, error envelope —
everything parses `--json` and recovers from errors), and the two responsibility gates:
**cost governance** (§12.4) and **HITL approval** (§12.2/§12.4). An agent firing `--live`
runs and version promotions across a project without a preview gate, an aggregate ceiling,
and a human checkpoint is the plan's largest single risk — and every primitive needed to
close it already ships.
