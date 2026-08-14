// Small client-side CSV export helper shared by any page that lets the
// user download a filtered slice of the manifest (DataQuality, DeepSearch).
export function toCsv(rows: Record<string, unknown>[], columns: string[]): string {
  const escape = (v: unknown): string => {
    const s = v === null || v === undefined ? "" : String(v);
    if (/[",\r\n]/.test(s)) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };
  const header = columns.map(escape).join(",");
  const lines = rows.map((r) => columns.map((c) => escape(r[c])).join(","));
  return [header, ...lines].join("\r\n");
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
