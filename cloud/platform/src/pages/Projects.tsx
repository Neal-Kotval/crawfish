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
import { useEffect, useRef, useState } from "react";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import { formatApiError } from "@crawfish/ui/lib/formatApiError";

export type Project = {
  id: string;
  name: string;
  githubRepo: string | null;
  cloneStatus: "pending" | "cloning" | "cloned" | "local_only" | "error";
  cloneError: string | null;
  localPath: string | null;
  linearTeamId: string | null;
  linearTeamKey: string | null;
};

type LoadState =
  | { kind: "loading" }
  | { kind: "disconnected" }
  | { kind: "error"; message: string }
  | { kind: "ok"; projects: Project[] };

export function Projects({
  orgId,
  openImport,
  onOpenProject,
}: {
  orgId: string;
  openImport: () => void;
  onOpenProject?: (p: Project) => void;
}) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });

  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    async function poll() {
      // Pause when the tab is hidden — don't burn server quota in the background.
      if (document.hidden) return;
      try {
        const r = await fetch(`/api/orgs/${encodeURIComponent(orgId)}/projects`, {
          credentials: "include",
        });
        if (cancelledRef.current) return;
        if (r.status === 409) {
          setState({ kind: "disconnected" });
          return;
        }
        if (!r.ok) {
          // Check content-type: if Vite returns HTML (proxy miss), surface a
          // friendly message rather than a raw SyntaxError from res.json().
          const ct = r.headers.get("content-type") ?? "";
          if (ct.includes("text/html")) {
            setState({ kind: "error", message: "Can't reach the server. Start cloud/server and refresh." });
            return;
          }
          setState({ kind: "error", message: formatApiError({ status: r.status }).body });
          return;
        }
        const json = (await r.json()) as Project[];
        if (!cancelledRef.current) setState({ kind: "ok", projects: json });
      } catch (e) {
        if (!cancelledRef.current) {
          setState({ kind: "error", message: formatApiError(e).body });
        }
      }
    }

    poll();
    const t = window.setInterval(poll, 5000);

    // Restart polling when the tab becomes visible again.
    function onVisibility() {
      if (!document.hidden && !cancelledRef.current) poll();
    }
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelledRef.current = true;
      window.clearInterval(t);
      document.removeEventListener("visibilitychange", onVisibility);
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

      <Body state={state} openImport={openImport} onOpenProject={onOpenProject} />
    </main>
  );
}

function Body({
  state,
  openImport,
  onOpenProject,
}: {
  state: LoadState;
  openImport: () => void;
  onOpenProject?: (p: Project) => void;
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
      <div
        style={{
          marginTop: 12,
          padding: "14px 16px",
          background: "var(--warn-bg)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-md)",
          maxWidth: 640,
        }}
      >
        <div style={{ fontSize: 14, fontWeight: 500, color: "var(--ink)", marginBottom: 4 }}>
          Couldn't load projects
        </div>
        <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>{state.message}</div>
      </div>
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
        <ProjectCard key={p.id} p={p} onOpen={onOpenProject} />
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

function ProjectCard({ p, onOpen }: { p: Project; onOpen?: (p: Project) => void }) {
  const clickable = Boolean(onOpen);
  return (
    <div
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onClick={clickable ? () => onOpen!(p) : undefined}
      onKeyDown={
        clickable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onOpen!(p);
              }
            }
          : undefined
      }
      style={{
        padding: 16,
        border: "1px solid var(--rule-3)",
        borderRadius: "var(--r-lg)",
        background: "var(--surface-2)",
        display: "flex",
        flexDirection: "column",
        gap: 8,
        cursor: clickable ? "pointer" : "default",
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
      {clickable ? (
        <span style={{ fontSize: 12, color: "var(--accent)", marginTop: 2 }}>View issues →</span>
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
