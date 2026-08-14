import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "../../lib/utils";

interface KpiCardProps {
  label: string;
  value: ReactNode;
  sub?: ReactNode;
  deltaTone?: "good" | "bad" | "neutral";
  className?: string;
}

export function KpiCard({ label, value, sub, deltaTone = "neutral", className }: KpiCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className={cn(
        "rounded-md border border-border border-t-2 border-t-border2 bg-metric-bg bg-card px-4 py-3.5",
        className
      )}
    >
      <div className="font-mono text-[10px] font-medium uppercase tracking-wider text-text-tert">{label}</div>
      <div className="mt-1 font-mono text-2xl font-semibold text-text-prim tabular-nums">{value}</div>
      {sub && (
        <div
          className={cn(
            "mt-1 font-mono text-[11px]",
            deltaTone === "good" && "text-good",
            deltaTone === "bad" && "text-over",
            deltaTone === "neutral" && "text-text-sec"
          )}
        >
          {sub}
        </div>
      )}
    </motion.div>
  );
}
