/**
 * Shell — signed-in app chrome.
 *
 * Two modes:
 *  • Org context (route has :org param) → sidebar shows Canvas/Board/Sessions/
 *    Knowledge/Diagnoses + Team/Billing/Settings. Titlebar shows the org name.
 *  • Root context (no :org, e.g. the org picker) → sidebar shows the user's
 *    pinned orgs + "+ New org". Titlebar shows the user, not an org.
 */
import { Outlet, useNavigate, useParams } from "react-router-dom";
import { TitleBar } from "@crawfish/ui/components/TitleBar";
import { SideItem } from "@crawfish/ui/components/SideItem";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Icons } from "@crawfish/ui/components/Icon";

const NAV = [
  { key: "canvas",    label: "Canvas",    icon: Icons.canvas },
  { key: "board",     label: "Board",     icon: Icons.board },
  { key: "sessions",  label: "Sessions",  icon: Icons.sessions },
  { key: "knowledge", label: "Knowledge", icon: Icons.knowledge },
  { key: "diagnoses", label: "Diagnoses", icon: Icons.diagnoses },
];

const ORG_ADMIN = [
  { key: "team",     label: "Team & invites" },
  { key: "billing",  label: "Billing" },
  { key: "settings", label: "Settings" },
];

const PINNED_ORGS = [
  { id: "acme-co",  label: "acme-co",  status: "live" as const },
  { id: "pat-side", label: "pat-side", status: "idle" as const },
];

export function Shell() {
  const navigate = useNavigate();
  const { org, tab } = useParams<{ org?: string; tab?: string }>();
  const active = tab ?? "canvas";
  const inOrg = Boolean(org);

  return (
    <div className="cfp-shell cfp-shell--no-rail">
      <div className="cfp-shell__titlebar">
        <TitleBar
          org={inOrg ? (org as string) : "your orgs"}
          orgGlyph={inOrg ? "cf" : "··"}
          costToday={inOrg ? "$0.14" : undefined}
          tokensPerHr={inOrg ? "1.2k" : undefined}
          userInitial="F"
          onOrgSwitch={() => navigate("/")}
        />
      </div>

      <aside className="cfp-shell__sidebar">
        {inOrg ? (
          <>
            <div>
              <Eyebrow style={{ padding: "0 6px", marginBottom: 6 }}>Workspace</Eyebrow>
              {NAV.map((n) => (
                <SideItem
                  key={n.key}
                  icon={n.icon}
                  label={n.label}
                  active={active === n.key}
                  onClick={() => navigate(`/orgs/${org}/${n.key}`)}
                />
              ))}
            </div>

            <div>
              <Eyebrow style={{ padding: "0 6px", marginBottom: 6 }}>Org admin</Eyebrow>
              {ORG_ADMIN.map((n) => (
                <SideItem
                  key={n.key}
                  label={n.label}
                  active={active === n.key}
                  onClick={() => navigate(`/orgs/${org}/${n.key}`)}
                />
              ))}
            </div>

            <div style={{ marginTop: "auto" }}>
              <SideItem label="← All orgs" onClick={() => navigate("/")} />
            </div>
          </>
        ) : (
          <>
            <div>
              <Eyebrow style={{ padding: "0 6px", marginBottom: 6 }}>Your orgs</Eyebrow>
              {PINNED_ORGS.map((o) => (
                <SideItem
                  key={o.id}
                  label={
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <span style={{
                        width: 6, height: 6, borderRadius: "50%",
                        background: o.status === "live" ? "var(--accent)" : "var(--ink-faint)",
                      }} />
                      {o.label}
                    </span>
                  }
                  onClick={() => navigate(`/orgs/${o.id}/canvas`)}
                />
              ))}
              <div style={{ marginTop: 6 }}>
                <SideItem
                  icon={Icons.plus}
                  label="New org"
                  onClick={() => navigate("/onboarding")}
                />
              </div>
            </div>

            <div style={{ marginTop: "auto" }}>
              <SideItem label="Sign out" onClick={() => navigate("/signin")} />
            </div>
          </>
        )}
      </aside>

      <Outlet />
    </div>
  );
}
