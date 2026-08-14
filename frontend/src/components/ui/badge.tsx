import type { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";
import type { TripRow } from "../../types";

const CLASS_MAP: Record<string, string> = {
  Good: "bg-good-bg text-good",
  Monitor: "bg-monitor-bg text-monitor",
  "Over Limit": "bg-over-bg text-over",
};

export function ComplianceBadge({ flag }: { flag: TripRow["Compliance"] }) {
  const cls = CLASS_MAP[flag ?? ""] ?? "bg-card2 text-text-tert";
  return (
    <span className={cn("inline-block rounded px-2 py-0.5 font-mono text-[10.5px] font-semibold tracking-wide", cls)}>
      {flag ?? "N/A"}
    </span>
  );
}

const CHIP_COLORS: Record<string, string> = {
  blue: "bg-[#142a2a] text-[#5cc8c8] border-[#1f4a4a]",
  green: "bg-[#11331f] text-[#3ddc84] border-[#1d4a30]",
  amber: "bg-[#4a3414] text-[#ff9d2e] border-[#5c3f12]",
  red: "bg-[#3a1414] text-[#ff5252] border-[#5c1818]",
  gray: "bg-card2 text-text-tert border-border",
  purple: "bg-[#241a3a] text-[#c9a8ff] border-[#3a2a5c]",
};

export function Chip({
  children,
  color = "gray",
  onRemove,
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { color?: keyof typeof CHIP_COLORS; onRemove?: () => void }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded px-2.5 py-1 font-mono text-[11px] font-medium border",
        CHIP_COLORS[color],
        className
      )}
      {...props}
    >
      {children}
      {onRemove && (
        <button
          type="button"
          aria-label="Remove filter"
          onClick={onRemove}
          className="ml-0.5 opacity-70 hover:opacity-100"
        >
          ×
        </button>
      )}
    </span>
  );
}
