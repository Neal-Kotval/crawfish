/**
 * LinkDash — hands the just-signed-in user back to the desktop dash.
 *
 * Reached when the user clicked "Sign in" from dash's SignInGate, signed in
 * on the platform, and now needs to be returned to the local dash with their
 * identity. We construct `http://localhost:7881/?user=<email>&name=<name>` (or
 * the prod equivalent) — dash's App.tsx writes cf-linked-user on first paint
 * and drops the SignInGate.
 *
 * Renders a brief "Returning you to Dash…" card with a manual fallback link
 * so the user is never stranded if the auto-redirect fails or pop-up blocker
 * trips.
 */
import { useEffect } from "react";
import { useCurrentUser } from "../lib/useAuth";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";

const DASH_URL =
  (import.meta.env.VITE_DASH_URL as string | undefined) ?? "http://localhost:7881";

export function LinkDash() {
  const user = useCurrentUser();

  const targetUrl = (() => {
    if (!user.isLoaded || !user.isSignedIn) return null;
    const params = new URLSearchParams();
    if (user.email) params.set("user", user.email);
    if (user.name) params.set("name", user.name);
    return `${DASH_URL}/?${params.toString()}`;
  })();

  useEffect(() => {
    if (!targetUrl) return;
    // Slight delay so the user reads the "Returning you to Dash…" message
    // before the redirect fires. Tauri custom-scheme handlers are a future
    // upgrade — for now this is a same-origin-shaped HTTP URL.
    const t = window.setTimeout(() => {
      window.location.replace(targetUrl);
    }, 600);
    return () => window.clearTimeout(t);
  }, [targetUrl]);

  return (
    <div
      className="cf"
      style={{
        minHeight: "100vh",
        background: "var(--paper)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 420,
          background: "var(--surface-2)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-lg)",
          padding: 28,
          boxShadow: "var(--shadow-md)",
          textAlign: "center",
        }}
      >
        <Eyebrow style={{ marginBottom: 12 }}>Linking Dash</Eyebrow>
        <h1
          style={{
            fontFamily: "var(--ff-display)",
            fontWeight: 500,
            fontSize: 28,
            letterSpacing: "-0.025em",
            margin: "0 0 10px",
          }}
        >
          Returning you to Dash…
        </h1>
        <p style={{ margin: "0 0 18px", color: "var(--ink-soft)", fontSize: 14, lineHeight: 1.5 }}>
          Signed in as <b>{user.email || "—"}</b>. Bouncing you back to the
          local Dash app now.
        </p>
        {targetUrl ? (
          <a
            href={targetUrl}
            className="cfp-btn cf-touch-target"
            style={{
              background: "var(--accent)",
              color: "#fff",
              border: "1px solid var(--accent)",
              textDecoration: "none",
              padding: "12px 20px",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            Open Dash →
          </a>
        ) : (
          <div className="cf-mono" style={{ fontSize: 12, color: "var(--ink-mute)" }}>
            loading session…
          </div>
        )}
        <div
          className="cf-mono"
          style={{ fontSize: 11, color: "var(--ink-mute)", marginTop: 18, wordBreak: "break-all" }}
        >
          {targetUrl ?? DASH_URL}
        </div>
      </div>
    </div>
  );
}
