/**
 * OrgRoute — dispatches /orgs/:org/:tab to the right surface.
 *
 * Each surface is a thin stub today; the real implementations will land
 * as the platform fans out. Online collaborative canvas is the big one
 * (multi-cursor, presence indicators, live trace shared across users).
 */
import { useParams } from "react-router-dom";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";

function Surface({ title, eyebrow, body }: { title: string; eyebrow: string; body: string }) {
  return (
    <main className="cfp-shell__main" style={{ padding: 28 }}>
      <Eyebrow>{eyebrow}</Eyebrow>
      <h1 style={{
        fontFamily: "var(--ff-display)", fontWeight: 500, fontSize: 32,
        letterSpacing: "-0.025em", margin: "6px 0 12px",
      }}>{title}</h1>
      <p style={{ color: "var(--ink-soft)", fontSize: 14, maxWidth: 640 }}>{body}</p>
      <Pill tone="warn" style={{ marginTop: 16 }}>scaffold · wire later</Pill>
    </main>
  );
}

export function OrgRoute() {
  const { org = "acme-co", tab = "canvas" } = useParams<{ org?: string; tab?: string }>();

  switch (tab) {
    case "canvas":
      return <Surface
        eyebrow={`${org} · canvas`}
        title="Online org canvas"
        body="The desktop dash canvas, but multiplayer. Everyone in the org sees the same nodes, edges, and live trace; cursors are presence-indicated; an agent run streams to all viewers."
      />;
    case "board":
      return <Surface eyebrow={`${org} · board`} title="Board" body="Shared kanban board for human + agent tickets." />;
    case "sessions":
      return <Surface eyebrow={`${org} · sessions`} title="Sessions" body="Cross-team transcripts with public permalinks for sharing a session externally." />;
    case "knowledge":
      return <Surface eyebrow={`${org} · knowledge`} title="Knowledge" body="Shared ADRs, runbooks, and pinned slack messages indexed for agent retrieval." />;
    case "diagnoses":
      return <Surface eyebrow={`${org} · diagnoses`} title="Diagnoses" body="Org-wide findings across agents — token bloat, retry storms, librarian misses." />;
    case "team":
      return <Surface eyebrow={`${org} · team`} title="Team & invites" body="Invite humans, assign roles, manage ACL groups, see who's online." />;
    case "billing":
      return <Surface eyebrow={`${org} · billing`} title="Billing" body="Monthly usage, per-agent budgets, plan, payment methods." />;
    case "settings":
      return <Surface eyebrow={`${org} · settings`} title="Org settings" body="Name, domain, default runtime, policy presets, integrations." />;
    default:
      return <Surface eyebrow={`${org}`} title="Unknown surface" body={`No surface named "${tab}".`} />;
  }
}
