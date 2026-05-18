/**
 * Minimal YAML frontmatter parser and serializer for `.crawfish/tasks/*.md`
 * and `.crawfish/epics/*.md`. We deliberately do not pull a YAML dep — the
 * skill emits a narrow subset (strings, ISO dates, inline arrays). Anything
 * richer is rejected with a descriptive error.
 *
 * Mirrors the parser shape in `desktop/dash/src/server/roadmap.ts` so reader
 * and writer agree on the wire format. If you change one, change the other.
 */

export type FrontmatterValue = string | string[] | number;
export type Frontmatter = Record<string, FrontmatterValue>;

export interface ParsedDoc {
  fm: Frontmatter;
  body: string;
}

export function parseFrontmatter(raw: string): ParsedDoc {
  const match = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) return { fm: {}, body: raw };
  const fm: Frontmatter = {};
  for (const line of match[1].split(/\r?\n/)) {
    if (line.trim() === "" || line.trim().startsWith("#")) continue;
    const m = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!m) continue;
    const key = m[1];
    const value = m[2].trim();
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
  }
  return { fm, body: match[2] };
}

export function serializeFrontmatter(fm: Frontmatter, body: string): string {
  const lines: string[] = ["---"];
  for (const [key, val] of Object.entries(fm)) {
    if (Array.isArray(val)) {
      lines.push(`${key}: [${val.map(quoteIfNeeded).join(", ")}]`);
    } else if (typeof val === "number") {
      lines.push(`${key}: ${val}`);
    } else {
      lines.push(`${key}: ${quoteIfNeeded(val)}`);
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
