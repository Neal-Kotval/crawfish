/**
 * Dashboard — the new `/` landing page (replaces OrgPicker).
 *
 * Per the 2026-05-18 product brainstorm: one user, one workspace, projects
 * everywhere. This page shows:
 *   - A welcome hero with the user's display name.
 *   - Two install cards: Dash (desktop studio) and CLI (`craw`).
 *   - The user's projects list, pulled from their primary workspace org.
 *   - "Open canvas →" link per project, deep-linking into Dash.
 *
 * Multi-org back-compat: if the user has >1 org (legacy demo accounts),
 * we surface "Other workspaces" as a small dropdown at the bottom.
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import {
  listMyOrgs,
  listProjects,
  type OrgSummary,
  type ProjectSummary,
} from "../lib/api";
import { formatApiError } from "@crawfish/ui/lib/formatApiError";
import { useCurrentUser } from "../lib/useAuth";
import { ImportModal } from "./ImportModal";

type ProjectsState =
  | { kind: "loading" }
  | { kind: "ok"; projects: ProjectSummary[] }
  | { kind: "error"; title: string; body: string };

type Importer = { tab: "create" | "local" | "github" } | null;

export function Dashboard() {
  const navigate = useNavigate();
  const user = useCurrentUser();
  const [orgs, setOrgs] = useState<OrgSummary[] | null>(null);
  const [error, setError] = useState<{ title: string; body: string } | null>(null);
  const [projects, setProjects] = useState<ProjectsState>({ kind: "loading" });
  const [importer, setImporter] = useState<Importer>(null);

  // Primary org is the oldest one the user is in (founder of the auto-created
  // workspace). Sorting by createdAt ascending puts it first.
  const primaryOrg = useMemo(() => {
    if (!orgs || orgs.length === 0) return null;
    return [...orgs].sort((a, b) => a.createdAt.localeCompare(b.createdAt))[0];
  }, [orgs]);

  const otherOrgs = useMemo(() => {
    if (!orgs || !primaryOrg) return [];
    return orgs.filter((o) => o.id !== primaryOrg.id);
  }, [orgs, primaryOrg]);

  useEffect(() => {
    let cancelled = false;
    listMyOrgs()
      .then((data) => {
        if (!cancelled) setOrgs(data);
      })
      .catch((e) => {
        if (cancelled) return;
        const friendly = formatApiError(e);
        setError({ title: friendly.title, body: friendly.body });
        setOrgs([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!primaryOrg) return;
    void loadProjects(primaryOrg.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [primaryOrg?.id]);

  async function loadProjects(orgId: string) {
    setProjects({ kind: "loading" });
    try {
      const list = await listProjects(orgId);
      setProjects({ kind: "ok", projects: list });
    } catch (e) {
      const friendly = formatApiError(e);
      setProjects({ kind: "error", title: friendly.title, body: friendly.body });
    }
  }

  const loading = orgs === null;
  const firstName = user.name?.split(/[\s.@]/)[0] || user.email?.split("@")[0] || "there";

  return (
    <main className="cfp-shell__main" style={{ padding: 28 }}>
      <Eyebrow>Your workspace</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 36,
          letterSpacing: "-0.028em",
          margin: "8px 0 6px",
        }}
      >
        {loading ? "Loading…" : `Welcome back, ${firstName}.`}
      </h1>
      {!loading && (
        <p
          style={{
            margin: "0 0 24px",
            color: "var(--ink-mute)",
            fontSize: 14,
            maxWidth: 640,
          }}
        >
          Crawfish runs on your machine. Install Dash and the CLI, then point
          them at a folder to start.
        </p>
      )}

      {error && (
        <div
          style={{
            marginBottom: 24,
            padding: "14px 16px",
            background: "var(--warn-bg)",
            border: "1px solid var(--rule-3)",
            borderRadius: "var(--r-md)",
            maxWidth: 1100,
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)", marginBottom: 4 }}>
            {error.title}
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>{error.body}</div>
        </div>
      )}

      {/* ── Install cards ─────────────────────────────────────── */}
      <section
        aria-label="Install Crawfish"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 14,
          maxWidth: 1100,
          marginBottom: 28,
        }}
      >
        <InstallCard
          eyebrow="Desktop · Tauri"
          title="Dash"
          body="The studio. Visual org canvas, agent board, sessions, knowledge — your projects on one screen."
          ctaLabel="↓ Download Dash"
          ctaHref="https://crawfish.dev"
          primary
        />
        <InstallCard
          eyebrow="Terminal · CLI"
          title="craw"
          body={
            <>
              The scriptable engine. Initialize a project (
              <span className="cf-mono">craw init</span>) and your agents pick it up.
            </>
          }
          ctaLabel="$ brew install crawfish"
          ctaHref="https://crawfish.dev/docs/install"
          mono
        />
      </section>

      {/* ── Projects ──────────────────────────────────────────── */}
      <section
        aria-label="Your projects"
        style={{ maxWidth: 1100, display: "flex", flexDirection: "column", gap: 12 }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <h2
            style={{
              fontFamily: "var(--ff-display)",
              fontWeight: 500,
              fontSize: 22,
              letterSpacing: "-0.018em",
              margin: 0,
            }}
          >
            Your projects
          </h2>
          {projects.kind === "ok" && (
            <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
              {projects.projects.length}
            </span>
          )}
        </div>

        {!loading && !primaryOrg && (
          <div
            style={{
              padding: 18,
              border: "1px dashed var(--rule-3)",
              borderRadius: "var(--r-md)",
              color: "var(--ink-mute)",
              fontSize: 13,
              textAlign: "center",
            }}
          >
            Your workspace isn't ready yet. Try refreshing.
          </div>
        )}

        {primaryOrg && (
          <>
            <ProjectList
              state={projects}
              orgName={primaryOrg.name}
              onOpen={(p) =>
                navigate(`/orgs/${primaryOrg.name}/projects?selected=${encodeURIComponent(p.id)}`)
              }
            />
            <div
              style={{
                padding: 14,
                background: "var(--surface)",
                border: "1px solid var(--rule)",
                borderRadius: "var(--r-md)",
                display: "flex",
                flexDirection: "column",
                gap: 10,
              }}
            >
              <Eyebrow>Add a project</Eyebrow>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                <CreateButton onClick={() => setImporter({ tab: "create" })} primary>
                  + Create locally
                </CreateButton>
                <CreateButton onClick={() => setImporter({ tab: "local" })}>
                  + Open local
                </CreateButton>
                <CreateButton onClick={() => setImporter({ tab: "github" })}>
                  + Import from GitHub
                </CreateButton>
              </div>
              <p
                style={{
                  margin: 0,
                  fontSize: 12,
                  color: "var(--ink-mute)",
                  lineHeight: 1.5,
                }}
              >
                <span style={{ fontWeight: 500, color: "var(--ink-soft)" }}>Create</span> spins up a fresh local folder via Dash · <span style={{ fontWeight: 500, color: "var(--ink-soft)" }}>Open local</span> adopts an existing folder · <span style={{ fontWeight: 500, color: "var(--ink-soft)" }}>From GitHub</span> clones a repo.
              </p>
            </div>
          </>
        )}
      </section>

      {/* ── Other workspaces (back-compat) ─────────────────────── */}
      {otherOrgs.length > 0 && (
        <section
          aria-label="Other workspaces"
          style={{ maxWidth: 1100, marginTop: 32, display: "flex", flexDirection: "column", gap: 8 }}
        >
          <Eyebrow>Other workspaces</Eyebrow>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 8,
            }}
          >
            {otherOrgs.map((o) => (
              <button
                key={o.id}
                type="button"
                onClick={() => navigate(`/orgs/${o.name}/canvas`)}
                className="cf-touch-target"
                style={{
                  appearance: "none",
                  cursor: "pointer",
                  background: "var(--surface-2)",
                  border: "1px solid var(--rule-3)",
                  borderRadius: "var(--r-sm)",
                  padding: "8px 12px",
                  fontSize: 13,
                  color: "var(--ink)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                {o.name}
                <span className="cf-mono" style={{ color: "var(--ink-mute)", fontSize: 11 }}>
                  {o.role}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      {importer && primaryOrg && (
        <ImportModal
          orgId={primaryOrg.id}
          orgName={primaryOrg.name}
          defaultTab={importer.tab}
          onClose={() => setImporter(null)}
          onCreated={() => {
            void loadProjects(primaryOrg.id);
            setImporter(null);
          }}
        />
      )}
    </main>
  );
}

function InstallCard({
  eyebrow,
  title,
  body,
  ctaLabel,
  ctaHref,
  primary,
  mono,
}: {
  eyebrow: string;
  title: string;
  body: React.ReactNode;
  ctaLabel: string;
  ctaHref: string;
  primary?: boolean;
  mono?: boolean;
}) {
  return (
    <article
      style={{
        background: "var(--surface-2)",
        border: `1px solid ${primary ? "var(--accent-soft)" : "var(--rule-3)"}`,
        borderRadius: "var(--r-lg)",
        padding: 20,
        display: "flex",
        flexDirection: "column",
        gap: 10,
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <Eyebrow>{eyebrow}</Eyebrow>
      <h3
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 26,
          letterSpacing: "-0.02em",
          margin: 0,
        }}
      >
        {title}
        <span style={{ color: "var(--accent)" }}>.</span>
      </h3>
      <p
        style={{
          margin: 0,
          fontSize: 13,
          color: "var(--ink-soft)",
          lineHeight: 1.5,
        }}
      >
        {body}
      </p>
      <a
        href={ctaHref}
        className="cf-touch-target"
        style={{
          marginTop: 4,
          alignSelf: "flex-start",
          appearance: "none",
          cursor: "pointer",
          textDecoration: "none",
          fontFamily: mono ? "var(--ff-mono)" : "var(--ff-sans)",
          fontSize: 13,
          fontWeight: 500,
          padding: "10px 14px",
          borderRadius: "var(--r-sm)",
          background: primary ? "var(--accent)" : "var(--ink)",
          color: primary ? "#fff" : "var(--ink-on)",
          border: `1px solid ${primary ? "var(--accent)" : "var(--ink)"}`,
        }}
      >
        {ctaLabel}
      </a>
    </article>
  );
}

function ProjectList({
  state,
  orgName,
  onOpen,
}: {
  state: ProjectsState;
  orgName: string;
  onOpen: (p: ProjectSummary) => void;
}) {
  if (state.kind === "loading") {
    return (
      <div
        style={{
          padding: "12px 14px",
          fontFamily: "var(--ff-mono)",
          fontSize: 12,
          color: "var(--ink-mute)",
          border: "1px dashed var(--rule)",
          borderRadius: "var(--r-md)",
        }}
      >
        loading…
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <div
        style={{
          padding: "12px 14px",
          background: "var(--warn-bg)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-md)",
        }}
      >
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", marginBottom: 2 }}>
          {state.title}
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-soft)" }}>{state.body}</div>
      </div>
    );
  }
  if (state.projects.length === 0) {
    return (
      <div
        style={{
          padding: 16,
          border: "1px dashed var(--rule)",
          borderRadius: "var(--r-md)",
          fontSize: 13,
          color: "var(--ink-mute)",
          textAlign: "center",
        }}
      >
        No projects yet. Add one below to get started.
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {state.projects.map((p) => (
        <button
          key={p.id}
          type="button"
          onClick={() => onOpen(p)}
          className="cf-touch-target"
          style={{
            appearance: "none",
            cursor: "pointer",
            textAlign: "left",
            background: "var(--surface-2)",
            border: "1px solid var(--rule)",
            borderRadius: "var(--r-md)",
            padding: "12px 14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <span style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0, flex: 1 }}>
            <span style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)" }}>{p.name}</span>
            <span
              className="cf-mono"
              style={{
                fontSize: 11,
                color: "var(--ink-mute)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {p.githubRepo ?? p.localPath ?? "—"}
            </span>
          </span>
          <Pill tone={p.cloneStatus === "cloned" ? "good" : "ink"}>
            {projectStatusLabel(p)}
          </Pill>
        </button>
      ))}
    </div>
  );
}

function projectStatusLabel(p: ProjectSummary): string {
  if (p.cloneStatus === "local_only") return "local";
  if (p.cloneStatus === "cloning") return "cloning…";
  if (p.cloneStatus === "cloned") return "cloned";
  return "error";
}

function CreateButton({
  onClick,
  primary,
  children,
}: {
  onClick: () => void;
  primary?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="cf-touch-target"
      style={{
        appearance: "none",
        cursor: "pointer",
        fontFamily: "var(--ff-sans)",
        fontSize: 13,
        fontWeight: 500,
        padding: "10px 14px",
        borderRadius: "var(--r-sm)",
        background: primary ? "var(--accent)" : "var(--surface-2)",
        color: primary ? "#fff" : "var(--ink)",
        border: `1px solid ${primary ? "var(--accent)" : "var(--rule-3)"}`,
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
      }}
    >
      {children}
    </button>
  );
}
