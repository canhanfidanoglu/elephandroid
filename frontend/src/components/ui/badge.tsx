import { HTMLAttributes, forwardRef } from "react";

type Variant = "default" | "success" | "warning" | "danger";

const variantStyles: Record<Variant, string> = {
  default: "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300",
  success: "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  danger: "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant = "default", className = "", ...props }, ref) => (
    <span
      ref={ref}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${variantStyles[variant]} ${className}`}
      {...props}
    />
  ),
);

Badge.displayName = "Badge";

export { Badge };
