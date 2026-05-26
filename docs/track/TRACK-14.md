# TRACK-14 — Admin, audit & policy

**Components:** `PLAT` (primary) · `DASH` (kill-switch + allow/deny widgets) · `OPS` (the shipped RBAC matrix doc)
**Source:** ORCHESTRATOR-USER-STORIES.md §14 · ROADMAP.md O-stages O2.8, O5.2, O5.3, O5.8, O5.9

> **Component legend** (used in every TRACK file):
> - **PLAT** — the hosted platform. Backend `cloud/server/` (Express + Prisma + Postgres) and the signed-in web SPA `cloud/platform/` (React, Clerk auth).
> - **DASH** — the desktop dashboard `desktop/dash/` (React; proxies to the `desktop/lens` transcript reader).
> - **CLI** — `cli/orgctl/` and `cli/projectctl/` (the craws, the worktree utility, budget/stats/triage primitives, inbound adapters).
> - **OPS** — operational/docs work (runbooks, status page, on-call, published reference docs). Not a code submodule; the deliverable is a written artifact or a process, not a build target.

---

## What this surface is

This is the governance layer. It answers two questions a buyer's security team will ask before
they let an autonomous craw touch their repos: *what is the craw allowed to do*, and *what did it
actually do*. Concretely that is five mechanisms — an append-only audit log of every governance
action, RBAC roles with a documented permission matrix, a workspace-wide kill switch, per-craw
file-path allow/deny lists, and per-craw/per-org network-egress policy — plus one unbuilt
aggregator, the versioned policy bundle.

Two of these mechanisms *constrain* craws before the fact (file-path and egress policy: a craw
physically cannot write to `/secrets/` or call an unlisted host), and the rest *record or pause*
after the fact (the audit log records, the kill switch halts, RBAC gates who may change any of it).
The containment mechanisms follow the GRAND_PLAN §3.16 **defence-toolcall** pattern: the craw's
tools are wrapped so a disallowed action is refused at the call site, not flagged later.

The work splits cleanly by component. Almost all of it is PLAT backend — `cloud/server` owns the
audit projection, RBAC, egress policy, and the kill-switch workflow. Two pieces surface in DASH as
operator widgets (the kill switch and the allow/deny editor). The RBAC permission matrix ships as a
written doc (`OPS`), because its AC explicitly says "matrix shipped as docs." The audit *store*
already exists — Crawfish ships a JSONL substrate — so O5.3 builds the queryable projection and the
UI on top, not a new datastore.

---

## Where the code lives

| Story | Component | Path |
|---|---|---|
| Immutable audit log (§14.1) | `PLAT` | `cloud/server/src/audit/{index,query}.ts` (O5.3); reuses shipped JSONL substrate |
| Filter audit log (§14.2) | `PLAT` | `cloud/server/src/audit/query.ts` + `cloud/platform/src/pages/AuditLog.tsx` (O5.3) |
| RBAC roles + matrix (§14.3) | `PLAT` + `OPS` | `cloud/server/src/auth/rbac.ts` + `docs/orchestrator/rbac-matrix.md` (O5.2) |
| Kill switch (§14.4) | `PLAT` + `DASH` | `cloud/server` workflow control + `desktop/dash` operator toggle (O5.9) |
| File-path allow/deny (§14.5) | `PLAT` + `DASH` | policy model in `cloud/server` + editor in `desktop/dash`; enforced in `CLI` worker at worktree mount (O2.8) |
| Egress allowlist (§14.6) | `PLAT` | `cloud/server/src/policy/egress.ts` (O5.8) |
| Versioned policy bundle (§14.7) | `PLAT` | **unmapped — see Gaps** |

---

## User stories

Tags are now **components** (where it gets built), not personas.

14.1 **[PLAT]** Every governance-relevant action is written to an immutable audit log: member added/removed, role changed, craw installed, policy edited, budget changed, manual task takeover. *AC: log is append-only; exportable as JSONL; uses existing JSONL substrate.*

14.2 **[PLAT, DASH]** Filter the audit log by actor, action type, time window, and resource. *AC: 90-day retention default; configurable per workspace; older data exported and purged.*

14.3 **[PLAT, OPS]** RBAC: assign roles (admin, member, viewer); each role has a documented permission matrix. *AC: matrix shipped as docs; admin can override per-resource.*

14.4 **[PLAT, DASH]** Set a kill-switch policy: pause all craw activity workspace-wide. *AC: pause is reversible; in-flight tasks complete; new dispatches queue.*

14.5 **[PLAT, DASH]** Configure a per-craw allow/deny list of file paths (e.g., the lint-craw cannot touch `/secrets/` or `/migrations/`). *AC: enforced at the worktree mount level; violations block before commit.*

14.6 **[PLAT]** Configure a per-craw allow list of network egress destinations (default: GitHub + LLM provider only). *AC: matches GRAND_PLAN §3.16 defence-toolcall pattern.*

14.7 **[PLAT]** Configure a policy bundle per workspace: required reviewer count, allowed labels, max diff size for auto-approval. *AC: policy bundle is JSON; editable in dashboard; versioned with audit trail.*

