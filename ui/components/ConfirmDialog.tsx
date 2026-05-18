import { useEffect, useRef, type ReactNode } from "react";

/**
 * Brand-consistent confirm dialog. Replacement for `window.confirm(...)`
 * which is OS-styled, unbranded, and not keyboard-friendly across browsers.
 *
 * Usage:
 *   const [open, setOpen] = useState(false);
 *   <ConfirmDialog
 *     open={open}
 *     title="Revoke invite?"
 *     body="The recipient can no longer accept this invite."
 *     confirmLabel="Revoke"
 *     destructive
 *     onCancel={() => setOpen(false)}
 *     onConfirm={() => { revoke(); setOpen(false); }}
 *   />
 *
 * Renders nothing when `open` is false. Closes on Escape. Focus traps to the
 * confirm button so Enter immediately confirms.
 */
export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  body?: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    confirmRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="cf-confirm-title"
      onClick={onCancel}
      style={{
        position: "fixed",
        inset: 0,
        background: "var(--scrim)",
        zIndex: 1100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "100%",
          maxWidth: 420,
          background: "var(--surface-2)",
          border: "1px solid var(--rule-3)",
          borderRadius: "var(--r-lg)",
          boxShadow: "var(--shadow-lg)",
          padding: "20px 22px 18px",
        }}
      >
        <h2
          id="cf-confirm-title"
          style={{
            fontFamily: "var(--ff-display)",
            fontSize: 20,
            fontWeight: 500,
            letterSpacing: "-0.02em",
            margin: 0,
            color: "var(--ink)",
          }}
        >
          {title}
        </h2>
        {body ? (
          <div
            style={{
              marginTop: 10,
              fontSize: 14,
              lineHeight: 1.5,
              color: "var(--ink-soft)",
            }}
          >
            {body}
          </div>
        ) : null}
        <div
          style={{
            marginTop: 20,
            display: "flex",
            justifyContent: "flex-end",
            gap: 8,
          }}
        >
          <button
            type="button"
            onClick={onCancel}
            className="cf-touch-target"
            style={{
              appearance: "none",
              cursor: "pointer",
              fontFamily: "var(--ff-sans)",
              fontSize: 13,
              fontWeight: 500,
              padding: "8px 14px",
              borderRadius: "var(--r-sm)",
              background: "var(--surface-2)",
              color: "var(--ink)",
              border: "1px solid var(--rule-3)",
            }}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            ref={confirmRef}
            onClick={onConfirm}
            className="cf-touch-target"
            style={{
              appearance: "none",
              cursor: "pointer",
              fontFamily: "var(--ff-sans)",
              fontSize: 13,
              fontWeight: 500,
              padding: "8px 14px",
              borderRadius: "var(--r-sm)",
              background: destructive ? "var(--danger)" : "var(--accent)",
              color: "#fff",
              border: `1px solid ${destructive ? "var(--danger)" : "var(--accent)"}`,
            }}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
