/**
 * Minimal YAML frontmatter parser and serializer for `.crawfish/tasks/*.md`
 * and `.crawfish/epics/*.md`. We deliberately do not pull a YAML dep — the
 * skill emits a narrow subset (strings, ISO dates, inline arrays). Anything
 * richer is rejected with a descriptive error.
 *
 * Mirrors the parser shape in `desktop/dash/src/server/roadmap.ts` so reader
 * and writer agree on the wire format. If you change one, change the other.
 *
 * NOW-W2: the `criteria` key serialises as a YAML block list-of-maps to
 * accommodate per-task acceptance criteria with optional evidence payloads.
 */

export type CriterionKind = "behavioral" | "test" | "metric" | "preflight" | "manual";

export interface CriterionEvidence {
  kind: CriterionKind;
  [key: string]: unknown;
}

export interface Criterion {
  id: string;
  statement: string;
  kind: CriterionKind;
  evidence?: CriterionEvidence;
}

export const LINK_KINDS = [
  "blocks",
  "depends_on",
  "duplicates",
  "relates_to",
  "subtask_of",
] as const;
export type LinkKind = (typeof LINK_KINDS)[number];

export interface TaskLink {
  kind: LinkKind;
  target_task_id: string;
}

export type FrontmatterValue = string | string[] | number | Criterion[] | TaskLink[];
export type Frontmatter = Record<string, FrontmatterValue>;

export interface ParsedDoc {
  fm: Frontmatter;
  body: string;
}

