import { ReactNode } from "react";

type MessageTone = "error" | "warn" | "hint" | "success";

/**
 * Message — inline status text (error, warning, hint, success). Replaces
 * the dozens of `<div style={{ color: "var(--cf-danger)", fontSize: 12 }}>`
 * patterns scattered across the dash.
 */
export function Message({
  tone = "hint",
  children,
}: {
  tone?: MessageTone;
  children: ReactNode;
}) {
  return <div className={`cf-msg cf-msg--${tone}`}>{children}</div>;
}
