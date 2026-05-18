/**
 * Build the "Open in Dash" URL.
 *
 * In dev, point at the dash-web SPA on http://localhost:7881 (or whatever
 * VITE_DEV_DASH_URL says) so the user doesn't have to rebuild and reinstall
 * the Tauri app on every change. This is also what Playwright targets.
 *
 * In prod (no dev URL set, not import.meta.env.DEV), use the
 * crawfish-dash:// custom scheme that the bundled .app registers with the OS.
 */

const DEV_DASH_URL = (import.meta.env.VITE_DEV_DASH_URL as string | undefined)?.trim();

export type DashLinkOpts = {
  org: string;
  user?: string;
  name?: string;
};

export function isDevDashEnabled(): boolean {
  return Boolean(DEV_DASH_URL) || Boolean(import.meta.env.DEV);
}

function devDashBase(): string {
  // Explicit override beats the convention.
  if (DEV_DASH_URL) return DEV_DASH_URL.replace(/\/+$/, "");
  return "http://localhost:7881";
}

export function buildDashLink({ org, user, name }: DashLinkOpts): string {
  const params = new URLSearchParams({ org });
  if (user) params.set("user", user);
  if (name) params.set("name", name);
  if (isDevDashEnabled()) {
    return `${devDashBase()}/canvas?${params.toString()}`;
  }
  return `crawfish-dash://link?${params.toString()}`;
}

/** target attribute for <a> — dev URL opens in a new tab; custom scheme is "self". */
export function dashLinkTarget(): string | undefined {
  return isDevDashEnabled() ? "_blank" : undefined;
}
