// Design tokens for crawfish-lens (and dash, P2). The Apple feel comes from
// SF-style typography, generous spacing, restrained color, and smooth motion —
// not from chrome. Keep this file small and authoritative.

export const tokens = {
  font: {
    family:
      '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Helvetica Neue", system-ui, sans-serif',
    mono: 'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace',
    weight: { regular: 400, medium: 500, semibold: 600, bold: 700 },
  },
  size: {
    // 4px scale; matches macOS density.
    1: "4px",
    2: "8px",
    3: "12px",
    4: "16px",
    5: "20px",
    6: "24px",
    7: "32px",
    8: "40px",
    9: "56px",
  },
  radius: {
    sm: "6px",
    md: "10px",
    lg: "14px",
    xl: "20px",
  },
  motion: {
    fast: "120ms cubic-bezier(0.4, 0, 0.2, 1)",
    normal: "200ms cubic-bezier(0.4, 0, 0.2, 1)",
    slow: "320ms cubic-bezier(0.4, 0, 0.2, 1)",
  },
  // Token-bucket colors. Used in TokenBar and elsewhere.
  // These need to contrast on both light and dark; chosen to match SF system colors.
  bucket: {
    input: "var(--cf-color-bucket-input)",
    output: "var(--cf-color-bucket-output)",
    cacheRead: "var(--cf-color-bucket-cache-read)",
    cacheWrite: "var(--cf-color-bucket-cache-write)",
  },
} as const;

export type Tokens = typeof tokens;