14.8 **[deferred → v2]** SSO, SAML, OIDC, custom retention policies, data residency.

---

## Coding tasks, by component

### PLAT — `cloud/server` + `cloud/platform`

- **O5.3** — Audit log projection + UI (`cloud/server/src/audit/{index,query}.ts` + `cloud/platform/src/pages/AuditLog.tsx`). Implements §14.1 and §14.2. The store is the shipped append-only JSONL; this task builds the **projection** (a queryable index rebuilt from the JSONL) and the filter UI. Every other surface writes its governance events here — member changes, craw installs, policy edits, takeovers (TRACK-11 §11.3), PR-bot revisions (TRACK-9 §9.7) — so this is the single trail. Six action types must be representable:

  ```ts
  // cloud/server/src/audit/index.ts — one append, never an update
  type AuditEvent = {
    ts: string;            // ISO-8601, set at write time
    actor: string;         // userId or "craw:<id>"
    action: "member.added" | "member.removed" | "role.changed"
          | "craw.installed" | "policy.edited" | "budget.changed"
          | "task.takeover";
    resource: string;      // e.g. "repo:acme/api" or "craw:dep-bumper"
    detail: Record<string, unknown>;
  };
  // Append-only: write a line, fsync, return. No row is ever mutated.
  await appendJsonl(auditPath(workspaceId), JSON.stringify(event) + "\n");
  ```

  The projection (`query.ts`) reads the JSONL and builds an index keyed by actor / action / time /
  resource so the §14.2 filters are fast. The index is disposable — if it is lost, rebuild it by
  replaying the JSONL.

- **O5.2** — RBAC roles + permission matrix (`cloud/server/src/auth/rbac.ts`). Implements §14.3. Three roles (admin, member, viewer); every guarded route checks the matrix; admin may override per-resource. The matrix is the authoritative may-do source for *every* surface, so encode it as data the server reads, not as scattered `if (role === ...)` checks:

  ```ts
  // cloud/server/src/auth/rbac.ts
  const MATRIX = {
    admin:  { "craw.install": true,  "policy.edit": true,  "audit.read": true },
    member: { "craw.install": true,  "policy.edit": false, "audit.read": true },
    viewer: { "craw.install": false, "policy.edit": false, "audit.read": true },
  } as const;

  function may(role: Role, perm: Permission, override?: ResourceOverride): boolean {
    if (override?.perm === perm) return override.allow;  // per-resource admin override
    return MATRIX[role][perm] ?? false;
  }
  ```

  Cross-ref: seat/role assignment (TRACK-1 §1.2, TRACK-12 seats) reads the `OrgMember.role` field — RBAC and seat-billing share `OrgMember` but answer different questions (may-do vs. is-billable).

- **O5.8** — Per-craw + per-org network egress policy (`cloud/server/src/policy/egress.ts`). Implements §14.6. Default allowlist is GitHub + the LLM provider only; per-craw and per-org scoping means a forked craw (TRACK-2 §2.7) cannot widen its egress beyond its org's policy. Same defence-toolcall pattern as file-path policy — keep both in one policy model so a craw's containment is a single object, not two unrelated tables.

- **O5.9** — Workspace-wide kill switch (PLAT workflow control + DASH toggle). Implements §14.4. The broadest pause in the system: reversible, in-flight tasks finish, new dispatches queue. Same pause mechanic as budget caps (TRACK-5/12) but at maximum scope, and the pause action is itself an audited event (§14.1). PLAT owns the workflow flag and the queue gate; DASH owns the operator-facing toggle (below).

### DASH — `desktop/dash`

- **O5.9 (widget)** — Kill-switch toggle. A prominent, fast-to-reach control (this is an emergency action) that flips the workspace pause flag via the PLAT API and reflects current state. It must show what is in-flight versus queued so the operator understands that pausing does not abort running work.

- **O2.8 (editor)** — File-path allow/deny editor. The dashboard surface where an admin authors the per-craw allow/deny list. The list is data; **enforcement happens in the CLI worker at the worktree mount** (below), not in DASH. DASH only edits and displays the policy.

### CLI — enforcement point for O2.8

- **O2.8 (enforcement)** — Per-craw file-path allow/deny enforcement at the worktree mount. Implements §14.5. The allow/deny list authored in DASH is enforced by the worker when it mounts the worktree: a write to a denied path is refused at the filesystem boundary **before commit**, not caught in a post-hoc diff review. This is the defence-toolcall pattern (GRAND_PLAN §3.16) applied to file writes, and it shares the worktree-isolation substrate with TRACK-5 (O0.5).

  ```ts
  // CLI worker — wrap the file-write tool so a denied path never lands on disk
  function guardedWrite(policy: PathPolicy) {
    return async (path: string, contents: string) => {
      if (!policy.allows(path)) {
        // Refuse at the call site. The craw sees a tool error, not a silent skip,
        // and nothing is staged for commit.
        throw new PolicyViolation(`write to ${path} denied by craw policy`);
      }
      return fs.writeFile(resolveInWorktree(path), contents);
    };
  }
  ```

