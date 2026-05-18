/**
 * OrgMembers — team & invites panel for /orgs/:org/team.
 *
 * Shows current members, an invite-by-email form, and the list of pending
 * invites with revoke buttons. In dev (mock-email mode) the create-invite
 * response includes the link to copy; we render it as a dashed mono card.
 */
import { useCallback, useEffect, useState } from "react";
import { Eyebrow } from "@crawfish/ui/components/Eyebrow";
import { Pill } from "@crawfish/ui/components/Pill";
import {
  acceptInvite as _accept, // unused, just for type parity
  createInvite,
  fetchOrg,
  listInvites,
  revokeInvite,
  type ApiError,
  type CreateInviteResponse,
  type Invite,
  type InviteRole,
  type Org,
} from "../lib/api";

void _accept;

type LoadState =
  | { kind: "loading" }
  | { kind: "ok"; org: Org; invites: Invite[] }
  | { kind: "error"; message: string };

export function OrgMembers({ orgSlug }: { orgSlug: string }) {
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [emailDraft, setEmailDraft] = useState("");
  const [roleDraft, setRoleDraft] = useState<InviteRole>("contributor");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [lastCreated, setLastCreated] = useState<CreateInviteResponse | null>(null);
  const [copied, setCopied] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const org = await fetchOrg(orgSlug);
      const invites = await listInvites(org.id);
      setState({ kind: "ok", org, invites });
    } catch (e) {
      const err = e as ApiError;
      setState({ kind: "error", message: err.message || "Failed to load team." });
    }
  }, [orgSlug]);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    refresh().catch(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [refresh]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (state.kind !== "ok") return;
    setFormError(null);
    setSubmitting(true);
    try {
      const created = await createInvite(state.org.id, {
        email: emailDraft.trim(),
        role: roleDraft,
      });
      setLastCreated(created);
      setEmailDraft("");
      setCopied(false);
      await refresh();
    } catch (e) {
      const err = e as ApiError;
      setFormError(err.message || "Failed to send invite.");
    } finally {
      setSubmitting(false);
    }
  }

  async function onRevoke(invite: Invite) {
    if (state.kind !== "ok") return;
    if (!window.confirm(`Revoke invite for ${invite.email}?`)) return;
    try {
      await revokeInvite(state.org.id, invite.id);
      await refresh();
    } catch (e) {
      const err = e as ApiError;
      window.alert(err.message || "Failed to revoke.");
    }
  }

  async function onCopy(link: string) {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  if (state.kind === "loading") {
    return (
      <main className="cfp-shell__main" style={{ padding: 28 }}>
        <Eyebrow>{orgSlug} · team</Eyebrow>
        <div className="cf-mono" style={{ marginTop: 12, color: "var(--ink-mute)", fontSize: 12 }}>
          loading…
        </div>
      </main>
    );
  }

  if (state.kind === "error") {
    return (
      <main className="cfp-shell__main" style={{ padding: 28 }}>
        <Eyebrow>{orgSlug} · team</Eyebrow>
        <p style={{ color: "var(--ink-soft)", fontSize: 14, marginTop: 12 }}>{state.message}</p>
      </main>
    );
  }

  const { org, invites } = state;

  return (
    <main className="cfp-shell__main" style={{ padding: 28, maxWidth: 880 }}>
      <Eyebrow>{org.name} · team</Eyebrow>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 32,
          letterSpacing: "-0.025em",
          margin: "6px 0 24px",
        }}
      >
        Team and invites
      </h1>

      {/* Current members */}
      <section style={{ marginBottom: 32 }}>
        <Eyebrow>Members ({org.members.length})</Eyebrow>
        <div
          style={{
            marginTop: 10,
            border: "1px solid var(--rule-3)",
            borderRadius: "var(--r-lg)",
            background: "var(--surface-2)",
            overflow: "hidden",
          }}
        >
          {org.members.map((m, idx) => (
            <div
              key={m.email}
              style={{
                padding: "12px 16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 12,
                borderTop: idx === 0 ? "none" : "1px solid var(--rule)",
              }}
            >
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontSize: 14, fontWeight: 500 }}>{m.name || m.email}</span>
                {m.name && (
                  <span className="cf-mono" style={{ fontSize: 11, color: "var(--ink-mute)" }}>
                    {m.email}
                  </span>
                )}
              </div>
              <Pill tone="ink">{m.role}</Pill>
            </div>
          ))}
        </div>
      </section>

      {/* Invite form */}
      <section style={{ marginBottom: 32 }}>
        <Eyebrow>Invite by email</Eyebrow>
        <form
          onSubmit={onSubmit}
          style={{
            marginTop: 10,
            display: "flex",
            gap: 8,
            alignItems: "stretch",
          }}
        >
          <input
            type="email"
            required
            placeholder="teammate@company.com"
            value={emailDraft}
            onChange={(e) => setEmailDraft(e.target.value)}
            disabled={submitting}
            style={{
              flex: 1,
              padding: "10px 12px",
              fontSize: 14,
              fontFamily: "inherit",
              background: "var(--paper)",
              border: "1px solid var(--rule-3)",
              borderRadius: "var(--r-sm)",
              color: "var(--ink)",
            }}
          />
          <select
            value={roleDraft}
            onChange={(e) => setRoleDraft(e.target.value as InviteRole)}
            disabled={submitting}
            style={{
              padding: "10px 12px",
              fontSize: 14,
              fontFamily: "inherit",
              background: "var(--paper)",
              border: "1px solid var(--rule-3)",
              borderRadius: "var(--r-sm)",
              color: "var(--ink)",
            }}
          >
            <option value="contributor">contributor</option>
            <option value="owner">owner</option>
          </select>
          <button
            type="submit"
            disabled={submitting || !emailDraft.trim()}
            style={{
              padding: "10px 18px",
              fontSize: 14,
              fontWeight: 500,
              background: "var(--ink)",
              color: "var(--accent)",
              border: "none",
              borderRadius: "var(--r-sm)",
              cursor: submitting ? "wait" : "pointer",
              opacity: submitting || !emailDraft.trim() ? 0.6 : 1,
            }}
          >
            {submitting ? "Sending…" : "Send invite"}
          </button>
        </form>

        {formError && (
          <div
            className="cf-mono"
            style={{
              marginTop: 12,
              padding: "8px 12px",
              fontSize: 12,
              color: "var(--bad, #a23a2a)",
              background: "var(--surface-warn, #fef3e6)",
              border: "1px solid var(--rule-3)",
              borderRadius: "var(--r-sm)",
            }}
          >
            {formError}
          </div>
        )}

        {lastCreated && (
          <div
            style={{
              marginTop: 16,
              padding: 16,
              border: "1px dashed var(--rule-3)",
              borderRadius: "var(--r-lg)",
              background: "var(--paper)",
            }}
          >
            <div
              className="cf-mono"
              style={{ fontSize: 11, color: "var(--ink-mute)", marginBottom: 8 }}
            >
              MOCK EMAIL, dev mode, no SMTP yet
            </div>
            <div className="cf-mono" style={{ fontSize: 12, color: "var(--ink-soft)", lineHeight: 1.7 }}>
              <div>
                <span style={{ color: "var(--ink-mute)" }}>To: </span>
                {lastCreated.mockEmail.to}
              </div>
              <div>
                <span style={{ color: "var(--ink-mute)" }}>Subject: </span>
                {lastCreated.mockEmail.subject}
              </div>
              <div style={{ marginTop: 6, wordBreak: "break-all" }}>
                <span style={{ color: "var(--ink-mute)" }}>Link: </span>
                <a
                  href={lastCreated.mockEmail.link}
                  style={{ color: "var(--accent)", textDecoration: "none" }}
                >
                  {lastCreated.mockEmail.link}
                </a>
              </div>
            </div>
            <button
              type="button"
              onClick={() => onCopy(lastCreated.mockEmail.link)}
              style={{
                marginTop: 10,
                padding: "6px 12px",
                fontSize: 12,
                background: "transparent",
                border: "1px solid var(--rule-3)",
                borderRadius: "var(--r-sm)",
                color: "var(--ink)",
                cursor: "pointer",
              }}
            >
              {copied ? "Copied" : "Copy link"}
            </button>
          </div>
        )}
      </section>

      {/* Pending invites */}
      <section>
        <Eyebrow>Pending invites ({invites.length})</Eyebrow>
        {invites.length === 0 ? (
          <p
            className="cf-mono"
            style={{ marginTop: 10, fontSize: 12, color: "var(--ink-mute)" }}
          >
            no pending invites
          </p>
        ) : (
          <div
            style={{
              marginTop: 10,
              border: "1px solid var(--rule-3)",
              borderRadius: "var(--r-lg)",
              background: "var(--surface-2)",
              overflow: "hidden",
            }}
          >
            {invites.map((inv, idx) => (
              <div
                key={inv.id}
                style={{
                  padding: "12px 16px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 12,
                  borderTop: idx === 0 ? "none" : "1px solid var(--rule)",
                }}
              >
                <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
                  <span style={{ fontSize: 14 }}>{inv.email}</span>
                  <span
                    className="cf-mono"
                    style={{ fontSize: 11, color: "var(--ink-mute)" }}
                  >
                    expires {new Date(inv.expiresAt).toLocaleDateString()}
                    {inv.code ? ` · /invites/${inv.code}` : ""}
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Pill tone="ink">{inv.role}</Pill>
                  <button
                    type="button"
                    onClick={() => onRevoke(inv)}
                    title="Revoke invite"
                    style={{
                      width: 28,
                      height: 28,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background: "transparent",
                      border: "1px solid var(--rule-3)",
                      borderRadius: "var(--r-sm)",
                      color: "var(--ink-soft)",
                      cursor: "pointer",
                      fontSize: 14,
                      lineHeight: 1,
                    }}
                  >
                    ×
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
