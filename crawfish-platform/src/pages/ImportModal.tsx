/**
 * ImportModal — two-tab modal for adding a project to an org.
 *
 * Tab 1 (From GitHub):
 *   - Debounced search input → GET /api/github/repos?q=<term>
 *   - Scrollable list of {id, full_name, private, default_branch, updated_at}
 *   - Clicking a row POSTs { githubRepoId } to /api/orgs/:orgId/projects
 *     and closes the modal on success.
 *   - 409 github_disconnected → render reconnect prompt in place of the list.
 *
 * Tab 2 (From local folder):
 *   - Stub copy. Task 16 wires the desktop handoff.
 *
 * Styling matches OrgMembers / Projects (Task 12). No new globals.css classes.
 */
import { useEffect, useState } from "react";
import { Pill } from "@crawfish/ui/components/Pill";

type Repo = {
  id: number;
  full_name: string;
  default_branch: string;
  private: boolean;
  updated_at: string;
};

type ListState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "disconnected" }
  | { kind: "error"; message: string }
  | { kind: "ok"; repos: Repo[] };

type Tab = "github" | "local";

export function ImportModal({
  orgId,
  onClose,
  onCreated,
}: {
  orgId: string;
  onClose: () => void;
  onCreated?: () => void;
}) {
  const [tab, setTab] = useState<Tab>("github");

  // Close on Escape.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="cfp-import-title"
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.45)",
        zIndex: 1000,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "10vh 16px 16px",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 560,
          background: "var(--paper)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-lg)",
          boxShadow: "0 24px 60px rgba(0,0,0,0.25)",
          display: "flex",
          flexDirection: "column",
          maxHeight: "80vh",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px 12px",
            borderBottom: "1px solid var(--rule)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <h2
            id="cfp-import-title"
            style={{
              margin: 0,
              fontFamily: "var(--ff-display)",
              fontSize: 20,
              fontWeight: 500,
              letterSpacing: "-0.02em",
            }}
          >
            Import project
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              width: 28,
              height: 28,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              background: "transparent",
              border: "1px solid var(--rule-3)",
              borderRadius: "var(--r-sm)",
              color: "var(--ink-soft)",
              cursor: "pointer",
              fontSize: 16,
              lineHeight: 1,
            }}
          >
            ×
          </button>
        </div>

        {/* Tabs */}
        <div
          role="tablist"
          aria-label="Import source"
          style={{
            display: "flex",
            gap: 4,
            padding: "10px 20px 0",
            borderBottom: "1px solid var(--rule)",
          }}
        >
          <TabButton active={tab === "github"} onClick={() => setTab("github")}>
            From GitHub
          </TabButton>
          <TabButton active={tab === "local"} onClick={() => setTab("local")}>
            From local folder
          </TabButton>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
          {tab === "github" ? (
            <GithubTab orgId={orgId} onClose={onClose} onCreated={onCreated} />
          ) : (
            <LocalTab />
          )}
        </div>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      style={{
        padding: "8px 12px",
        background: "transparent",
        border: "none",
        borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
        color: active ? "var(--ink)" : "var(--ink-soft)",
        fontSize: 13,
        fontWeight: active ? 500 : 400,
        cursor: "pointer",
        marginBottom: -1,
      }}
    >
      {children}
    </button>
  );
}

// ─── GitHub tab ────────────────────────────────────────────────────────────

