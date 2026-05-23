// Theme storage + DOM application for the signed-in platform SPA.
// Default is dark; the user can switch to light via Settings → Appearance.
// The choice is persisted in localStorage (per-origin) and reapplied on every
// page load via `applyTheme` — called from main.tsx before React mounts so
// there's no light-to-dark flash on first paint.
//
// This mirrors desktop/dash's src/lib/theme.ts contract (same storage key,
// same `cf-theme-change` event) so the two surfaces behave identically.

export type Theme = "light" | "dark";

const STORAGE_KEY = "cf-theme";

export function getStoredTheme(): Theme {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === "dark" || v === "light") return v;
  } catch {}
  return "dark";
}

export function setStoredTheme(theme: Theme): void {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {}
  applyTheme(theme);
  window.dispatchEvent(new CustomEvent("cf-theme-change", { detail: theme }));
}

export function applyTheme(theme: Theme = getStoredTheme()): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}
