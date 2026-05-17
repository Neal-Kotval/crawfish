/**
 * Auth page — Clerk widget when VITE_CLERK_PUBLISHABLE_KEY is set, façade
 * when it isn't. The façade still works in dev: "Continue with GitHub"
 * stamps localStorage.cf_dev_user and routes to /.
 */
import { Link, useNavigate } from "react-router-dom";
import { SignIn, SignUp } from "@clerk/clerk-react";
import { CLERK_ENABLED, clerkAppearance } from "../lib/clerk";

export function Auth({ mode }: { mode: "signin" | "signup" }) {
  const isSignup = mode === "signup";
  const navigate = useNavigate();

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
          width: CLERK_ENABLED ? 460 : 420,
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
              afterSignUpUrl="/"
              appearance={clerkAppearance}
            />
          ) : (
            <SignIn
              routing="path"
              path="/signin"
              signUpUrl="/signup"
              afterSignInUrl="/"
              appearance={clerkAppearance}
            />
          )
        ) : (
          <DevFacade isSignup={isSignup} onContinue={() => {
            localStorage.setItem("cf_dev_user", "dev@local");
            navigate("/");
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

      <button
        type="button"
        className="cfp-btn cfp-btn--ink"
        style={{ width: "100%", justifyContent: "center", padding: "10px 14px" }}
        onClick={onContinue}
      >
        Continue with GitHub →
      </button>

      <div
        className="cf-mono"
        style={{
          textAlign: "center",
          fontSize: 11,
          color: "var(--ink-faint)",
          margin: "18px 0",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
        OR
        <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
      </div>

      <input
        type="email"
        placeholder="you@company.com"
        style={{
          width: "100%",
          padding: "10px 12px",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-sm)",
          fontFamily: "var(--ff-sans)",
          fontSize: 14,
          background: "var(--surface)",
          color: "var(--ink)",
        }}
      />
      <button
        type="button"
        className="cfp-btn cfp-btn--primary"
        style={{
          width: "100%",
          justifyContent: "center",
          padding: "10px 14px",
          marginTop: 10,
        }}
        onClick={onContinue}
      >
        {isSignup ? "Send sign-up link" : "Send magic link"}
      </button>

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
