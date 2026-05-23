/**
 * OrgRoute — dispatches /orgs/:org/:tab to the right surface.
 *
 * Canvas: fetches the real org and renders a read-only dotted canvas with the
 *         user's actual agents laid out in a default grid. No multi-cursor,
 *         no drag, no live trace (those come post-MVP).
 * Other tabs: still stubbed; will fan out in later milestones.
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import { Node } from "@crawfish/ui/components/Node";
import { Avatar, AvatarStack } from "@crawfish/ui/components/Avatar";
import { fetchOrg, type Org, type ApiError } from "../lib/api";
import { formatApiError } from "@crawfish/ui/lib/formatApiError";
import { useCurrentUser } from "../lib/useAuth";
import { buildDashLink, dashLinkTarget, isDevDashEnabled } from "../lib/dashUrl";
import { OrgMembers } from "./OrgMembers";
import { Projects, type Project } from "./Projects";
import { ProjectIssues } from "./ProjectIssues";
import { Connections } from "./Connections";
import { Board } from "./Board";
import { OrgSettings } from "./OrgSettings";
import { ImportModal } from "./ImportModal";

function Surface({ title, eyebrow, body }: { title: string; eyebrow: string; body: string }) {
  return (
    <main className="cfp-shell__main" style={{ padding: 28 }}>
      <Eyebrow>{eyebrow}</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 32,
          letterSpacing: "-0.025em",
          margin: "6px 0 12px",
        }}
      >
        {title}
      </h1>
      <p style={{ color: "var(--ink-soft)", fontSize: 14, maxWidth: 640 }}>{body}</p>
      <Pill tone="warn" style={{ marginTop: 16 }}>
        scaffold · wire later
      </Pill>
    </main>
  );
}

export function OrgRoute() {
  const { org = "", tab = "canvas" } = useParams<{ org?: string; tab?: string }>();

  switch (tab) {
    case "canvas":
      return <CanvasSurface org={org} />;
    case "projects":
      return <ProjectsSurface org={org} />;
    case "board":
      return <Board orgId={org} />;
    case "sessions":
      return <Surface eyebrow={`${org} · sessions`} title="Sessions" body="Cross-team transcripts with public permalinks for sharing a session externally." />;
    case "knowledge":
      return <Surface eyebrow={`${org} · knowledge`} title="Knowledge" body="Shared ADRs, runbooks, and pinned slack messages indexed for agent retrieval." />;
    case "diagnoses":
      return <Surface eyebrow={`${org} · diagnoses`} title="Diagnoses" body="Org-wide findings across agents — token bloat, retry storms, librarian misses." />;
    case "team":
      return <OrgMembers orgSlug={org} />;
    case "billing":
      return <Surface eyebrow={`${org} · billing`} title="Billing" body="Monthly usage, per-agent budgets, plan, payment methods." />;
    case "connections":
      return <Connections orgId={org} />;
    case "settings":
      return <OrgSettings org={org} />;
    default:
      return <Surface eyebrow={`${org}`} title="Unknown surface" body={`No surface named "${tab}".`} />;
  }
}

// ─── Read-only online canvas ───────────────────────────────────────────────

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; org: Org }
  | { kind: "error"; status: number | undefined; message: string };

const DEFAULT_GRID_Y = 252;
const DEFAULT_GRID_XS = [84, 328, 572, 816];

function CanvasSurface({ org: orgSlug }: { org: string }) {
  const me = useCurrentUser();
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    fetchOrg(orgSlug)
      .then((org) => {
        if (!cancelled) setState({ kind: "ok", org });
      })
      .catch((e) => {
        if (cancelled) return;
        const err = e as ApiError;
        const friendly = formatApiError(e);
        setState({ kind: "error", status: err.status, message: friendly.body });
      });
    return () => {
      cancelled = true;
    };
  }, [orgSlug]);

  if (state.kind === "loading") {
    return (
      <main className="cfp-shell__main" style={{ padding: 28 }}>
        <Eyebrow>{orgSlug} · canvas</Eyebrow>
        <div className="cf-mono" style={{ marginTop: 12, color: "var(--ink-mute)", fontSize: 12 }}>
          loading…
        </div>
      </main>
    );
  }

  if (state.kind === "error") {
    // Server collapses non-member to 404 (see crawfish-server/src/routes/orgs.ts)
    // to avoid leaking org existence. So 403 never reaches us in practice;
    // treat any not-found/forbidden as the same "we couldn't show you this".
    const isMissing = state.status === 404 || state.status === 403;
    return (
      <main className="cfp-shell__main" style={{ padding: 28 }}>
        <Eyebrow>{orgSlug} · canvas</Eyebrow>
        <h1
          style={{
            fontFamily: "var(--ff-display)",
            fontWeight: 500,
            fontSize: 32,
            letterSpacing: "-0.025em",
            margin: "6px 0 12px",
          }}
        >
          {isMissing ? "We couldn't open this org" : "Couldn't load this org"}
        </h1>
        <p style={{ color: "var(--ink-soft)", fontSize: 14, maxWidth: 640 }}>
          {isMissing
            ? `No org named "${orgSlug}" is visible to your account. It may not exist, or you may not be a member yet. Ask the founder for an invite.`
            : state.message}
        </p>
        <Link
          to="/"
          style={{
            display: "inline-block",
            marginTop: 16,
            color: "var(--accent)",
            fontSize: 13,
            textDecoration: "none",
          }}
        >
          ← Back to all orgs
        </Link>
      </main>
    );
  }

  const { org } = state;
  const memberCount = org.members.length;
  const agentCount = org.agents.length;

  return (
    <main className="cfp-shell__main" style={{ padding: 0, display: "flex", flexDirection: "column" }}>
      {/* Read-only banner */}
      <div
        style={{
          padding: "10px 20px",
          background: "var(--paper-2)",
          borderBottom: "1px solid var(--rule)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          fontSize: 13,
        }}
      >
        <span style={{ color: "var(--ink-soft)" }}>
          <span className="cf-mono" style={{ color: "var(--ink-mute)", marginRight: 8, fontSize: 11 }}>
            READ-ONLY
          </span>
          Install Dash to give agents tasks and contribute live.
        </span>
        <a
          href={(import.meta.env.VITE_MARKETING_URL as string | undefined) ?? "https://crawfish.dev"}
          target="_blank"
          rel="noreferrer"
          style={{
            color: "var(--accent)",
            textDecoration: "none",
            fontWeight: 500,
          }}
        >
          Install Dash →
        </a>
      </div>

      {/* Header */}
      <div style={{ padding: "20px 28px 12px", borderBottom: "1px solid var(--rule)" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 16,
          }}
        >
          <div>
            <Eyebrow>{org.name} · canvas</Eyebrow>
            <h1
              style={{
                fontFamily: "var(--ff-display)",
                fontWeight: 500,
                fontSize: 28,
                letterSpacing: "-0.022em",
                margin: "4px 0 4px",
              }}
            >
              {org.name}
            </h1>
            <div className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
              {memberCount} member{memberCount === 1 ? "" : "s"} · {agentCount} agent
              {agentCount === 1 ? "" : "s"}
              {org.project ? ` · ${org.project}` : ""}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <a
              href={buildDashLink({ org: org.name, user: me.email, name: me.name })}
              target={dashLinkTarget()}
              rel={dashLinkTarget() ? "noopener noreferrer" : undefined}
              className="cfp-btn cfp-btn--sm cfp-btn--ink"
              title={
                isDevDashEnabled()
                  ? "Open the dev dash web build (no Tauri install needed)."
                  : "Open this org in the Crawfish desktop app. Requires Dash to be installed."
              }
              style={{ textDecoration: "none" }}
            >
              Open in Dash ↗
            </a>
            <Pill tone="ink">viewing as {me.name || me.email}</Pill>
            {org.members.length === 1 ? (
              <Avatar
                name={org.members[0].name || org.members[0].email}
                size="sm"
                title={`${org.members[0].email} · ${org.members[0].role}`}
              />
            ) : (
              <AvatarStack>
                {org.members.slice(0, 5).map((m) => (
                  <Avatar key={m.email} name={m.name || m.email} size="sm" title={`${m.email} · ${m.role}`} />
                ))}
              </AvatarStack>
            )}
          </div>
        </div>
      </div>

      {/* Dotted canvas surface — agents flow in a wrap container so they
          reflow on mobile instead of clipping off-screen at pixel x=816. */}
      <div
        style={{
          position: "relative",
          flex: 1,
          minHeight: 520,
          background:
            "radial-gradient(circle, var(--rule) 1px, transparent 1px) 0 0 / 18px 18px",
          backgroundColor: "var(--paper)",
          overflow: "auto",
          padding: "32px 24px",
        }}
      >
        {agentCount === 0 ? (
          <div
            style={{
              padding: 40,
              color: "var(--ink-mute)",
              fontSize: 14,
            }}
          >
            No agents in this org yet.
          </div>
        ) : (
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 20,
              alignItems: "flex-start",
              justifyContent: "flex-start",
            }}
          >
            {org.agents.map((agent, i) => (
              <div
                key={agent.name}
                style={{ position: "relative", width: 188, height: 86 }}
              >
                <Node
                  x={0}
                  y={0}
                  name={agent.name}
                  role={agent.role}
                  runtime={agent.runtime}
                  status="ready"
                  variant={i === 0 ? "accent" : "neutral"}
                />
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

// ─── Projects tab ──────────────────────────────────────────────────────────
//
// Thin wrapper that owns the import-modal open state. The org slug is passed
// through as `orgId` because the server's projects router accepts either the
// org id or its slug. The ImportModal component lands in Task 13 — for now
// we render `null` so the open button is wired but no modal appears yet.

function ProjectsSurface({ org }: { org: string }) {
  const [importOpen, setImportOpen] = useState(false);
  const [selected, setSelected] = useState<Project | null>(null);

  if (selected) {
    return <ProjectIssues orgId={org} project={selected} onBack={() => setSelected(null)} />;
  }

  return (
    <>
      <Projects orgId={org} openImport={() => setImportOpen(true)} onOpenProject={setSelected} />
      {importOpen && (
        <ImportModal orgId={org} onClose={() => setImportOpen(false)} />
      )}
    </>
  );
}
