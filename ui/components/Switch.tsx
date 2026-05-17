import { InputHTMLAttributes, forwardRef } from "react";

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

/**
 * iOS-style toggle switch. Wrap a labeled control by setting `label`;
 * for layout flexibility, pass children-less and place text next to it.
 */
export const Switch = forwardRef<HTMLInputElement, SwitchProps>(function Switch(
  { label, className, ...rest },
  ref,
) {
  const sw = (
    <label className={["cf-switch", className ?? ""].filter(Boolean).join(" ")}>
      <input ref={ref} type="checkbox" {...rest} />
      <span className="cf-switch__track" />
    </label>
  );
  if (!label) return sw;
  return (
    <span className="cf-row cf-gap-2">
      {sw}
      <span className="cf-label">{label}</span>
    </span>
  );
});
