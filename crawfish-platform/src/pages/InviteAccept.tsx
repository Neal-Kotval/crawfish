/**
 * InviteAccept — /invites/:code landing page.
 *
 * Renders outside the RequireAuth guard so a not-yet-signed-in invitee
 * can see what they're being invited to before they sign in. Three states:
 *   1. not signed in           → sign-in CTA
 *   2. signed in, email match  → accept button
 *   3. signed in, email mismatch → sign-out CTA
 *
 * Distinct UX for 404 (unknown), 410 (expired/redeemed), 403 (email mismatch).
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useClerk } from "@clerk/clerk-react";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import {
  acceptInvite,
  getInvite,
  type ApiError,
  type InvitePreview,
} from "../lib/api";
import { useCurrentUser } from "../lib/useAuth";
import { CLERK_ENABLED } from "../lib/clerk";

type State =
  | { kind: "loading" }
  | { kind: "ok"; preview: InvitePreview }
  | { kind: "not_found" }
  | { kind: "expired"; message: string }
  | { kind: "error"; message: string };

export function InviteAccept() {
  const { code = "" } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const me = useCurrentUser();
  const [state, setState] = useState<State>({ kind: "loading" });
  const [accepting, setAccepting] = useState(false);
  const [acceptError, setAcceptError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    getInvite(code)
      .then((preview) => {
        if (!cancelled) setState({ kind: "ok", preview });
      })
      .catch((e) => {
        if (cancelled) return;
        const err = e as ApiError;
        if (err.status === 404) return setState({ kind: "not_found" });
        if (err.status === 410) {
          return setState({
            kind: "expired",
            message: err.message || "This invite is no longer valid.",
          });
        }
        setState({ kind: "error", message: err.message || "Failed to load invite." });
      });
    return () => {
      cancelled = true;
    };
  }, [code]);

  async function onAccept() {
    setAcceptError(null);
    setAccepting(true);
    try {
      const result = await acceptInvite(code);
      navigate(`/orgs/${result.org.slug}/canvas`, { replace: true });
    } catch (e) {
      const err = e as ApiError;
      setAcceptError(err.message || "Failed to accept invite.");
      setAccepting(false);
    }
  }

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
          maxWidth: 480,
          background: "var(--surface-2)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-lg)",
          padding: 28,
          boxShadow: "var(--shadow-sm)",
        }}
      >
        <InviteBody
          state={state}
          me={me}
          code={code}
          accepting={accepting}
          acceptError={acceptError}
          onAccept={onAccept}
        />
      </div>
    </div>
  );
}

function InviteBody({
  state,
  me,
  code,
  accepting,
  acceptError,
  onAccept,
}: {
  state: State;
  me: ReturnType<typeof useCurrentUser>;
  code: string;
  accepting: boolean;
  acceptError: string | null;
  onAccept: () => void;
}) {
  if (state.kind === "loading") {
    return (
      <>
        <Eyebrow>Invitation</Eyebrow>
        <p className="cf-mono" style={{ marginTop: 8, fontSize: 12, color: "var(--ink-mute)" }}>
          loading…
        </p>
      </>
    );
  }

  if (state.kind === "not_found") {
    return (
      <>
        <Eyebrow>Invitation not found</Eyebrow>
        <Heading>Unknown invite link</Heading>
        <Body>
          We couldn't find an invitation with this code. It may have been revoked, or the link may
          have been mistyped.
        </Body>
      </>
    );
  }

  if (state.kind === "expired") {
    return (
      <>
        <Eyebrow>Invitation no longer valid</Eyebrow>
        <Heading>This invite has expired</Heading>
        <Body>{state.message} Ask whoever invited you to send a new one.</Body>
      </>
    );
  }

  if (state.kind === "error") {
    return (
      <>
        <Eyebrow>Something went wrong</Eyebrow>
        <Heading>Couldn't load invite</Heading>
        <Body>{state.message}</Body>
      </>
    );
  }

  const { preview } = state;
  const inviteEmail = preview.email.toLowerCase();
  const meEmail = (me.email || "").toLowerCase();
  const emailMatches = meEmail === inviteEmail;

  return (
    <>
      <Eyebrow>Invitation to {preview.org.name}</Eyebrow>
      <Heading>Join {preview.org.name}</Heading>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
        <Pill tone="ink">{preview.role}</Pill>
        <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
          for {preview.email}
        </span>
      </div>
      <Body>
        Expires {new Date(preview.expiresAt).toLocaleDateString()}.
      </Body>

      {!me.isSignedIn && (
        <SigninCTA inviteEmail={preview.email} code={code} />
      )}

      {me.isSignedIn && emailMatches && (
        <>
          <button
            type="button"
            onClick={onAccept}
            disabled={accepting}
            className="cfp-btn cfp-btn--primary"
            style={primaryBtn(accepting)}
          >
            {accepting ? "Joining…" : `Accept and join ${preview.org.name}`}
          </button>
          {acceptError && (
            <div
              className="cf-mono"
              style={{
                marginTop: 12,
                fontSize: 12,
                color: "var(--danger)",
              }}
            >
              {acceptError}
            </div>
          )}
        </>
      )}

      {me.isSignedIn && !emailMatches && (
        <EmailMismatch inviteEmail={preview.email} currentEmail={me.email} />
      )}
    </>
  );
}

function Heading({ children }: { children: React.ReactNode }) {
  return (
    <h1
      style={{
        fontFamily: "var(--ff-display)",
        fontWeight: 500,
        fontSize: 28,
        letterSpacing: "-0.022em",
        margin: "6px 0 12px",
      }}
    >
      {children}
    </h1>
  );
}

function Body({ children }: { children: React.ReactNode }) {
  return (
    <p style={{ color: "var(--ink-soft)", fontSize: 14, lineHeight: 1.6, margin: "0 0 20px" }}>
      {children}
    </p>
  );
}

// Pair with className="cfp-btn cfp-btn--primary" so the button matches
// the vermillion primary CTA in onboarding and Auth. Width + cursor are
// the only inline overrides needed.
function primaryBtn(disabled: boolean): React.CSSProperties {
  return {
    width: "100%",
    justifyContent: "center",
    opacity: disabled ? 0.6 : 1,
    cursor: disabled ? "wait" : "pointer",
  };
}

function SigninCTA({ inviteEmail, code }: { inviteEmail: string; code: string }) {
  const redirect = encodeURIComponent(`/invites/${code}`);
  return (
    <>
      <p style={{ color: "var(--ink-soft)", fontSize: 14, marginBottom: 12 }}>
        Sign in as <strong>{inviteEmail}</strong> to accept this invitation.
      </p>
      <a
        href={`/signin?redirect=${redirect}`}
        className="cfp-btn cfp-btn--primary"
        style={{
          ...primaryBtn(false),
          textDecoration: "none",
        }}
      >
        Sign in to continue
      </a>
    </>
  );
}

function EmailMismatch({
  inviteEmail,
  currentEmail,
}: {
  inviteEmail: string;
  currentEmail: string;
}) {
  // CLERK_ENABLED is a build-time constant, so the hook choice is stable across
  // renders. Calling useClerk only when the provider is mounted avoids a runtime
  // throw in dev mode.
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const clerk = CLERK_ENABLED ? useClerk() : null;
  const [signingOut, setSigningOut] = useState(false);

  async function onSignOut() {
    setSigningOut(true);
    try {
      if (clerk) {
        await clerk.signOut({ redirectUrl: window.location.pathname });
      } else {
        // dev-mode: nothing to sign out of, just nudge the cf_dev_user value.
        try {
          localStorage.removeItem("cf_dev_user");
        } catch {
          /* ignore */
        }
        window.location.reload();
      }
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <>
      <p style={{ color: "var(--ink-soft)", fontSize: 14, marginBottom: 12 }}>
        This invite is for <strong>{inviteEmail}</strong>. You're signed in as{" "}
        <strong>{currentEmail || "an unknown user"}</strong>. Sign out and back in as the invited
        address to continue.
      </p>
      <button
        type="button"
        onClick={onSignOut}
        disabled={signingOut}
        className="cfp-btn cfp-btn--primary"
        style={primaryBtn(signingOut)}
      >
        {signingOut ? "Signing out…" : "Sign out"}
      </button>
    </>
  );
}
