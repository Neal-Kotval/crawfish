// Artifact store at `~/.crawfish/artifacts/`. Each artifact is a single
// file named by a content hash, plus a tiny JSON sidecar with metadata.
//
// Goal: large tool results write here. The model gets back
//   { artifact_id, summary, next_action }
// — a few hundred tokens instead of the full payload. Later calls can
// `artifact_read({ id, offset, length })` to fetch slices.

import { createHash, randomUUID } from "node:crypto";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  statSync,
  writeFileSync,
  appendFileSync,
} from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function root(): string {
  const d = join(homedir(), ".crawfish", "artifacts");
  if (!existsSync(d)) mkdirSync(d, { recursive: true });
  return d;
}

export interface ArtifactMeta {
  id: string;
  bytes: number;
  hash_sha256: string;
  mime: string;
  source_tool?: string;
  created_at: string;
}

export interface ArtifactPut {
  artifact_id: string;
  bytes: number;
  /** Heuristic summary — caller may override. */
  summary: string;
  /** Suggested next action — e.g. "artifact_grep(...)". */
  next_action: string;
}

function metaPath(id: string): string {
  return join(root(), `${id}.json`);
}

function bodyPath(id: string): string {
  return join(root(), `${id}.bin`);
}

/**
 * Store a string or buffer payload. Returns the artifact envelope a model
 * sees in place of the full content.
 */
export function putArtifact(payload: string | Buffer, opts?: {
  mime?: string;
  source_tool?: string;
  summary?: string;
}): ArtifactPut {
  const buf = Buffer.isBuffer(payload) ? payload : Buffer.from(payload, "utf8");
  const hash = createHash("sha256").update(buf).digest("hex");
  // Use the first 16 hex chars + a random suffix so collision-resistant
  // but human-quotable in logs.
  const id = `${hash.slice(0, 16)}-${randomUUID().slice(0, 8)}`;

  const meta: ArtifactMeta = {
    id,
    bytes: buf.length,
    hash_sha256: hash,
    mime: opts?.mime ?? "text/plain",
    source_tool: opts?.source_tool,
    created_at: new Date().toISOString(),
  };
  writeFileSync(bodyPath(id), buf);
  writeFileSync(metaPath(id), JSON.stringify(meta, null, 2));

  const summary = opts?.summary ?? heuristicSummary(buf);
  return {
    artifact_id: id,
    bytes: buf.length,
    summary,
    next_action:
      `Call artifact_read({ id: "${id}", offset, length }) for a slice, ` +
      `or artifact_grep({ id: "${id}", pattern }) to search.`,
  };
}

export function readArtifact(id: string, offset = 0, length = 4096): {
  meta: ArtifactMeta;
  text: string;
  is_truncated: boolean;
} {
  const meta = JSON.parse(readFileSync(metaPath(id), "utf8")) as ArtifactMeta;
  const buf = readFileSync(bodyPath(id));
  const end = Math.min(buf.length, offset + length);
  const slice = buf.subarray(offset, end);
  return {
    meta,
    text: slice.toString("utf8"),
    is_truncated: end < buf.length,
  };
}

export function grepArtifact(
  id: string,
  pattern: string,
  n = 20,
): { meta: ArtifactMeta; matches: Array<{ line: number; text: string }>; total: number } {
  const meta = JSON.parse(readFileSync(metaPath(id), "utf8")) as ArtifactMeta;
  const buf = readFileSync(bodyPath(id), "utf8");
  const rx = new RegExp(pattern, "i");
  const lines = buf.split(/\r?\n/);
  const matches: Array<{ line: number; text: string }> = [];
  let total = 0;
  for (let i = 0; i < lines.length; i++) {
    if (!rx.test(lines[i])) continue;
    total++;
    if (matches.length < n) matches.push({ line: i + 1, text: lines[i] });
  }
  return { meta, matches, total };
}

/** Heuristic summary — first sniff for JSON/HTML/log shape, then return a
 *  short rendering tuned to that shape. Pure-text, no LLM call. */
function heuristicSummary(buf: Buffer): string {
  const head = buf.subarray(0, 4096).toString("utf8");
  const trimmed = head.trim();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (Array.isArray(parsed)) {
        return `JSON array, length=${parsed.length}. First element shape: ${shape(parsed[0])}.`;
      }
      const keys = Object.keys(parsed);
      return `JSON object with keys: ${keys.slice(0, 12).join(", ")}${keys.length > 12 ? ", …" : ""}.`;
    } catch {
      /* fall through */
    }
  }
  if (trimmed.startsWith("<")) {
    return `HTML/XML, ${buf.length} bytes. First tags: ${
      Array.from(trimmed.matchAll(/<[a-z][\w-]*/gi))
        .slice(0, 8)
        .map((m) => m[0])
        .join(" ")
    }`;
  }
  const lines = head.split(/\r?\n/);
  return `Text, ${buf.length} bytes, ~${head.split(/\r?\n/).length} lines in first 4KB. First line: ${
    lines[0].slice(0, 140)
  }`;
}

function shape(v: unknown): string {
  if (v === null) return "null";
  if (Array.isArray(v)) return `array[${v.length}]`;
  if (typeof v === "object") {
    const k = Object.keys(v as Record<string, unknown>);
    return `{${k.slice(0, 6).join(",")}${k.length > 6 ? ",…" : ""}}`;
  }
  return typeof v;
}

/** Append a JSONL line to the artifact log — used by lens for audit. */
export function logArtifact(meta: ArtifactMeta): void {
  const p = join(root(), "log.jsonl");
  appendFileSync(p, JSON.stringify(meta) + "\n");
}

export function artifactStats(): { count: number; total_bytes: number } {
  const dir = root();
  let count = 0;
  let total = 0;
  try {
    const fs = require("node:fs") as typeof import("node:fs");
    for (const name of fs.readdirSync(dir)) {
      if (!name.endsWith(".bin")) continue;
      count++;
      total += statSync(join(dir, name)).size;
    }
  } catch {
    /* ignore */
  }
  return { count, total_bytes: total };
}
