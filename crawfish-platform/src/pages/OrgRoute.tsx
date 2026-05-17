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
import { useCurrentUser } from "../lib/useAuth";

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
    case "board":
      return <Surface eyebrow={`${org} · board`} title="Board" body="Shared kanban board for human + agent tickets." />;
    case "sessions":
      return <Surface eyebrow={`${org} · sessions`} title="Sessions" body="Cross-team transcripts with public permalinks for sharing a session externally." />;
    case "knowledge":
      return <Surface eyebrow={`${org} · knowledge`} title="Knowledge" body="Shared ADRs, runbooks, and pinned slack messages indexed for agent retrieval." />;
    case "diagnoses":
      return <Surface eyebrow={`${org} · diagnoses`} title="Diagnoses" body="Org-wide findings across agents — token bloat, retry storms, librarian misses." />;
    case "team":
      return <Surface eyebrow={`${org} · team`} title="Team & invites" body="Invite humans, assign roles, manage ACL groups, see who's online." />;
    case "billing":
      return <Surface eyebrow={`${org} · billing`} title="Billing" body="Monthly usage, per-agent budgets, plan, payment methods." />;
    case "settings":
      return <Surface eyebrow={`${org} · settings`} title="Org settings" body="Name, domain, default runtime, policy presets, integrations." />;
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
        setState({ kind: "error", status: err.status, message: err.message || "Failed to load org." });
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
    const isForbidden = state.status === 403;
    const isNotFound = state.status === 404;
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
          {isForbidden ? "This org isn't yours" : isNotFound ? "Org not found" : "Couldn't load this org"}
        </h1>
        <p style={{ color: "var(--ink-soft)", fontSize: 14, maxWidth: 640 }}>
          {isForbidden
            ? "You're signed in, but you're not a member of this org. Ask the founder for an invite."
            : isNotFound
              ? `No org named "${orgSlug}" on this server.`
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
          background: "var(--paper-2, #f3eee2)",
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
          href="https://crawfish.dev"
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
            <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
              viewing as {me.name || me.email}
            </span>
            <AvatarStack>
              {org.members.slice(0, 5).map((m) => (
                <Avatar key={m.email} name={m.name || m.email} size="sm" title={`${m.email} · ${m.role}`} />
              ))}
            </AvatarStack>
          </div>
        </div>
      </div>

      {/* Dotted canvas surface */}
      <div
        style={{
          position: "relative",
          flex: 1,
          minHeight: 520,
          background:
            "radial-gradient(circle, var(--rule, #e6e0d0) 1px, transparent 1px) 0 0 / 18px 18px",
          backgroundColor: "var(--paper)",
          overflow: "auto",
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
          org.agents.map((agent, i) => {
            const x = DEFAULT_GRID_XS[i] ?? 84 + (i - DEFAULT_GRID_XS.length) * 244;
            const y = DEFAULT_GRID_Y + Math.floor(i / DEFAULT_GRID_XS.length) * 140;
            return (
              <Node
                key={agent.name}
                x={x}
                y={y}
                name={agent.name}
                role={agent.role}
                runtime={agent.runtime}
                status="ready"
                variant={i === 0 ? "accent" : "neutral"}
              />
            );
          })
        )}
      </div>
    </main>
  );
}
