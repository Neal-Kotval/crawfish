/**
 * Shell — signed-in app chrome.
 *
 * Two modes:
 *  • Org context (route has :org param) → sidebar shows Canvas/Board/Sessions/
 *    Knowledge/Diagnoses + Team/Billing/Settings. Titlebar shows the org name.
 *  • Root context (no :org, e.g. the org picker) → sidebar shows the user's
 *    pinned orgs + "+ New org". Titlebar shows the user, not an org.
 */
import { useEffect, useState } from "react";
import { Outlet, useNavigate, useParams } from "react-router-dom";
import { TitleBar } from "@crawfish/ui/components/TitleBar";
import { SideItem } from "@crawfish/ui/components/SideItem";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Icons } from "@crawfish/ui/components/Icon";
import { useCurrentUser } from "./lib/useAuth";
import { listMyOrgs, type OrgSummary } from "./lib/api";
import { useClerk } from "@clerk/clerk-react";
import { CLERK_ENABLED } from "./lib/clerk";

const NAV = [
  { key: "canvas",    label: "Canvas",    icon: Icons.canvas },
  { key: "projects",  label: "Projects",  icon: Icons.code },
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

function initialFor(name: string, email: string): string {
  const src = (name || email || "?").trim();
  return src.charAt(0).toUpperCase() || "?";
}

export function Shell() {
  const navigate = useNavigate();
  const { org, tab } = useParams<{ org?: string; tab?: string }>();
  const active = tab ?? "canvas";
  const inOrg = Boolean(org);
  const me = useCurrentUser();
  // Clerk hook is safe to call unconditionally — CLERK_ENABLED is a build-time
  // constant from import.meta.env, so the branch is stable across renders.
  // eslint-disable-next-line react-hooks/rules-of-hooks
  const clerk = CLERK_ENABLED ? useClerk() : null;

  const [orgs, setOrgs] = useState<OrgSummary[]>([]);
  useEffect(() => {
    let cancelled = false;
    listMyOrgs()
      .then((list) => {
        if (!cancelled) setOrgs(list);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  async function signOut() {
    try {
      if (clerk) await clerk.signOut();
    } catch {
      /* ignore */
    }
    try {
      localStorage.removeItem("cf_dev_user");
    } catch {
      /* ignore */
    }
    navigate("/signin");
  }

  return (
    <div className="cfp-shell cfp-shell--no-rail cfp-shell--responsive">
      <style>{`
        @media (max-width: 768px) {
          .cfp-shell--responsive {
            grid-template-columns: 1fr !important;
            grid-template-rows: auto auto 1fr !important;
            grid-template-areas: "titlebar" "sidebar" "content" !important;
          }
          .cfp-shell--responsive .cfp-shell__sidebar {
            position: static;
            width: 100%;
            min-height: 0;
            max-height: 200px;
            overflow-y: auto;
            border-right: none;
            border-bottom: 1px solid var(--rule);
          }
        }
      `}</style>
      <div className="cfp-shell__titlebar">
        <TitleBar
          org={inOrg ? (org as string) : "your orgs"}
          orgGlyph={inOrg ? "cf" : "··"}
          userInitial={initialFor(me.name, me.email)}
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
              {/* Per 2026-05-18 brainstorm: one user, one workspace. We only
                  render the multi-org list when the user is a legacy account
                  with >1 org. New users see a clean sidebar — their projects
                  live on the Dashboard at /, not behind an org picker. */}
              {orgs.length > 1 && (
                <>
                  <Eyebrow style={{ padding: "0 6px", marginBottom: 6 }}>Your workspaces</Eyebrow>
                  {orgs.map((o) => {
                    const isActive = inOrg && org === o.name;
                    return (
                      <SideItem
                        key={o.id}
                        label={
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                            {isActive && (
                              <span
                                style={{
                                  width: 6,
                                  height: 6,
                                  borderRadius: "50%",
                                  background: "var(--accent)",
                                  flexShrink: 0,
                                }}
                              />
                            )}
                            {o.name}
                          </span>
                        }
                        active={isActive}
                        onClick={() => navigate(`/orgs/${o.name}/canvas`)}
                      />
                    );
                  })}
                </>
              )}
              {orgs.length === 1 && inOrg && (
                <SideItem
                  label="← Dashboard"
                  onClick={() => navigate("/")}
                />
              )}
            </div>

            <div style={{ marginTop: "auto" }}>
              <SideItem label="Sign out" onClick={signOut} />
            </div>
          </>
        )}
      </aside>

      <Outlet />
    </div>
  );
}

