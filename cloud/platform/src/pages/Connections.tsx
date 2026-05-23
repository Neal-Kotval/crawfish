/**
 * Connections — per-provider integration status for an org.
 *
 * Lists GitHub + Linear with a connected/disconnected Pill. For Linear when
 * disconnected, a "Connect Linear" button hits the server connect route and
 * redirects the browser to the returned authorize URL. The browser only ever
 * receives the authorize URL — the client_secret and tokens stay server-side
 * (T-20-07).
 */
import { useEffect, useState } from "react";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import { formatApiError } from "@crawfish/ui/lib/formatApiError";
import { listIntegrations, connectProvider, type Integration } from "../lib/api";

type LoadState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; integrations: Integration[] };

const PROVIDER_LABEL: Record<string, string> = { github: "GitHub", linear: "Linear" };

export function Connections({ orgId }: { orgId: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [connecting, setConnecting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    listIntegrations(orgId)
      .then((integrations) => {
        if (!cancelled) setState({ kind: "ok", integrations });
      })
      .catch((e) => {
        if (!cancelled) setState({ kind: "error", message: formatApiError(e).body });
      });
    return () => {
      cancelled = true;
    };
  }, [orgId]);

  async function onConnectLinear() {
    setConnecting(true);
    try {
      const { authorizeUrl } = await connectProvider(orgId, "linear");
      window.location.assign(authorizeUrl);
    } catch (e) {
      setState({ kind: "error", message: formatApiError(e).body });
      setConnecting(false);
    }
  }

  return (
    <main className="cfp-shell__main" style={{ padding: 28, maxWidth: 720 }}>
      <Eyebrow>{orgId} · connections</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 32,
          letterSpacing: "-0.025em",
          margin: "6px 0 8px",
        }}
      >
        Connections
      </h1>
      <p style={{ color: "var(--ink-soft)", fontSize: 14, maxWidth: 560, marginBottom: 24 }}>
        Connect issue trackers to auto-load issues into your projects. GitHub uses your
        sign-in connection; Linear connects per workspace.
      </p>

      {state.kind === "loading" && (
        <div className="cf-mono" style={{ color: "var(--ink-mute)", fontSize: 12 }}>
          loading…
        </div>
      )}

      {state.kind === "error" && (
        <div
          style={{
            padding: "14px 16px",
            background: "var(--warn-bg)",
            border: "1px solid var(--rule-3)",
            borderRadius: "var(--r-md)",
            maxWidth: 560,
          }}
        >
          <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 4 }}>
            Couldn't load connections
          </div>
          <div style={{ fontSize: 13, color: "var(--ink-soft)" }}>{state.message}</div>
        </div>
      )}

      {state.kind === "ok" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {state.integrations.map((it) => (
            <div
              key={it.provider}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 16,
                padding: 16,
                border: "1px solid var(--rule-3)",
                borderRadius: "var(--r-lg)",
                background: "var(--surface-2)",
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span style={{ fontSize: 15, fontWeight: 500 }}>
                  {PROVIDER_LABEL[it.provider] ?? it.provider}
                </span>
                <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
                  {it.connected
                    ? it.externalWorkspaceName
                      ? `connected · ${it.externalWorkspaceName}`
                      : "connected"
                    : "not connected"}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <Pill tone={it.connected ? "accent" : "neutral"}>
                  {it.connected ? "connected" : "disconnected"}
                </Pill>
                {it.provider === "linear" && !it.connected && (
                  <button
                    type="button"
                    onClick={onConnectLinear}
                    disabled={connecting}
                    className="cfp-btn cfp-btn--primary"
                    style={{ cursor: connecting ? "default" : "pointer" }}
                  >
                    {connecting ? "Redirecting…" : "Connect Linear"}
                  </button>
                )}
                {it.provider === "github" && !it.connected && (
                  <a href="/auth" className="cfp-btn" style={{ textDecoration: "none" }}>
                    Reconnect GitHub
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
