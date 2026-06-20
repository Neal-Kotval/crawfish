# Connector starter issues

These are ready-to-file `connector`-labeled starter issues — the canonical first
contribution to Crawfish. Each is self-contained: a one-paragraph scope, the base
class to subclass, and a typed I/O sketch. Build one by copying the
[Slack worked example](contributing-a-connector.md) and swapping the body.

Every connector must uphold the [security spine](../architecture/SECURITY.md):
**static-only targets** and **credentials by reference** (an env-var name, never the
value). Sinks default to `dry_run=True` so tests stay offline.

---

## Slack sink — the worked reference

**Status: done.** Shipped as `packages/crawfish-slack/` and documented in full in
[Contributing a connector](contributing-a-connector.md). Use it as the template for
every connector below.

Scope: post a message to a static Slack channel. Holds the bot token by reference and
records writes in dry-run mode. Base class: `Sink[JSONValue]`. Target:
`channel: str (static)`. Input value: message text. `credential_ref` → bot-token
env var.

---

## Notion sink

Scope: create a page or append a block in a fixed Notion database — a clean target
for "summarize each item, file it in a tracker". The database is chosen once
(static); page contents come from the pipeline output. Hold the integration token by
reference; resolve it only at egress.

- **Base class:** `Sink[JSONValue]`
- **Target (static):** `database_id: str`
- **Input value:** page properties / block content (JSON)
- **Credential:** `credential_ref` → Notion integration token env var

## Gmail source

Scope: fetch the messages matching a static Gmail search query so a pipeline can
triage or summarize an inbox. The query is fixed at batch start; results stream as
fluid items. Emits multiple outputs (`multi=True`).

- **Base class:** `Source[JSONValue]`, `multi=True`
- **Input (static):** `query: str` (e.g. `"label:support is:unread"`)
- **Output:** `messages: list[Email]`
- **Credential:** `credential_ref` → OAuth token reference

## Jira sink

Scope: create or comment on an issue in a fixed Jira project — the Atlassian
counterpart to the in-tree Linear sink. Project is static; issue fields come from the
output. Idempotent by the base class, so a re-run won't duplicate the issue.

- **Base class:** `Sink[JSONValue]`
- **Target (static):** `project_key: str`
- **Input value:** issue fields (summary, description, type)
- **Credential:** `credential_ref` → Jira API token env var

## Postgres source

Scope: stream rows from a static, parameterised query so a pipeline can fan out over
a table. The SQL text is static (never model-derived); only bound parameters may
vary. Emits one output per row (`multi=True`).

- **Base class:** `Source[JSONValue]`, `multi=True`
- **Input (static):** `query: str`, optional bound params
- **Output:** `rows: list[Row]`
- **Credential:** `credential_ref` → DSN / connection-string env var

## RSS source

Scope: pull entries from a static feed URL — the simplest possible source (no
credential needed), ideal for a first contribution. The feed URL is static; entries
stream as fluid items.

- **Base class:** `Source[JSONValue]`, `multi=True`
- **Input (static):** `feed_url: str`
- **Output:** `entries: list[FeedEntry]`
- **Credential:** none

## Webhook sink

Scope: POST the pipeline output to a static URL — a generic egress for any system
that accepts JSON. The URL is static so a prompt can't redirect the call; the body is
the output value. Optionally sign the payload with a referenced secret.

- **Base class:** `Sink[JSONValue]`
- **Target (static):** `url: str`
- **Input value:** JSON body
- **Credential:** optional `credential_ref` → signing-secret env var
