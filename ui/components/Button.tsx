import { ButtonHTMLAttributes, ReactNode, forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "quiet" | "danger" | "glass";
type Size = "xs" | "sm" | "md" | "lg";

export interface ButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  variant?: Variant;
  size?: Size;
  pill?: boolean;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  children?: ReactNode;
}

const VARIANT_CLASS: Record<Variant, string> = {
  primary: "cf-btn--primary",
  secondary: "",
  ghost: "cf-btn--ghost",
  quiet: "cf-btn--quiet",
  danger: "cf-btn--danger",
  glass: "cf-btn--glass",
};

const SIZE_CLASS: Record<Size, string> = {
  xs: "cf-btn--xs",
  sm: "cf-btn--sm",
  md: "",
  lg: "cf-btn--lg",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", pill, leadingIcon, trailingIcon, className, children, ...rest },
  ref,
) {
  const cls = [
    "cf-btn",
    VARIANT_CLASS[variant],
    SIZE_CLASS[size],
    pill ? "cf-btn--pill" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button ref={ref} className={cls} {...rest}>
      {leadingIcon}
      {children}
      {trailingIcon}
    </button>
  );
});

export interface IconButtonProps extends Omit<ButtonProps, "leadingIcon" | "trailingIcon" | "children" | "pill"> {
  /** Required for accessibility — icon-only buttons must have a label. */
  "aria-label": string;
  icon: ReactNode;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon, className, size = "md", variant = "ghost", ...rest },
  ref,
) {
  return (
    <Button
      ref={ref}
      variant={variant}
      size={size}
      className={["cf-btn--icon", className ?? ""].filter(Boolean).join(" ")}
      {...rest}
    >
      {icon}
    </Button>
  );
});
