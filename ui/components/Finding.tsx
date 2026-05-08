import type { Finding } from "../lib/api";

export function FindingBanner({ f }: { f: Finding }) {
  const icon =
    f.severity === "crit" ? "🛑" : f.severity === "warn" ? "⚠️" : "💡";
  return (
    <div className="cf-finding" data-severity={f.severity}>
      <div className="cf-finding__icon">{icon}</div>
      <div className="cf-finding__body">
        <div className="cf-finding__title">{f.title}</div>
        <div className="cf-finding__detail">{f.detail}</div>
        {f.fix?.install ? (
          <code className="cf-finding__fix">{f.fix.install}</code>
        ) : f.fix ? (
          <span className="cf-finding__detail">{f.fix.text}</span>
        ) : null}
      </div>
    </div>
  );
}
