/**
 * Auth hooks + <RequireAuth> route guard.
 *
 * Wraps Clerk's useUser/useAuth into a unified useCurrentUser() shape so
 * downstream components don't branch on CLERK_ENABLED. Dev-mode returns a
 * stable fake user (honoring localStorage.cf_dev_user if set).
 */
import React from "react";
import { Navigate } from "react-router-dom";
import { useUser as clerkUseUser, useAuth as clerkUseAuth } from "@clerk/clerk-react";
import { CLERK_ENABLED } from "./clerk";

export type CurrentUser = {
  id: string;
  email: string;
  name: string;
  isSignedIn: boolean;
  isLoaded: boolean;
};

export function useCurrentUser(): CurrentUser {
  if (CLERK_ENABLED) {
    // Safe to call hooks unconditionally — CLERK_ENABLED is a build-time
    // constant from import.meta.env, so this branch is stable across renders.
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { user, isLoaded, isSignedIn } = clerkUseUser();
    return {
      id: user?.id ?? "",
      email: user?.primaryEmailAddress?.emailAddress ?? "",
      name:
        user?.fullName ??
        user?.firstName ??
        user?.username ??
        user?.primaryEmailAddress?.emailAddress ??
        "",
      isSignedIn: Boolean(isSignedIn),
      isLoaded: Boolean(isLoaded),
    };
  }
  const devEmail =
    (typeof localStorage !== "undefined" && localStorage.getItem("cf_dev_user")) || "dev@local";
  return {
    id: "dev-user",
    email: devEmail,
    name: devEmail.split("@")[0] || "dev",
    isSignedIn: true,
    isLoaded: true,
  };
}

export function useAuthToken(): () => Promise<string | null> {
  if (CLERK_ENABLED) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    const { getToken } = clerkUseAuth();
    return async () => {
      try {
        return await getToken();
      } catch {
        return null;
      }
    };
  }
  return async () => null;
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useCurrentUser();
  if (!isLoaded) {
    return (
      <div
        className="cf"
        style={{
          minHeight: "100vh",
          background: "var(--paper)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span
          className="cf-eyebrow"
          style={{ color: "var(--ink-faint)", fontSize: 11, letterSpacing: "0.08em" }}
        >
          loading…
        </span>
      </div>
    );
  }
  if (!isSignedIn) return <Navigate to="/signin" replace />;
  return <>{children}</>;
}