function GithubTab({
  orgId,
  onClose,
  onCreated,
}: {
  orgId: string;
  onClose: () => void;
  onCreated?: () => void;
}) {
  const [q, setQ] = useState("");
  const [state, setState] = useState<ListState>({ kind: "loading" });
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const debouncedQ = useDebounced(q, 250);

  useEffect(() => {
    let cancelled = false;
    setState((prev) => (prev.kind === "ok" ? prev : { kind: "loading" }));

    async function load() {
      try {
        const url =
          "/api/github/repos" +
          (debouncedQ.trim() ? `?q=${encodeURIComponent(debouncedQ.trim())}` : "");
        const r = await fetch(url, { credentials: "include" });
        if (cancelled) return;
        if (r.status === 409) {
          setState({ kind: "disconnected" });
          return;
        }
        if (!r.ok) {
          setState({ kind: "error", message: `HTTP ${r.status}` });
          return;
        }
        const json = (await r.json()) as Repo[];
        if (!cancelled) setState({ kind: "ok", repos: json });
      } catch (e) {
        if (!cancelled) {
          setState({
            kind: "error",
            message: e instanceof Error ? e.message : String(e),
          });
        }
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [debouncedQ]);

  async function onPick(repo: Repo) {
    setSubmitError(null);
    setSubmittingId(repo.id);
    try {
      const r = await fetch(
        `/api/orgs/${encodeURIComponent(orgId)}/projects`,
        {
          method: "POST",
          credentials: "include",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ githubRepoId: repo.id }),
        }
      );
      if (r.status === 409) {
        // Could be github_disconnected, or org_project_exists.
        let code: string | undefined;
        try {
          const body = (await r.json()) as { error?: { code?: string } };
          code = body?.error?.code;
        } catch {
          /* ignore */
        }
        if (code === "github_disconnected") {
          setState({ kind: "disconnected" });
          return;
        }
        setSubmitError(code ?? `HTTP 409`);
        return;
      }
      if (!r.ok) {
        setSubmitError(`HTTP ${r.status}`);
        return;
      }
      onCreated?.();
      onClose();
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmittingId(null);
    }
  }

  if (state.kind === "disconnected") {
    return (
      <div
        style={{
          padding: 16,
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-lg)",
          background: "var(--warn-bg)",
          color: "var(--ink-soft)",
          fontSize: 14,
          lineHeight: 1.5,
        }}
      >
        Your GitHub connection is missing.{" "}
        <a
          href="/auth"
          style={{
            color: "var(--accent)",
            textDecoration: "none",
            fontWeight: 500,
          }}
        >
          Reconnect
        </a>
        .
      </div>
    );
  }

  const disabled = submittingId !== null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <input
        type="text"
        placeholder="Search your repos…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        disabled={disabled}
        autoFocus
        style={{
          padding: "10px 12px",
          fontSize: 14,
          fontFamily: "inherit",
          background: "var(--paper)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-sm)",
          color: "var(--ink)",
          width: "100%",
          boxSizing: "border-box",
        }}
      />

      {submitError && (
        <div
          className="cf-mono"
          style={{
            padding: "8px 12px",
            fontSize: 12,
            color: "var(--danger)",
            background: "var(--warn-bg)",
            border: "1px solid var(--rule-3)",
            borderRadius: "var(--r-sm)",
          }}
        >
          {submitError}
        </div>
      )}

      <RepoList
        state={state}
        disabled={disabled}
        submittingId={submittingId}
        onPick={onPick}
      />
    </div>
  );
}

function RepoList({
  state,
  disabled,
  submittingId,
  onPick,
}: {
  state: ListState;
  disabled: boolean;
  submittingId: number | null;
  onPick: (r: Repo) => void;
}) {
  if (state.kind === "loading" || state.kind === "idle") {
    return (
      <div
        className="cf-mono"
        style={{ color: "var(--ink-mute)", fontSize: 12, padding: 12 }}
      >
        loading…
      </div>
    );
  }
  if (state.kind === "error") {
    return (
      <p style={{ color: "var(--ink-soft)", fontSize: 14, margin: 0 }}>
        Couldn't load repos: {state.message}
      </p>
    );
  }
  if (state.kind === "disconnected") {
    // Handled by parent; render nothing here.
    return null;
  }
  if (state.repos.length === 0) {
    return (
      <p
        className="cf-mono"
        style={{ color: "var(--ink-mute)", fontSize: 12, margin: 0, padding: 12 }}
      >
        no repos match
      </p>
    );
  }
  return (
    <div
      style={{
        border: "1px solid var(--rule-3)",
        borderRadius: "var(--r-lg)",
        background: "var(--surface-2)",
        overflow: "auto",
        maxHeight: 360,
      }}
    >
      {state.repos.map((r, idx) => {
        const isBusy = submittingId === r.id;
        return (
          <button
            key={r.id}
            type="button"
            disabled={disabled}
            onClick={() => onPick(r)}
            style={{
              width: "100%",
              textAlign: "left",
              padding: "12px 16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
              background: "transparent",
              border: "none",
              borderTop: idx === 0 ? "none" : "1px solid var(--rule)",
              color: "var(--ink)",
              cursor: disabled ? (isBusy ? "wait" : "not-allowed") : "pointer",
              opacity: disabled && !isBusy ? 0.6 : 1,
              fontFamily: "inherit",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
              <span
                style={{
                  fontSize: 14,
                  fontWeight: 500,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {r.full_name}
              </span>
              <span
                className="cf-mono"
                style={{ fontSize: 11, color: "var(--ink-mute)" }}
              >
                {r.default_branch} · updated{" "}
                {new Date(r.updated_at).toLocaleDateString()}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
              {r.private ? <Pill tone="ink">private</Pill> : null}
              {isBusy ? (
                <span
                  className="cf-mono"
                  style={{ fontSize: 11, color: "var(--ink-mute)" }}
                >
                  importing…
                </span>
              ) : null}
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ─── Local-folder tab (stub for Task 16) ───────────────────────────────────

function LocalTab() {
  return (
    <div
      style={{
        padding: 20,
        border: "1px dashed var(--rule-3)",
        borderRadius: "var(--r-lg)",
        background: "var(--paper)",
        textAlign: "center",
        color: "var(--ink-soft)",
        fontSize: 14,
        lineHeight: 1.6,
      }}
    >
      Open the Crawfish desktop app to import a local folder.
    </div>
  );
}

// ─── Helpers ───────────────────────────────────────────────────────────────

function useDebounced<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}
