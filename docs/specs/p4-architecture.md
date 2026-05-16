# Phase 4 Architecture — Runtimes, GitHub, Knowledge

This document fleshes out the three architectural workstreams the user
asked for during Phase 4 planning:

- **§1 — Multi-LLM runtime abstraction**: Claude Code, Claude API, OpenAI
  / ChatGPT, OpenAI Codex CLI — each agent picks the provider that runs
  its turns.
- **§2 — Project storage architecture**: `org-fs/` is *internal* working
  memory. *External* repos and reference material bind through a new
  knowledge layer with a local RAG index. `org-fs/` is not just a folder.
- **§3 — GitHub bridge**: connect a repo per org. Read-only first
  (issues/PRs into the board + sessions), write-back later. GitHub stays
  advisory; Crawfish stays authoritative.

Companion docs: `ROADMAP.md` §Phase 4, `docs/specs/org-contract.md` (v2
schema additions land here when this phase enters build).

---

## 1 · Multi-LLM runtime abstraction

### Problem

Today every agent assumes Claude. The `crons.ts` daemon fires on schedule
but the LLM invocation is stubbed. To let a founder say "this support
agent uses GPT-4o, my code reviewer uses Claude Opus, my designer uses
Claude Code locally," we need a provider interface and a per-agent
runtime selector.

### Concept — `RuntimeProvider`

```ts
interface RuntimeProvider {
  id: string;                         // "claude-code" | "claude-api" | "openai-api" | "codex"
  displayName: string;
  /** Synthesize a single turn against the provider. Used by cron + the
   *  on-demand "run task" action. Returns the text output + token usage. */
  run(opts: {
    member: AgentMember;              // includes prompt_file, tools, model
    input: string;                    // task prompt
    context: ProviderContext;         // tools, org_fs handle, knowledge_query handle
  }): Promise<{
    output: string;
    tokens_used: { input: number; output: number; cache_read?: number; cache_write?: number };
    cost_usd?: number;
  }>;
  /** Liveness probe — does this provider have the credentials it needs? */
  health(): Promise<{ ok: true } | { ok: false; reason: string }>;
}
```

### Built-in providers

| Provider id     | Backend              | Auth                                  | When to pick it                           |
| --------------- | -------------------- | ------------------------------------- | ----------------------------------------- |
| `claude-code`   | Claude Code CLI      | none (uses Claude Code subscription)  | Daily-driver, interactive, no key needed  |
| `claude-api`    | `@anthropic-ai/sdk`  | `ANTHROPIC_API_KEY` (env or keychain) | Scheduled / autonomous runs, fine-grained |
| `openai-api`    | `openai` SDK         | `OPENAI_API_KEY`                      | GPT-4o / o3 for tasks where you want it   |
| `codex`         | OpenAI Codex CLI     | shared with `openai-api`              | Codebase-heavy coding sessions            |

The `claude-code` provider spawns Claude Code as a subprocess with the
agent's prompt + tool allowlist; Claude Code handles the loop and we
capture stdout + token-usage from its JSONL.

### Per-agent runtime selection

`org.json` members get a new optional field:

```jsonc
{
  "id": "eng",
  "kind": "agent",
  "role": "Engineer",
  "name": "Dana",
  "prompt_file": "members/eng.md",
  "tools": ["board_*", "org_fs_*", "codebase_*"],
  "model": "claude-sonnet-4-6",
  "runtime": "claude-code"            // NEW: default if absent
}
```

Validation: if `runtime === "claude-api"` or `"openai-api"`, the daemon
will refuse to start the agent unless the corresponding env var or
keychain entry is present.

### Where it ships

- `crawfish-lens/src/runtimes/` (new dir) — one file per provider.
- `crawfish-lens/src/server/crons.ts` — replace the stubbed
  `runCron(cron)` body with `RuntimeProviders.get(member.runtime).run(...)`.
- `crawfish-dash/web/src/routes/Settings.tsx` — new "Runtimes" sub-tab
  showing credential status per provider and a small "Test" button per
  provider.

### Non-goals for Phase 4

- A provider for Gemini / Mistral / local Ollama. Architecturally the
  interface supports them — we just won't write the adapter in P4.
- Cost-budgeting across providers. Tokens stay the unit.

---

## 2 · Project storage — `org-fs` + knowledge layer + RAG

### Current state (v1)

`~/.crawfish/orgs/<id>/files/` is a flat hosted FS, capped at 1 MiB per
file. Agents read/write via `org_fs_*` MCP tools. There's no indexing,
no embedding, no external bind, no RAG. The folder *is* the storage.

### Phase 4 model — three layers

