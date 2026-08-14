export function fmtKg(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toLocaleString(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 })} kg`;
}

export function fmtT(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${(v / 1000).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })} t`;
}

export function fmtGkm(v: number | null | undefined, unit: string): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v.toLocaleString(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 })} ${unit}`;
}

export function fmtNum(v: number | null | undefined, digits = 0): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function effUnit(basis: "passenger" | "vehicle"): string {
  return basis === "passenger" ? "g/pkm" : "g/km";
}

export function isTrueish(v: unknown): boolean {
  return String(v ?? "").trim().toLowerCase() === "true" || String(v ?? "").trim() === "1";
}