**Reuses (already shipped — do not rebuild):**
- The JSONL audit substrate (`PLAT`) — cited directly in §14.1 AC. The store ships; O5.3 builds only the projection + UI.
- `OrgMember` Prisma model (`PLAT`) — RBAC role assignment reads/writes its `role` field.
- Worktree isolation (`CLI`, O0.5, TRACK-5) — the mount where O2.8 path enforcement attaches.

---

## Key technical concepts, explained

**Append-only audit log: immutable store vs. rebuildable projection (§14.1).** The integrity
guarantee is that the *record* is never altered — the JSONL file is written line-by-line and never
edited or deleted in place. But you cannot filter a flat file efficiently, so O5.3 also builds a
*projection*: an index derived from the JSONL. These are different objects with different rules.

```ts
// Store: immutable. The only mutation is appending a new line.
appendJsonl(path, line);           // never updateLine() / deleteLine()

// Projection: disposable. Built by reading the store; safe to drop and rebuild.
function rebuildIndex(path) {
  const idx = new AuditIndex();
  for (const line of readLines(path)) idx.add(JSON.parse(line));  // replay
  return idx;
}
```

If the projection is corrupted or its schema changes, you rebuild it from the store. If the store
is corrupted, you have lost the audit trail — which is why it is append-only and fsync'd.

**Defence-toolcall: enforce file-path policy at the worktree mount, before commit (§14.5).** The
naive design checks the diff at PR time and rejects a PR that touched `/secrets/`. That is too late:
the secret has already been read into the craw's context and written to disk in the worktree. The
defence-toolcall pattern (GRAND_PLAN §3.16) instead wraps the craw's *write tool* so a disallowed
path is refused at the call site (see `guardedWrite` above). The denied write never reaches the
filesystem, so there is nothing to catch at commit. Egress policy (§14.6) is the same pattern applied
to the network tool.

**The RBAC matrix as the authoritative may-do source (§14.3).** Encoding permissions as a single
data structure (the `MATRIX` above) rather than inline role checks means there is one place that
answers "may this role do this," and the shipped `rbac-matrix.md` doc is generated from — or verified
against — that same structure. Scattering `if (role === "admin")` checks across routes guarantees
drift between what the docs promise and what the code enforces.

**Retention purge is archival export + tombstone, not in-place delete (§14.2).** The 90-day default
retention (configurable per workspace) requires purging older data — but an in-place delete would
break the append-only guarantee of §14.1. So "purge" means: export the aged records to cold storage,
then write a tombstone line recording that range `[t0, t1]` was archived and where it went. The store
stays append-only; queries past the window resolve to "archived, fetch from export."

```ts
// Purge = export + tombstone, never a destructive delete on the store.
const archived = await exportRange(workspaceId, olderThan(90, "days"));
appendJsonl(auditPath(workspaceId), JSON.stringify({
  ts: now(), actor: "system", action: "audit.archived",
  resource: `range:${archived.from}..${archived.to}`,
  detail: { location: archived.uri },
}) + "\n");
```

---

## Gaps — work with no O-stage assigned

These stories have acceptance criteria but **no numbered O0–O7 deliverable.** Flag for the lead.

- **§14.7 unified versioned policy bundle.** No numbered deliverable. The bundle's constituent
  settings already live across surfaces — required reviewer count is §8.5 (O1.4), max-diff-for-
  auto-approval is §4.5/§4.6 (O1.3), allowed labels is routing (O2.7) — but the *single, versioned
  JSON policy bundle* with its own edit UI and audit trail is unbuilt. *What's needed:* decide
  whether §14.7 is (a) a genuine new aggregate object stored and versioned as one JSON document, or
  (b) an aggregation **view** that reads the three existing settings and presents them together.
  Option (b) is far cheaper but does not satisfy "versioned with audit trail" unless the view itself
  snapshots and diffs. Lead should pick (a) or (b) and assign an O-stage.

- **§14.8 SSO / SAML / OIDC + custom retention + data residency.** `[deferred → v2]`; ROADMAP confirms
  SSO is Stage 3. No O-stage. v1 ships the 90-day default retention plus a single configurable window
  only — not arbitrary custom retention policies.

---

## Open questions

- **§14.7 bundle vs. view:** if the policy bundle is an aggregation view (option b above), what does
  "versioned with audit trail" mean for settings that are versioned independently in their own
  surfaces? Either the view snapshots all three on every edit, or "versioned" is a promise the view
  cannot keep. Decide before assigning.
- **§14.2 vs §16.6 (TRACK-16):** the 90-day audit retention window and the 90-day post-cancel export
  window coincide numerically but are different clocks. Confirm they stay decoupled — purging audit
  data on a retention timer must not interfere with a cancelled customer's 90-day export.
- **§14.5/§14.6 one policy model:** confirm file-path and egress policy share a single per-craw policy
  object. They are two halves of one containment story; splitting them into separate tables invites a
  craw that is locked down on disk but open on the network.
