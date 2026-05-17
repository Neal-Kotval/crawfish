/**
 * Link redeem page — /link/:code
 *
 * The user has clicked "Make this org online" inside Dash, which generated
 * a 6-char code and opened this URL in the browser. The user confirms the
 * code matches, we POST the redeem, and Dash polling picks up the new
 * authToken on its next 2s tick.
 *
 * No Shell — this is a focused single-purpose dialog (no sidebar/titlebar).
 */
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiFetch } from "../lib/api";

type Status = "ready" | "redeeming" | "linked" | "error";

export function LinkRedeem() {
  const { code: rawCode } = useParams<{ code: string }>();
  const code = (rawCode ?? "").toUpperCase();

  const [status, setStatus] = useState<Status>("ready");
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [orgName, setOrgName] = useState<string | null>(null);

  async function confirm() {
    setStatus("redeeming");
    setError(null);
    try {
      const res = await apiFetch(`/api/device-link/${encodeURIComponent(code)}/redeem`, {
        method: "POST",
      });
      if (res.ok) {
        const body = (await res.json()) as { org?: { name?: string } };
        setOrgName(body.org?.name ?? null);
        setStatus("linked");
        return;
      }
      const body = await res.json().catch(() => null);
      setError({
        code: body?.error?.code ?? `http_${res.status}`,
        message: body?.error?.message ?? `Request failed (HTTP ${res.status}).`,
      });
      setStatus("error");
    } catch (err) {
      setError({ code: "network", message: String(err) });
      setStatus("error");
    }
  }

  return (
    <div
      className="cf"
      style={{
        minHeight: "100vh",
        background: "var(--paper)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        style={{
          width: 460,
          background: "var(--surface-2)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-lg)",
          padding: 28,
          boxShadow: "var(--shadow-md)",
        }}
      >
        <span
          className="cf-eyebrow"
          style={{
            color: "var(--ink-faint)",
            fontSize: 11,
            letterSpacing: "0.08em",
            textTransform: "uppercase",
          }}
        >
          Device link
        </span>

        {status === "linked" ? (
          <LinkedView orgName={orgName} />
        ) : status === "error" && error?.code === "not_found" ? (
          <ErrorView title="Code not found" message="This code doesn't match any pending device link. It may have expired." />
        ) : status === "error" && error?.code === "expired" ? (
          <ErrorView title="Code expired" message="This code is older than 10 minutes. Click ‘Make online’ in Dash again to generate a fresh one." />
        ) : status === "error" && error?.code === "already_redeemed" ? (
          <ErrorView title="Already used" message="This code has already been redeemed. Each code only works once." />
        ) : (
          <ConfirmView
            code={code}
            redeeming={status === "redeeming"}
            error={error}
            onConfirm={confirm}
          />
        )}
      </div>
    </div>
  );
}

function ConfirmView({
  code,
  redeeming,
  error,
  onConfirm,
}: {
  code: string;
  redeeming: boolean;
  error: { code: string; message: string } | null;
  onConfirm: () => void;
}) {
  return (
    <>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 26,
          letterSpacing: "-0.025em",
          margin: "10px 0 6px 0",
        }}
      >
        Linking a device to your account
      </h1>
      <p style={{ color: "var(--ink-mute)", fontSize: 13, marginTop: 6, marginBottom: 22 }}>
        Confirm that the code shown in Dash matches the one below:
      </p>

      <div
        style={{
          textAlign: "center",
          padding: "20px 0 24px 0",
          fontFamily: "var(--ff-mono)",
          fontSize: 48,
          letterSpacing: "0.06em",
          color: "var(--accent)",
          fontWeight: 500,
        }}
      >
        {code}
      </div>

      {error ? (
        <p style={{ color: "var(--bad, #b1452f)", fontSize: 12, marginBottom: 12 }}>
          {error.message}
        </p>
      ) : null}

      <div style={{ display: "flex", gap: 8 }}>
        <button
          type="button"
          className="cfp-btn cfp-btn--primary"
          style={{ flex: 1, justifyContent: "center", padding: "10px 14px" }}
          onClick={onConfirm}
          disabled={redeeming}
        >
          {redeeming ? "Confirming…" : "Confirm"}
        </button>
        <Link
          to="/"
          className="cfp-btn"
          style={{ justifyContent: "center", padding: "10px 14px" }}
        >
          Cancel
        </Link>
      </div>
    </>
  );
}

function LinkedView({ orgName }: { orgName: string | null }) {
  return (
    <>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 26,
          letterSpacing: "-0.025em",
          margin: "10px 0 6px 0",
        }}
      >
        Linked <span style={{ color: "var(--accent)" }}>✓</span>
      </h1>
      <p style={{ color: "var(--ink-mute)", fontSize: 13, marginTop: 6, marginBottom: 22 }}>
        {orgName ? <>Your device is now linked to <b>{orgName}</b>. Return to Dash — the connection should appear within two seconds.</> : "Your device is now linked. Return to Dash — the connection should appear within two seconds."}
      </p>
      <Link
        to="/"
        className="cfp-btn"
        style={{ justifyContent: "center", padding: "10px 14px", width: "100%" }}
      >
        Go to your orgs
      </Link>
    </>
  );
}

function ErrorView({ title, message }: { title: string; message: string }) {
  return (
    <>
      <h1
        style={{
          fontFamily: "var(--ff-display)",
          fontWeight: 500,
          fontSize: 26,
          letterSpacing: "-0.025em",
          margin: "10px 0 6px 0",
        }}
      >
        {title}
      </h1>
      <p style={{ color: "var(--ink-mute)", fontSize: 13, marginTop: 6, marginBottom: 22 }}>
        {message}
      </p>
      <Link
        to="/"
        className="cfp-btn"
        style={{ justifyContent: "center", padding: "10px 14px", width: "100%" }}
      >
        Cancel
      </Link>
    </>
  );
}
