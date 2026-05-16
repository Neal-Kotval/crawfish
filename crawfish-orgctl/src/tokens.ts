/**
 * Cheap token estimator — bytes/4. Matches the heuristic used by sibling
 * crawfish optimizers so the `tokens_used` numbers are cross-comparable.
 * Crawfish optimizer contract v1.0: every tool response includes
 * `tokens_used` estimated from the serialized payload.
 */
export function estimateTokens(s: string): number {
  return Math.max(1, Math.ceil(s.length / 4));
}

/** Compute `tokens_used` for an already-built response payload. */
export function tokensOf(payload: unknown): number {
  return estimateTokens(JSON.stringify(payload));
}
