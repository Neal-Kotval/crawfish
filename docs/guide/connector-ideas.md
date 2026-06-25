# Connector starter issues

A connector is the first contribution most people make to Crawfish. These are
`connector`-labeled starter issues, ready to file. Each one is self-contained: a
one-paragraph scope, the base class to subclass, and a sketch of its typed inputs and
outputs. To build one, copy the [Slack worked example](contributing-a-connector.md) and
swap in your body.

!!! warning "Every connector upholds the security model"
    Targets are static-only. Never read a destination from model output. Credentials
    pass by reference: you give the name of an env var, never the value. Sinks default
    to `dry_run=True`, so tests run offline. See the
    [security model](../architecture/SECURITY.md).

## Slack sink, the worked reference

Status: done. It ships as `packages/crawfish-slack/` and is documented in full in
[Contributing a connector](contributing-a-connector.md). Use it as the template for
every connector below.

Scope: post a message to a static Slack channel, holding the bot token by reference and
recording writes in dry-run mode. Base class `Sink[JSONValue]`, target
`channel: str (static)`, input value is message text, `credential_ref` to a bot-token
env var.

## Notion sink

Scope: create a page or append a block in a fixed Notion database. It is a clean target
for "summarize each item, then file it in a tracker." You choose the database once, as a
static input. The page contents come from the pipeline output. Hold the integration
token by reference and resolve it only when you write.

- **Base class:** `Sink[JSONValue]`
- **Target (static):** `database_id: str`
- **Input value:** page properties / block content (JSON)
- **Credential:** `credential_ref` → Notion integration token env var

## Gmail source

Scope: fetch the messages matching a static Gmail search query, so a pipeline can triage
or summarize an inbox. The query is fixed at batch start, and results stream back as
fluid items. It emits multiple outputs (`multi=True`).

- **Base class:** `Source[JSONValue]`, `multi=True`
- **Input (static):** `query: str` (e.g. `"label:support is:unread"`)
- **Output:** `messages: list[Email]`
- **Credential:** `credential_ref` → OAuth token reference

## Jira sink

Scope: create or comment on an issue in a fixed Jira project. It is the Atlassian
counterpart to the in-tree Linear sink. The project is static, and the issue fields come
from the output. The base class makes it idempotent, so a re-run does not duplicate the
issue.

- **Base class:** `Sink[JSONValue]`
- **Target (static):** `project_key: str`
- **Input value:** issue fields (summary, description, type)
- **Credential:** `credential_ref` → Jira API token env var

## Postgres source

Scope: stream rows from a static, parameterised query, so a pipeline can fan out over a
table. The SQL text is static and never model-derived. Only the bound parameters vary.
It emits one output per row (`multi=True`).

- **Base class:** `Source[JSONValue]`, `multi=True`
- **Input (static):** `query: str`, optional bound params
- **Output:** `rows: list[Row]`
- **Credential:** `credential_ref` → DSN / connection-string env var

## RSS source

Scope: pull entries from a static feed URL. It is the simplest source there is, and it
needs no credential, which makes it a good first contribution. The feed URL is static,
and entries stream as fluid items.

- **Base class:** `Source[JSONValue]`, `multi=True`
- **Input (static):** `feed_url: str`
- **Output:** `entries: list[FeedEntry]`
- **Credential:** none

## Webhook sink

Scope: POST the pipeline output to a static URL, a generic egress for any system that
accepts JSON. A static URL means a prompt cannot redirect the call. The body is the
output value. You can optionally sign the payload with a referenced secret.

- **Base class:** `Sink[JSONValue]`
- **Target (static):** `url: str`
- **Input value:** JSON body
- **Credential:** optional `credential_ref` → signing-secret env var

## Next steps

- [Contributing a connector](contributing-a-connector.md) walks the Slack worked example
  to copy.
- [Security model](../architecture/SECURITY.md) covers the rules every connector
  upholds.
