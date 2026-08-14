import type { ReactNode } from "react";

/** Port of app.py's `.banner` class — the gradient intro card at the top of every module. */
export function Banner({ children }: { children: ReactNode }) {
  return (
    <div
      className="rounded-md border p-4 text-[13px] leading-relaxed [&_strong]:text-accent [&_code]:rounded [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-[11px]"
      style={{
        background: "var(--banner-bg)",
        color: "var(--banner-text)",
        borderColor: "var(--banner-bdr)",
      }}
    >
      {children}
    </div>
  );
}

/** Port of `.tip` — small callout cards used for recommendations/explanations. */
export function Tip({ children }: { children: ReactNode }) {
  return (
    <div
      className="mb-2 rounded-md border p-3 text-[12px] leading-relaxed [&_strong]:font-semibold"
      style={{ background: "var(--tip-bg)", borderColor: "var(--tip-bdr)", color: "var(--tip-text)" }}
    >
      {children}
    </div>
  );
}

/** Port of `.sec-label` — the uppercase mono divider label used between chart sections. */
export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div className="my-4 flex items-center gap-2.5 font-mono text-[10px] font-medium uppercase tracking-wide text-text-tert">
      {children}
      <span className="h-px flex-1" style={{ background: "var(--border)" }} />
    </div>
  );
}
