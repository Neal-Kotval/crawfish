/**
 * Org root resolution. Per spec §1 every org lives under
 * `~/.crawfish/orgs/<org_id>/`. The root can be overridden via
 * `CRAWFISH_HOME` so tests can use a tmpdir.
 */
import * as path from "node:path";
import * as os from "node:os";
import * as fs from "node:fs";
export function crawfishHome() {
    return process.env.CRAWFISH_HOME || path.join(os.homedir(), ".crawfish");
}
export function orgsRoot() {
    return path.join(crawfishHome(), "orgs");
}
export class OrgError extends Error {
    code;
    constructor(code, message) {
        super(message);
        this.code = code;
    }
}
/** Validate org_id (ULID-ish slug per §2 id rule). */
export function validateOrgId(orgId) {
    if (!/^[a-z0-9_-]{1,32}$/.test(orgId)) {
        throw new OrgError("not_found", `invalid org_id: ${orgId}`);
    }
}
/** Resolve `<orgs_root>/<org_id>/`. Creates nothing; caller checks existence. */
export function resolveOrgRoot(orgId) {
    validateOrgId(orgId);
    return path.join(orgsRoot(), orgId);
}
/** Require the org directory exists; throw `not_found` otherwise. */
export function requireOrg(orgId) {
    const root = resolveOrgRoot(orgId);
    if (!fs.existsSync(root)) {
        throw new OrgError("not_found", `org ${orgId} not found`);
    }
    return root;
}
//# sourceMappingURL=orgs.js.map