```
                      ┌─────────────────────────────────┐
                      │   knowledge_query(q, k)         │  ← agents call this
                      │   knowledge_ingest(source)      │
                      └──────────────┬──────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
   ┌────────▼──────────┐  ┌──────────▼──────────┐  ┌──────────▼──────────┐
   │ Internal working  │  │ Org knowledge       │  │ External sources    │
   │ org-fs/           │  │ org-fs/knowledge/   │  │ bound via org.json  │
   │ ─────────────     │  │ ─────────────       │  │ ─────────────       │
   │ scratchpad/       │  │ runbooks, ADRs,     │  │ - git repo path     │
   │ outputs/          │  │ product specs,      │  │ - URL list          │
   │ agent-memory/     │  │ FAQs, internal docs │  │ - file path glob    │
   └───────────────────┘  └─────────────────────┘  └─────────────────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │ SQLite + sqlite-vec │  ← local-only index,
                          │ embeddings table    │     no embedding API
                          │ per-org, rebuildable│
                          └─────────────────────┘
```

### The three layers, named

1. **Internal working memory** (`org-fs/scratchpad/`, `org-fs/outputs/`,
   `org-fs/agent-memory/`) — fast, mutable, per-agent or per-task.
   *Not* indexed for RAG. This is RAM.

2. **Org knowledge** (`org-fs/knowledge/`) — durable, human-curated
   markdown files. Onboarding docs, ADRs, product specs, FAQs. Indexed
   into the RAG store. This is the long-term memory.

3. **External sources** (declared in `org.json.knowledge_sources`) —
   pointers to material *outside* the org dir: a git repo path, a URL,
   a directory glob. Indexed by reference (we crawl on a schedule;
   contents are not copied). This is "everything the org should know
   about but doesn't own."

### Schema additions to `org.json`

```jsonc
{
  // ... existing fields ...
  "knowledge_sources": [
    {
      "id": "main-repo",
      "kind": "repo",
      "path": "/abs/path/to/repo",
      "include": ["**/*.md", "src/**/*.ts"],
      "exclude": ["node_modules", "dist"]
    },
    {
      "id": "stripe-docs",
      "kind": "url",
      "url": "https://stripe.com/docs/api",
      "depth": 1
    },
    {
      "id": "team-runbooks",
      "kind": "files",
      "path": "/Users/me/Documents/runbooks"
    }
  ]
}
```

### RAG storage

- **Local-only.** SQLite + `sqlite-vec` (or `sqlite-vss`) extension —
  ships with Node, no Pinecone / Vectara / Postgres needed.
- **Embeddings.** Local model via `transformers.js`
  (`Xenova/all-MiniLM-L6-v2`, 384-dim, 23MB, runs on CPU). Falls back to
  the active runtime's embeddings API if the user opts in (`org.json.embeddings_via: "openai-api"`).
- **Chunking.** ~512 token chunks with 64-token overlap, sentence-boundary
  aware. Configurable per source.
- **Rebuild.** `POST /api/orgs/:id/knowledge/rebuild` — wipes the
  embeddings table and re-ingests every source. Same model as
  `/api/orgs/:id/search/rebuild` from Phase 3 (FTS5 for tasks; this is
  the vector counterpart for knowledge).

### New MCP tools (in `crawfish-orgctl`)

| Tool                      | Args                                          | Returns                                    |
|---------------------------|-----------------------------------------------|--------------------------------------------|
| `knowledge_query`         | `{ org_id, q, k? = 5, source_id? }`           | `{ tokens_used, hits: KnowledgeHit[] }`    |
| `knowledge_ingest`        | `{ org_id, source_id }`                       | `{ tokens_used, chunks_indexed }`          |
| `knowledge_list_sources`  | `{ org_id }`                                  | `{ tokens_used, sources: KnowledgeSource[] }` |

`KnowledgeHit` carries `{ source_id, path_or_url, chunk_text, score }` so
the agent can cite the source instead of hallucinating from chunks.

### Where it ships

- `crawfish-lens/src/knowledge/` (new dir): chunker, embedder, sqlite-vec
  wrapper, source crawlers (`repo`, `url`, `files`).
- `crawfish-lens/src/server/knowledge.ts` — HTTP handlers
  (`/api/orgs/:id/knowledge`, `/.../knowledge/rebuild`, `/.../knowledge/query`).
- `crawfish-orgctl/src/tools/knowledge.ts` — MCP tool group.
- `crawfish-dash/web/src/routes/Org.tsx` — new "Knowledge" tab per org
  showing sources, last-indexed timestamps, and a search box that fires
  the query.

### Why not external by default

Local-first is non-negotiable through Phase 4 (per
`ROADMAP.md` §"What this is NOT building"). External vector DBs
(`pgvector`, Pinecone, Vectara, Chroma) are listed as adapters but not
implemented — they wait for the cloud-sync work in Phase 5.

---

## 3 · GitHub bridge

### Problem

Many users live in GitHub already — issues, PRs, branches. Crawfish
should meet them where they are without becoming a Jira-style mirror.

### Stance

- **Crawfish is authoritative** for tasks, messages, reviews. (Same rule
  as the "no external trackers as a dependency" anti-goal.)
- **GitHub is advisory** — issues import as suggested tasks, PRs import
  as suggested reviews. The user accepts or ignores.
- **Read-only first.** Phase 4 only pulls *from* GitHub. Push-back
  (Crawfish task → open GH issue, Crawfish review → comment on GH PR)
  is in Phase 4 stretch but can land later.
- **No webhook server.** Local poll every N minutes via `gh` CLI or the
  GH REST API directly.

