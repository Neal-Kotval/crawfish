// Approximate token counter. Matches the crawfish-opt-codebase heuristic so
// numbers across optimizers are comparable. ~4 chars/token plus a tiny
// overhead for whitespace runs.

export function approxTokens(text: string): number {
  if (!text) return 0;
  return Math.max(1, Math.ceil(text.length / 4));
}
