// Industry-overlay merger. A base template (e.g. `dev-shop`) describes a
// role-shape; an overlay (e.g. `consumer-mobile`) adds vertical-specific
// members + crons on top. The merger never *renames* base members — only
// appends — so a user can take an overlay safely without losing their
// existing org structure.
//
// Used by:
//   - the describe-my-org wizard (dash) when synthesizing a custom template
//   - the orgctl CLI when spinning an org from `template@v3 + overlay=b2b-saas`

export interface TemplateMember {
  id: string;
  kind: "agent" | "human";
  role: string;
  name: string;
  prompt?: string;
  prompt_file?: string;
  tools?: string[] | null;
  model?: string | null;
}

export interface TemplateCron {
  id: string;
  cron: string;
  member_id: string;
  prompt: string;
  output_to: string;
  enabled: boolean;
  last_run: string | null;
}

export interface BaseTemplate {
  slug: string;
  name: string;
  description: string;
  architecture: string;
  members: TemplateMember[];
}

export interface OrgConfig extends BaseTemplate {
  crons?: TemplateCron[];
  knowledge_sources?: Array<{
    id: string;
    kind: "repo" | "url" | "files";
    path_or_url: string;
    include?: string[];
    exclude?: string[];
  }>;
}

export interface Overlay {
  slug: string;
  name: string;
  description: string;
  add_members?: TemplateMember[];
  add_crons?: TemplateCron[];
  add_knowledge_sources?: OrgConfig["knowledge_sources"];
}

/**
 * Merge an overlay into a base. The result is a new object — neither input
 * is mutated. Duplicate member or cron ids are rejected with an Error so a
 * conflict can't silently shadow the base config.
 */
export function applyOverlay(base: OrgConfig, overlay: Overlay): OrgConfig {
  const baseMemberIds = new Set(base.members.map((m) => m.id));
  const incomingMembers = overlay.add_members ?? [];
  for (const m of incomingMembers) {
    if (baseMemberIds.has(m.id)) {
      throw new Error(
        `overlay ${overlay.slug} member id "${m.id}" collides with base ${base.slug}`,
      );
    }
  }

  const baseCronIds = new Set((base.crons ?? []).map((c) => c.id));
  const incomingCrons = overlay.add_crons ?? [];
  for (const c of incomingCrons) {
    if (baseCronIds.has(c.id)) {
      throw new Error(
        `overlay ${overlay.slug} cron id "${c.id}" collides with base ${base.slug}`,
      );
    }
  }

  const baseSourceIds = new Set((base.knowledge_sources ?? []).map((s) => s.id));
  const incomingSources = overlay.add_knowledge_sources ?? [];
  for (const s of incomingSources) {
    if (baseSourceIds.has(s.id)) {
      throw new Error(
        `overlay ${overlay.slug} knowledge_source "${s.id}" collides with base ${base.slug}`,
      );
    }
  }

  return {
    ...base,
    name: `${base.name} · ${overlay.name}`,
    description: `${base.description}\n\nOverlay: ${overlay.description}`,
    members: [...base.members, ...incomingMembers],
    crons: [...(base.crons ?? []), ...incomingCrons],
    knowledge_sources: [
      ...(base.knowledge_sources ?? []),
      ...incomingSources,
    ],
  };
}

/** Apply zero or more overlays in order. Useful for compound shapes. */
export function applyOverlays(base: OrgConfig, overlays: Overlay[]): OrgConfig {
  return overlays.reduce(applyOverlay, base);
}
