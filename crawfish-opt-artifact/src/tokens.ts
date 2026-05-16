// Approximate token counter — matches the rest of the opt suite (~4 chars/token).

export function approxTokens(text: string): number {
  if (!text) return 0;
  return Math.max(1, Math.ceil(text.length / 4));
}
