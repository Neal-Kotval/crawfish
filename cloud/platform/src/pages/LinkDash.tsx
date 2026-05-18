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
import { useEffect, useMemo } from "react";
import { useCurrentUser } from "../lib/useAuth";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";

// The installed Tauri app registers crawfish-dash:// (see desktop/app/src-tauri/
// tauri.conf.json: deep-link.schemes). When the user has the desktop app
// installed, the OS routes this URL to the running app. When they don't, the
// browser silently no-ops; we then fall back to the local dev/web URL.
const DASH_HTTP_URL =
  (import.meta.env.VITE_DASH_URL as string | undefined) ?? "http://localhost:7881";

export function LinkDash() {
  const user = useCurrentUser();

  const { customSchemeUrl, fallbackUrl } = useMemo(() => {
    if (!user.isLoaded || !user.isSignedIn) {
      return { customSchemeUrl: null, fallbackUrl: null };
    }
    const params = new URLSearchParams();
    if (user.email) params.set("user", user.email);
    if (user.name) params.set("name", user.name);
    const qs = params.toString();
    return {
      customSchemeUrl: `crawfish-dash://link?${qs}`,
      fallbackUrl: `${DASH_HTTP_URL}/?${qs}`,
    };
  }, [user.isLoaded, user.isSignedIn, user.email, user.name]);

  useEffect(() => {
    if (!customSchemeUrl || !fallbackUrl) return;
    // 1. Fire the custom scheme first — if the Tauri app is installed, this
    //    is intercepted by the OS and routes to the running app instance.
    // 2. After a short grace period, fall back to the HTTP URL so users
    //    running dash in the browser (or who don't have the app installed)
    //    still get signed in.
    const fireCustom = window.setTimeout(() => {
      try {
        window.location.assign(customSchemeUrl);
      } catch {
        /* ignore — fallback handles it */
      }
    }, 200);
    const fireFallback = window.setTimeout(() => {
      window.location.replace(fallbackUrl);
    }, 1500);
    return () => {
      window.clearTimeout(fireCustom);
      window.clearTimeout(fireFallback);
    };
  }, [customSchemeUrl, fallbackUrl]);

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
        {customSchemeUrl && fallbackUrl ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "center" }}>
            <a
              href={customSchemeUrl}
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
            <a
              href={fallbackUrl}
              className="cf-touch-target"
              style={{
                fontSize: 12,
                color: "var(--ink-mute)",
                textDecoration: "underline",
                padding: "8px 4px",
              }}
            >
              Or open in browser ↗
            </a>
          </div>
        ) : (
          <div className="cf-mono" style={{ fontSize: 12, color: "var(--ink-mute)" }}>
            loading session…
          </div>
        )}
        <div
          className="cf-mono"
          style={{ fontSize: 11, color: "var(--ink-mute)", marginTop: 18, wordBreak: "break-all" }}
        >
          {customSchemeUrl ?? DASH_HTTP_URL}
        </div>
      </div>
    </div>
  );
}