### Connection options

1. **`gh` CLI passthrough.** If the user has `gh` installed and
   authenticated, we shell out to it for reads. No token plumbing
   needed. *Default.*
2. **Personal access token in keychain.** For users without `gh`, store
   a PAT via `keytar`-equivalent (cross-platform secrets store). Token
   needs `repo` scope only.
3. **GitHub App.** Out of P4 scope. Listed for completeness.

### Schema additions to `org.json`

```jsonc
{
  // ...
  "github": {
    "repo": "owner/name",
    "auth": "gh" | "pat",             // PAT → token kept in keychain, never in org.json
    "sync": {
      "issues": true,
      "prs": true,
      "branches": true
    },
    "poll_interval_seconds": 300
  }
}
```

### What syncs in

- **Issues** → suggested tasks. New issue creates a `task_created` event
  with `labels: ["from-github", ...gh.labels]`, `description: gh.body`,
  and a back-pointer `external_ref: { kind: "github_issue", url, number }`.
  Closing the issue on GH transitions the task to `done`.
- **PRs** → suggested reviews under the new Reviews surface (Phase 5
  natively, but the GH bridge can scaffold the data layout in P4).
  Stored under `~/.crawfish/orgs/<id>/reviews.jsonl` so we don't have to
  block on the full P5 review surface.
- **Branch state** — each task can opt-in to a "linked branch" field
  showing ahead/behind/conflicts vs. base. Hits the GH API or `git`
  locally if the repo path is also bound as a knowledge source.

### MCP tools

| Tool                        | Args                                 | Returns                              |
|-----------------------------|--------------------------------------|--------------------------------------|
| `github_list_open_issues`   | `{ org_id }`                         | `{ tokens_used, issues: GHIssue[] }` |
| `github_list_open_prs`      | `{ org_id }`                         | `{ tokens_used, prs: GHPR[] }`       |
| `github_link_task`          | `{ org_id, task_id, kind, number }`  | `{ tokens_used, ok }`                |

### Where it ships

- `crawfish-lens/src/github/` (new dir): `gh` CLI wrapper + REST
  fallback + the issue/PR → task projection.
- `crawfish-lens/src/server/github.ts` — HTTP handlers
  (`/api/orgs/:id/github/poll`, `/.../github/issues`, etc.).
- `crawfish-orgctl/src/tools/github.ts` — MCP tool group.
- `crawfish-dash/web/src/routes/Settings.tsx` — new "Integrations" sub-tab
  with a "Connect GitHub repo" flow (paste `owner/name`, choose `gh` or
  PAT, click Connect → poll fires once, results show up on the board).
- `crawfish-dash/web/src/components/TaskCard.tsx` — small octocat
  ribbon when a task has a GH back-pointer; clicking opens the GH URL.

### What's out of scope

- Write-back (open issues / comment on PRs) — punted to P4-stretch / P5.
- GitLab / Bitbucket — adapter-shaped, but not in P4.
- Webhook receiver — would need a public ingress; not local-first.

---

## 4 · Sequencing inside Phase 4

```
   ┌────────────────────────────────┐
   │ 4.0 — Templates ✓ (just shipped)│
   │  startup · solo-builder · blank │
   │  dev-shop · research · support  │
   └──────────────┬──────────────────┘
                  │
       ┌──────────┼──────────┐
       │          │          │
   ┌───▼──┐  ┌────▼───┐  ┌───▼───┐
   │ 4.1  │  │  4.2   │  │  4.3  │
   │ Run- │  │ Know-  │  │  GH   │
   │ time │  │ ledge  │  │bridge │
   │ abs- │  │ layer  │  │       │
   │ traction│ +RAG  │  │       │
   └──┬───┘  └────┬───┘  └───┬───┘
      │           │          │
      └──────┬────┴──────┬───┘
             │           │
        ┌────▼────┐  ┌───▼────┐
        │ Plug    │  │ Demo + │
        │ runtime │  │ docs   │
        │ into    │  │        │
        │ crons   │  │        │
        └─────────┘  └────────┘
```

4.1 and 4.3 can run in parallel; 4.2 (knowledge + RAG) gates the demo
because the demo story is "give an agent your repo, ask it a question."

---

## 5 · Acceptance per workstream

**4.1** — A user can change `runtime: "openai-api"` on any agent in
`org.json`, set `OPENAI_API_KEY` in their env, and trigger a manual cron
run from the Settings → Runtimes panel. The output appears as a
`task_commented` event on the board, with `tokens_used` reported.

**4.2** — A user adds their own git repo as a `knowledge_source`, clicks
"Rebuild index", and within a few seconds can ask "what does the auth
module do?" in the Knowledge tab and get back top-5 chunks with file +
line citations.

**4.3** — A user connects `owner/name`, sees their last 20 open issues
appear as backlog tasks tagged `from-github`, and clicking any task
opens the corresponding GH issue URL in their browser.

---

*Owners:* lead writes this spec; the implementing teammates code against
it. Schema changes that need to touch `docs/specs/org-contract.md` are
**lead-only** per `CLAUDE.md`.
