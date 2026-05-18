/**
 * Projects — list projects for an org at /orgs/:org/projects.
 *
 * Polls GET /api/orgs/:orgId/projects every 5s to surface clone-status
 * transitions driven by the desktop poller (pending → cloning → cloned).
 * The server accepts either the org id or its name/slug for :orgId.
 *
 * Handles three top-level states:
 *  - 409 github_disconnected → reconnect prompt
 *  - empty list             → "Import your first repo" CTA
 *  - non-empty               → list of project cards + Import button
 *
 * The Import modal itself is Task 13; we only wire the open trigger.
 */
import { useEffect, useState } from "react";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";

export type Project = {
  id: string;
  name: string;
  githubRepo: string | null;
  cloneStatus: "pending" | "cloning" | "cloned" | "local_only" | "error";
  cloneError: string | null;
  localPath: string | null;
};

type LoadState =
  | { kind: "loading" }
  | { kind: "disconnected" }
  | { kind: "error"; message: string }
  | { kind: "ok"; projects: Project[] };

export function Projects({
  orgId,
  openImport,
}: {
  orgId: string;
  openImport: () => void;
}) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const r = await fetch(`/api/orgs/${encodeURIComponent(orgId)}/projects`, {
          credentials: "include",
        });
        if (cancelled) return;
        if (r.status === 409) {
          setState({ kind: "disconnected" });
          return;
        }
        if (!r.ok) {
          setState({ kind: "error", message: `HTTP ${r.status}` });
          return;
        }
        const json = (await r.json()) as Project[];
        if (!cancelled) setState({ kind: "ok", projects: json });
      } catch (e) {
        if (!cancelled) {
          setState({
            kind: "error",
            message: e instanceof Error ? e.message : String(e),
          });
        }
      }
    }

    poll();
    const t = window.setInterval(poll, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, [orgId]);

  return (
    <main className="cfp-shell__main" style={{ padding: 28, maxWidth: 880 }}>
      <Eyebrow>{orgId} · projects</Eyebrow>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          margin: "6px 0 24px",
        }}
      >
        <h1
          style={{
            fontFamily: "var(--ff-display)",
            fontWeight: 500,
            fontSize: 32,
            letterSpacing: "-0.025em",
            margin: 0,
          }}
        >
          Projects
        </h1>
        {state.kind === "ok" && state.projects.length > 0 ? (
          <button
            type="button"
            onClick={openImport}
            className="cfp-btn cfp-btn--primary"
            style={{ cursor: "pointer" }}
          >
            Import project
          </button>
        ) : null}
      </div>

      <Body state={state} openImport={openImport} />
    </main>
  );
}

function Body({
  state,
  openImport,
}: {
  state: LoadState;
  openImport: () => void;
}) {
  if (state.kind === "loading") {
    return (
      <div
        className="cf-mono"
        style={{ marginTop: 12, color: "var(--ink-mute)", fontSize: 12 }}
      >
        loading…
      </div>
    );
  }

  if (state.kind === "disconnected") {
    return <ReconnectPrompt />;
  }

  if (state.kind === "error") {
    return (
      <p style={{ color: "var(--ink-soft)", fontSize: 14, marginTop: 12 }}>
        Couldn't load projects: {state.message}
      </p>
    );
  }

  if (state.projects.length === 0) {
    return <Empty onImport={openImport} />;
  }

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
        gap: 16,
      }}
    >
      {state.projects.map((p) => (
        <ProjectCard key={p.id} p={p} />
      ))}
    </div>
  );
}

function statusTone(s: Project["cloneStatus"]): "ink" | "warn" | "accent" | "danger" {
  switch (s) {
    case "cloned":
      return "accent";
    case "cloning":
    case "pending":
      return "warn";
    case "error":
      return "danger";
    case "local_only":
    default:
      return "ink";
  }
}

function StatusBadge({ s }: { s: Project["cloneStatus"] }) {
  return <Pill tone={statusTone(s)}>{s.replace("_", " ")}</Pill>;
}

function ProjectCard({ p }: { p: Project }) {
  return (
    <div
      style={{
        padding: 16,
        border: "1px solid var(--rule-3)",
        borderRadius: "var(--r-lg)",
        background: "var(--surface-2)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <span style={{ fontSize: 14, fontWeight: 500 }}>{p.name}</span>
        <StatusBadge s={p.cloneStatus} />
      </div>
      <span
        className="cf-mono"
        style={{ fontSize: 11, color: "var(--ink-mute)" }}
      >
        {p.githubRepo ?? "Local only"}
      </span>
      {p.localPath ? (
        <span
          className="cf-mono"
          style={{
            fontSize: 11,
            color: "var(--ink-soft)",
            wordBreak: "break-all",
          }}
        >
          {p.localPath}
        </span>
      ) : null}
      {p.cloneError ? (
        <span
          className="cf-mono"
          style={{
            fontSize: 11,
            color: "var(--danger)",
            wordBreak: "break-word",
          }}
        >
          {p.cloneError}
        </span>
      ) : null}
    </div>
  );
}

function Empty({ onImport }: { onImport: () => void }) {
  return (
    <div
      style={{
        marginTop: 12,
        padding: 28,
        border: "1px dashed var(--rule-3)",
        borderRadius: "var(--r-lg)",
        background: "var(--paper)",
        textAlign: "center",
      }}
    >
      <p style={{ color: "var(--ink-soft)", fontSize: 14, marginBottom: 16 }}>
        No projects yet. Import a GitHub repo or adopt a local folder to get
        started.
      </p>
      <button
        type="button"
        onClick={onImport}
        className="cfp-btn cfp-btn--primary"
        style={{ cursor: "pointer" }}
      >
        Import your first repo
      </button>
    </div>
  );
}

function ReconnectPrompt() {
  return (
    <div
      style={{
        marginTop: 12,
        padding: 16,
        border: "1px solid var(--rule-3)",
        borderRadius: "var(--r-lg)",
        background: "var(--warn-bg)",
        color: "var(--ink-soft)",
        fontSize: 14,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 12,
      }}
    >
      <span>
        Your GitHub connection is missing or revoked. Reconnect to keep
        importing repos.
      </span>
      <a
        href="/auth"
        style={{
          color: "var(--accent)",
          textDecoration: "none",
          fontWeight: 500,
          whiteSpace: "nowrap",
        }}
      >
        Reconnect GitHub →
      </a>
    </div>
  );
}
