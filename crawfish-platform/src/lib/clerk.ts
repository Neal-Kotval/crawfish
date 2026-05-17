/**
 * Clerk env-key helpers + dev-mode fallback flag.
 *
 * When VITE_CLERK_PUBLISHABLE_KEY is set, the app boots in real-auth mode
 * (ClerkProvider wraps the tree, <SignIn>/<SignUp> widgets render).
 * When it's unset, the app runs in dev-mode: a fake user is returned by
 * useCurrentUser() and apiFetch passes X-User-Id instead of a JWT.
 */
export const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;
export const CLERK_ENABLED = Boolean(CLERK_KEY);
export const SERVER_URL =
  (import.meta.env.VITE_SERVER_URL as string | undefined) ?? "http://127.0.0.1:7882";

export const clerkAppearance = {
  variables: {
    colorPrimary: "#c8442b",
    colorBackground: "#ffffff",
    colorText: "#1a1a18",
    colorTextSecondary: "#6f6b62",
    colorInputBackground: "#fbf8f1",
    colorInputText: "#1a1a18",
    borderRadius: "6px",
    fontFamily: "Geist, -apple-system, system-ui, sans-serif",
  },
  elements: {
    card: { boxShadow: "var(--shadow-md)", border: "1px solid var(--rule-3)" },
    formButtonPrimary: { fontWeight: 500, letterSpacing: "-0.005em" },
  },
} as const;
