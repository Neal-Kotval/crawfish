import { test } from "node:test";
import assert from "node:assert/strict";
import { redact } from "../src/redact.js";

test("redacts a stripe-style secret key", () => {
  const out = redact("token sk_live_abcdefghijklmnopqrstuvwx hi", []);
  assert.match(out, /\[REDACTED\]/);
  assert.doesNotMatch(out, /sk_live_abcdef/);
});

test("redacts an OpenAI-style key", () => {
  const out = redact("OPENAI_API_KEY=sk-proj-aaaaaaaaaaaaaaaaaaaaaaaa", []);
  assert.match(out, /\[REDACTED\]/);
});

test("user-supplied patterns extend the default set", () => {
  const out = redact("internal-token-XYZ", [/internal-token-[A-Z]+/]);
  assert.match(out, /\[REDACTED\]/);
});

test("leaves normal prose alone", () => {
  const out = redact("the quick brown fox", []);
  assert.equal(out, "the quick brown fox");
});
