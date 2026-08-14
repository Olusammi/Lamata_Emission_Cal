import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("rounded-md border border-border border-t-2 border-t-border2 bg-card p-4", className)}
      {...props}
    />
  )
);
Card.displayName = "Card";

export const CardTitle = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn("font-mono text-[10px] font-medium uppercase tracking-wider text-text-tert mb-2", className)}
      {...props}
    />
  )
);
CardTitle.displayName = "CardTitle";
