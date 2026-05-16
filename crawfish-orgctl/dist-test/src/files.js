/**
 * Hosted-FS helpers for `<org>/files/`. Enforces spec §4 path rules:
 *   - reject `..`, absolute paths, null bytes
 *   - resolved path must stay under `<org>/files/`
 *   - 1 MiB cap on reads/writes → `too_large`
 */
import * as fs from "node:fs";
import * as fsp from "node:fs/promises";
import * as path from "node:path";
import { OrgError, requireOrg } from "./orgs.js";
export const MAX_BYTES = 1024 * 1024; // 1 MiB
function assertSafeRelative(p) {
    if (p.includes("\0"))
        throw new OrgError("path_escape", "null byte in path");
    if (path.isAbsolute(p))
        throw new OrgError("path_escape", "absolute path");
    // Normalize using POSIX semantics so '..' segments are detectable regardless
    // of platform sep. Reject any '..' segment up front.
    const parts = p.split(/[\\/]+/).filter((s) => s.length > 0 && s !== ".");
    if (parts.some((s) => s === "..")) {
        throw new OrgError("path_escape", "'..' segment not allowed");
    }
}
export function resolveFilePath(orgId, rel) {
    assertSafeRelative(rel);
    const orgRoot = requireOrg(orgId);
    const filesRoot = path.join(orgRoot, "files");
    const full = path.resolve(filesRoot, rel);
    const rootWithSep = filesRoot.endsWith(path.sep) ? filesRoot : filesRoot + path.sep;
    if (full !== filesRoot && !full.startsWith(rootWithSep)) {
        throw new OrgError("path_escape", "resolved path escapes files root");
    }
    return { root: filesRoot, full };
}
/** Recursive listing under `<org>/files/`, optionally filtered by prefix. */
export async function listFiles(orgId, prefix) {
    const orgRoot = requireOrg(orgId);
    const filesRoot = path.join(orgRoot, "files");
    if (!fs.existsSync(filesRoot))
        return [];
    const out = [];
    async function walk(dir, relDir) {
        const entries = await fsp.readdir(dir, { withFileTypes: true });
        for (const ent of entries) {
            const childAbs = path.join(dir, ent.name);
            const childRel = relDir ? `${relDir}/${ent.name}` : ent.name;
            const st = await fsp.stat(childAbs);
            if (ent.isDirectory()) {
                out.push({ path: childRel, kind: "dir", size: 0, mtime: st.mtime.toISOString() });
                await walk(childAbs, childRel);
            }
            else if (ent.isFile()) {
                out.push({ path: childRel, kind: "file", size: st.size, mtime: st.mtime.toISOString() });
            }
        }
    }
    await walk(filesRoot, "");
    let filtered = out;
    if (prefix) {
        assertSafeRelative(prefix);
        const norm = prefix.replace(/\\/g, "/").replace(/^\/+|\/+$/g, "");
        filtered = out.filter((e) => e.path === norm || e.path.startsWith(norm + "/"));
    }
    filtered.sort((a, b) => a.path.localeCompare(b.path));
    return filtered;
}
export async function readFile(orgId, rel) {
    const { full } = resolveFilePath(orgId, rel);
    let st;
    try {
        st = await fsp.stat(full);
    }
    catch {
        throw new OrgError("not_found", `file ${rel} not found`);
    }
    if (!st.isFile())
        throw new OrgError("not_found", `${rel} is not a file`);
    if (st.size > MAX_BYTES) {
        throw new OrgError("too_large", `file exceeds 1 MiB`);
    }
    const buf = await fsp.readFile(full);
    return {
        content: buf.toString("utf8"),
        size: st.size,
        mtime: st.mtime.toISOString(),
    };
}
export async function writeFile(orgId, rel, content) {
    const buf = Buffer.from(content, "utf8");
    if (buf.byteLength > MAX_BYTES) {
        throw new OrgError("too_large", `content exceeds 1 MiB`);
    }
    const { full } = resolveFilePath(orgId, rel);
    // Idempotent no-op: if existing content matches exactly, skip the write
    // but still return current stat. (Avoids touching mtime needlessly.)
    if (fs.existsSync(full)) {
        const existing = await fsp.readFile(full);
        if (existing.equals(buf)) {
            const st = await fsp.stat(full);
            return { size: st.size, mtime: st.mtime.toISOString() };
        }
    }
    await fsp.mkdir(path.dirname(full), { recursive: true });
    await fsp.writeFile(full, buf);
    const st = await fsp.stat(full);
    return { size: st.size, mtime: st.mtime.toISOString() };
}
