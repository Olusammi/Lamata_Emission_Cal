// Small client-side aggregation helpers — the JS equivalent of the
// pandas .groupby(...).agg(...) calls scattered through the original
// app.py modules. Used for chart data so filtering/aggregation never
// needs a server round trip.
import type { TripRow } from "../types";

export function groupBy<T, K extends string | number>(rows: T[], keyFn: (r: T) => K): Map<K, T[]> {
  const out = new Map<K, T[]>();
  for (const r of rows) {
    const k = keyFn(r);
    const bucket = out.get(k);
    if (bucket) bucket.push(r);
    else out.set(k, [r]);
  }
  return out;
}

export function sum(rows: TripRow[], field: string): number {
  let total = 0;
  for (const r of rows) {
    const v = r[field];
    if (typeof v === "number" && !Number.isNaN(v)) total += v;
  }
  return total;
}

export function mean(rows: TripRow[], field: string): number {
  const vals = rows.map((r) => r[field]).filter((v): v is number => typeof v === "number" && !Number.isNaN(v));
  if (!vals.length) return 0;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

export function median(rows: TripRow[], field: string): number {
  const vals = rows.map((r) => r[field]).filter((v): v is number => typeof v === "number" && !Number.isNaN(v)).sort((a, b) => a - b);
  if (!vals.length) return 0;
  const mid = Math.floor(vals.length / 2);
  return vals.length % 2 ? vals[mid] : (vals[mid - 1] + vals[mid]) / 2;
}

export function nunique(rows: TripRow[], field: string): number {
  return new Set(rows.map((r) => r[field])).size;
}

export function countBy(rows: TripRow[], field: string): { key: string; count: number }[] {
  const g = groupBy(rows, (r) => String(r[field] ?? "—"));
  return [...g.entries()].map(([key, v]) => ({ key, count: v.length }));
}

/** groupBy one field, then sum/mean/count a value field — the most common pattern in the charts. */
export function aggBy(
  rows: TripRow[],
  byField: string,
  valueField: string,
  op: "sum" | "mean" | "count" | "nunique" = "sum"
): { key: string; value: number }[] {
  const g = groupBy(rows, (r) => String(r[byField] ?? "—"));
  return [...g.entries()].map(([key, bucket]) => ({
    key,
    value:
      op === "sum" ? sum(bucket, valueField) :
      op === "mean" ? mean(bucket, valueField) :
      op === "nunique" ? nunique(bucket, valueField) :
      bucket.length,
  }));
}

export function sortDesc<T extends { value: number }>(items: T[]): T[] {
  return [...items].sort((a, b) => b.value - a.value);
}

export function topN<T>(items: T[], n: number): T[] {
  return items.slice(0, n);
}

export const isRevenue = (r: TripRow) => String(r.Revenue_Trip ?? "").toLowerCase() === "true" || r.Revenue_Trip === true;
