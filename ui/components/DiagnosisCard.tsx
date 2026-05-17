import type { ReactNode } from "react";
import { Eyebrow } from "./Eyebrow";

export interface DiagnosisCardProps {
  title?: ReactNode;
  children: ReactNode;
  cta?: ReactNode;
  onApply?: () => void;
}

export function DiagnosisCard({ title = "Diagnosis", children, cta, onApply }: DiagnosisCardProps) {
  return (
    <div className="cfp-diag">
      <Eyebrow style={{ color: "var(--accent)", marginBottom: 4 }}>{title}</Eyebrow>
      <div className="cfp-diag__body">{children}</div>
      {(cta || onApply) ? (
        <button
          type="button"
          className="cfp-btn cfp-btn--primary cfp-btn--sm"
          style={{ marginTop: 8 }}
          onClick={onApply}
        >{cta ?? "Apply fix →"}</button>
      ) : null}
    </div>
  );
}
