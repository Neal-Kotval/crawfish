const DEFAULT_PATTERNS: RegExp[] = [
  /sk-(proj-)?[A-Za-z0-9_-]{20,}/g,
  /sk_live_[A-Za-z0-9]{16,}/g,
  /sk_test_[A-Za-z0-9]{16,}/g,
  /xox[baprs]-[A-Za-z0-9-]{10,}/g,                // Slack
  /ghp_[A-Za-z0-9]{30,}/g,                         // GitHub PAT
  /AKIA[0-9A-Z]{16}/g,                             // AWS access key
  /AIza[0-9A-Za-z_-]{30,}/g,                       // Google
  /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g, // JWT
];

export function redact(text: string, userPatterns: RegExp[]): string {
  let out = text;
  for (const p of [...DEFAULT_PATTERNS, ...userPatterns]) {
    out = out.replace(p, "[REDACTED]");
  }
  return out;
}
