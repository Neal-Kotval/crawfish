/**
 * Auth page — Clerk widget when VITE_CLERK_PUBLISHABLE_KEY is set, façade
 * when it isn't. The façade still works in dev: "Continue with GitHub"
 * stamps localStorage.cf_dev_user and routes to /.
 */
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { SignIn, SignUp } from "@clerk/clerk-react";
import { CLERK_ENABLED, clerkAppearance } from "../lib/clerk";

// GitHub-only lock: hide email/password form, divider, footer, and all
// social buttons except GitHub. Merges atop the shared clerkAppearance.
const githubOnlyAppearance = {
  ...clerkAppearance,
  elements: {
    ...(clerkAppearance as { elements?: Record<string, unknown> }).elements,
    formContainer: { display: "none" },
    formFieldRow: { display: "none" },
    formButtonPrimary: { display: "none" },
    dividerRow: { display: "none" },
    dividerText: { display: "none" },
    footer: { display: "none" },
    footerAction: { display: "none" },
    socialButtonsBlockButton: { display: "none" },
    socialButtonsBlockButton__github: { display: "flex" },
  },
} as const;

export function Auth({ mode }: { mode: "signin" | "signup" }) {
  const isSignup = mode === "signup";
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // When the dash sends a user here via /signin?return-to=dash, bounce them
  // to /link-dash after sign-in so we can deep-link them back to dash with
  // their identity baked into the URL.
  const returnTo = searchParams.get("return-to");
  const afterAuthUrl = returnTo === "dash" ? "/link-dash" : "/";

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
          maxWidth: CLERK_ENABLED ? 460 : 420,
          background: "var(--surface-2)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-lg)",
          padding: CLERK_ENABLED ? 28 : 32,
          boxShadow: "var(--shadow-md)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: 6,
              background: "var(--ink)",
              color: "var(--accent)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "var(--ff-display)",
              fontSize: 16,
              fontWeight: 700,
              letterSpacing: "-0.04em",
            }}
          >
            cf
          </div>
          <span style={{ fontWeight: 600, fontSize: 17, letterSpacing: "-0.012em" }}>Crawfish</span>
        </div>

        {CLERK_ENABLED ? (
          isSignup ? (
            <SignUp
              routing="path"
              path="/signup"
              signInUrl="/signin"
              afterSignUpUrl={afterAuthUrl}
              appearance={githubOnlyAppearance}
            />
          ) : (
            <SignIn
              routing="path"
              path="/signin"
              signUpUrl="/signup"
              afterSignInUrl={afterAuthUrl}
              appearance={githubOnlyAppearance}
            />
          )
        ) : (
          <DevFacade isSignup={isSignup} onContinue={() => {
            localStorage.setItem("cf_dev_user", "dev@local");
            navigate(afterAuthUrl);
          }} />
        )}
      </div>
    </div>
  );
}

function DevFacade({ isSignup, onContinue }: { isSignup: boolean; onContinue: () => void }) {
  return (
    <>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 28,
          letterSpacing: "-0.025em",
          margin: 0,
        }}
      >
        {isSignup ? "Create your account" : "Welcome back"}
      </h1>

      <p style={{ color: "var(--ink-mute)", fontSize: 13, marginTop: 8, marginBottom: 22 }}>
        {isSignup ? "Two minutes to your first agent." : "Sign in to keep building your company."}
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          onContinue();
        }}
      >
        <button
          type="submit"
          className="cfp-btn cfp-btn--ink"
          style={{ width: "100%", justifyContent: "center", padding: "10px 14px" }}
        >
          Continue with GitHub →
        </button>
      </form>

      <p style={{ color: "var(--ink-mute)", fontSize: 12, marginTop: 18, textAlign: "center" }}>
        {isSignup ? (
          <>
            Already have an account?{" "}
            <Link to="/signin" style={{ color: "var(--accent)" }}>
              Sign in
            </Link>
          </>
        ) : (
          <>
            New to Crawfish?{" "}
            <Link to="/signup" style={{ color: "var(--accent)" }}>
              Create an account
            </Link>
          </>
        )}
      </p>

      <p
        className="cf-mono"
        style={{
          textAlign: "center",
          fontSize: 10,
          color: "var(--ink-faint)",
          marginTop: 22,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
        }}
      >
        dev mode · set VITE_CLERK_PUBLISHABLE_KEY for real auth
      </p>
    </>
  );
}