export function parseFrontmatter(raw: string): ParsedDoc {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) return { fm: {}, body: raw };
  const fm: Frontmatter = {};
  const allLines = match[1].split(/\r?\n/);
  let i = 0;
  while (i < allLines.length) {
    const line = allLines[i];
    if (line.trim() === "" || line.trim().startsWith("#")) {
      i++;
      continue;
    }
    const m = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!m) {
      i++;
      continue;
    }
    const key = m[1];
    const value = m[2].trim();
    if ((key === "criteria" || key === "links") && value === "") {
      // Block-style list-of-maps follows on indented lines.
      const block: string[] = [];
      i++;
      while (i < allLines.length) {
        const nxt = allLines[i];
        if (nxt.trim() === "") {
          block.push(nxt);
          i++;
          continue;
        }
        // Stop when we hit an unindented key:line at column 0.
        if (/^[A-Za-z0-9_-]+:/.test(nxt)) break;
        block.push(nxt);
        i++;
      }
      if (key === "criteria") fm[key] = parseCriteriaBlock(block);
      else fm[key] = parseLinksBlock(block);
      continue;
    }
    if (key === "links" && value === "[]") {
      fm[key] = [] as TaskLink[];
      i++;
      continue;
    }
    if (value === "") {
      fm[key] = "";
    } else if (value.startsWith("[") && value.endsWith("]")) {
      const inner = value.slice(1, -1).trim();
      fm[key] = inner === ""
        ? []
        : inner.split(",").map((s) => s.trim().replace(/^["']|["']$/g, ""));
    } else if (/^-?\d+(\.\d+)?$/.test(value)) {
      fm[key] = Number(value);
    } else {
      fm[key] = value.replace(/^["']|["']$/g, "");
    }
    i++;
  }
  return { fm, body: match[2] };
}

export function serializeFrontmatter(fm: Frontmatter, body: string): string {
  const lines: string[] = ["---"];
  for (const [key, val] of Object.entries(fm)) {
    if (key === "criteria" && Array.isArray(val) && isCriterionArray(val)) {
      if (val.length === 0) {
        lines.push(`${key}: []`);
      } else {
        lines.push(`${key}:`);
        for (const c of val) lines.push(...serializeCriterion(c));
      }
      continue;
    }
    if (key === "links" && Array.isArray(val) && isLinkArray(val)) {
      if (val.length === 0) {
        lines.push(`${key}: []`);
      } else {
        lines.push(`${key}:`);
        for (const l of val) {
          lines.push(`  - kind: ${quoteIfNeeded(l.kind)}`);
          lines.push(`    target_task_id: ${quoteIfNeeded(l.target_task_id)}`);
        }
      }
      continue;
    }
    if (Array.isArray(val)) {
      lines.push(`${key}: [${(val as string[]).map(quoteIfNeeded).join(", ")}]`);
    } else if (typeof val === "number") {
      lines.push(`${key}: ${val}`);
    } else {
      lines.push(`${key}: ${quoteIfNeeded(val as string)}`);
    }
  }
  lines.push("---");
  const bodyPart = body.startsWith("\n") ? body : `\n${body}`;
  return lines.join("\n") + bodyPart;
}

function quoteIfNeeded(s: string): string {
  if (/^[A-Za-z0-9._/-][A-Za-z0-9 ._/:+-]*$/.test(s)) return s;
  return `"${s.replace(/"/g, '\\"')}"`;
}

function isCriterionArray(val: unknown): val is Criterion[] {
  if (!Array.isArray(val)) return false;
  if (val.length === 0) return true;
  const first = val[0] as Record<string, unknown> | null;
  return !!first && typeof first === "object" && "id" in first && "statement" in first && "kind" in first;
}

function serializeCriterion(c: Criterion): string[] {
  const out: string[] = [];
  out.push(`  - id: ${quoteIfNeeded(c.id)}`);
  out.push(`    statement: ${quoteIfNeeded(c.statement)}`);
  out.push(`    kind: ${quoteIfNeeded(c.kind)}`);
  if (c.evidence) {
    out.push(`    evidence:`);
    out.push(`      kind: ${quoteIfNeeded(c.evidence.kind)}`);
    for (const [k, v] of Object.entries(c.evidence)) {
      if (k === "kind") continue;
      out.push(`      ${k}: ${serializeScalar(v)}`);
    }
  }
  return out;
}

function serializeScalar(v: unknown): string {
  if (v === null) return "null";
  if (typeof v === "number") return String(v);
  if (typeof v === "boolean") return String(v);
  if (typeof v === "string") return quoteIfNeeded(v);
  // Fallback for arrays/objects — inline JSON keeps round-trip lossless for nested data.
  return JSON.stringify(v);
}

interface CriterionInProgress {
  id?: string;
  statement?: string;
  kind?: CriterionKind;
  evidence?: Record<string, unknown>;
}

function parseCriteriaBlock(lines: string[]): Criterion[] {
  const out: Criterion[] = [];
  let cur: CriterionInProgress | null = null;
  let inEvidence = false;
  for (const raw of lines) {
    if (raw.trim() === "") continue;
    // New criterion: "  - id: ..."
    const itemMatch = raw.match(/^\s{2}-\s+([A-Za-z0-9_-]+):\s*(.*)$/);
    if (itemMatch) {
      if (cur && cur.id && cur.statement !== undefined && cur.kind) {
        out.push(finalizeCriterion(cur));
      }
      cur = {};
      inEvidence = false;
      assignField(cur, itemMatch[1], itemMatch[2].trim());
      continue;
    }
    // Continuation field at 4-space indent (criterion field).
    const fieldMatch = raw.match(/^\s{4}([A-Za-z0-9_-]+):\s*(.*)$/);
    if (fieldMatch && cur) {
      const key = fieldMatch[1];
      const val = fieldMatch[2].trim();
      if (key === "evidence" && val === "") {
        cur.evidence = {};
        inEvidence = true;
        continue;
      }
      inEvidence = false;
      assignField(cur, key, val);
      continue;
    }
    // Evidence sub-field at 6-space indent.
    const evMatch = raw.match(/^\s{6}([A-Za-z0-9_-]+):\s*(.*)$/);
    if (evMatch && cur && inEvidence && cur.evidence) {
      cur.evidence[evMatch[1]] = parseScalar(evMatch[2].trim());
      continue;
    }
  }
  if (cur && cur.id && cur.statement !== undefined && cur.kind) {
    out.push(finalizeCriterion(cur));
  }
  return out;
}

function assignField(cur: CriterionInProgress, key: string, val: string): void {
  const unquoted = val.replace(/^["']|["']$/g, "");
  if (key === "id") cur.id = unquoted;
  else if (key === "statement") cur.statement = unquoted;
  else if (key === "kind") cur.kind = unquoted as CriterionKind;
}

function finalizeCriterion(cur: CriterionInProgress): Criterion {
  const c: Criterion = {
    id: cur.id as string,
    statement: cur.statement as string,
    kind: cur.kind as CriterionKind,
  };
  if (cur.evidence && Object.keys(cur.evidence).length > 0) {
    const ev = cur.evidence;
    const kind = (ev.kind as CriterionKind) ?? c.kind;
    c.evidence = { ...ev, kind } as CriterionEvidence;
  }
  return c;
}

function isLinkArray(val: unknown): val is TaskLink[] {
  if (!Array.isArray(val)) return false;
  if (val.length === 0) return true;
  const first = val[0] as Record<string, unknown> | null;
  return !!first && typeof first === "object" && "kind" in first && "target_task_id" in first;
}

function parseLinksBlock(lines: string[]): TaskLink[] {
  const out: TaskLink[] = [];
  let cur: { kind?: string; target_task_id?: string } | null = null;
  for (const raw of lines) {
    if (raw.trim() === "") continue;
    const itemMatch = raw.match(/^\s{2}-\s+([A-Za-z0-9_-]+):\s*(.*)$/);
    if (itemMatch) {
      if (cur && cur.kind && cur.target_task_id) {
        out.push({ kind: cur.kind as LinkKind, target_task_id: cur.target_task_id });
      }
      cur = {};
      const k = itemMatch[1];
      const v = itemMatch[2].trim().replace(/^["']|["']$/g, "");
      if (k === "kind") cur.kind = v;
      else if (k === "target_task_id") cur.target_task_id = v;
      continue;
    }
    const fieldMatch = raw.match(/^\s{4}([A-Za-z0-9_-]+):\s*(.*)$/);
    if (fieldMatch && cur) {
      const k = fieldMatch[1];
      const v = fieldMatch[2].trim().replace(/^["']|["']$/g, "");
      if (k === "kind") cur.kind = v;
      else if (k === "target_task_id") cur.target_task_id = v;
    }
  }
  if (cur && cur.kind && cur.target_task_id) {
    out.push({ kind: cur.kind as LinkKind, target_task_id: cur.target_task_id });
  }
  return out;
}

function parseScalar(v: string): unknown {
  if (v === "") return "";
  if (v === "null") return null;
  if (v === "true") return true;
  if (v === "false") return false;
  if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
  if ((v.startsWith("{") && v.endsWith("}")) || (v.startsWith("[") && v.endsWith("]"))) {
    try {
      return JSON.parse(v);
    } catch {
      // fall through
    }
  }
  return v.replace(/^["']|["']$/g, "");
}
