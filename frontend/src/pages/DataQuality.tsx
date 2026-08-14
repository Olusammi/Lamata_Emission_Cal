import { useMemo, useState } from "react";
import { Circle, CheckCircle2, Download } from "lucide-react";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { KpiCard } from "../components/charts/KpiCard";
import { Banner, SectionLabel } from "../components/ui/banner";
import { Progress } from "../components/ui/progress";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toCsv, downloadCsv } from "../lib/csv";
import type { TripRow } from "../types";

type Severity = "Critical" | "Warning" | "Info";

interface QCheck {
  severity: Severity;
  name: string;
  mask: (r: TripRow) => boolean;
  why: string;
}

const CAPACITY_MAP: Record<string, number> = {
  "High Capacity": 150,
  HC: 150,
  Midi: 80,
  MIDI: 80,
  Mini: 18,
  MINI: 18,
  FLM: 18,
};

function capacityFor(category: unknown): number {
  return CAPACITY_MAP[String(category ?? "")] ?? 80;
}

const SEVERITY_COLOR: Record<Severity, string> = {
  Critical: "text-over",
  Warning: "text-monitor",
  Info: "text-accent",
};

const CANDIDATE_COLUMNS = [
  "Date", "Bus_ID", "Operator", "Route_Name", "Route_Distance_km", "Num_Trips_Today",
  "Avg_Speed_kmh", "Ridership", "Bus_Category", "Fuel_Type", "Euro_Standard",
];

function buildChecks(rows: TripRow[]): QCheck[] {
  const dupKey = (r: TripRow) => `${r.Date ?? ""}||${r.Bus_ID ?? ""}||${r.Route_Name ?? ""}`;
  const dupCounts = new Map<string, number>();
  for (const r of rows) {
    const k = dupKey(r);
    dupCounts.set(k, (dupCounts.get(k) ?? 0) + 1);
  }

  return [
    {
      severity: "Critical",
      name: "Non-positive distance",
      mask: (r) => (r.Route_Distance_km ?? 0) <= 0,
      why: "Zero/negative distance makes every per-km figure meaningless for the row.",
    },
    {
      severity: "Critical",
      name: "Ridership exceeds physical capacity",
      mask: (r) => {
        const trips = r.Num_Trips_Today || 1;
        const paxTrip = (r.Ridership ?? 0) / trips;
        return paxTrip > capacityFor(r.Bus_Category) * 1.3;
      },
      why: "More passengers per trip than 130% of the bus's capacity — likely a daily-vs-trip mixup.",
    },
    {
      severity: "Warning",
      name: "Implausible trip distance (>120 km per trip)",
      mask: (r) => {
        const trips = r.Num_Trips_Today || 1;
        const tripKm = (r.Route_Distance_km ?? 0) / trips;
        return tripKm > 120;
      },
      why: "A single urban trip longer than 120 km suggests the distance column holds something else.",
    },
    {
      severity: "Warning",
      name: "Speed outlier (<5 or >90 km/h)",
      mask: (r) => typeof r.Avg_Speed_kmh === "number" && (r.Avg_Speed_kmh < 5 || r.Avg_Speed_kmh > 90),
      why: "Outside the range the COPERT speed curves are valid for — the engine clamps it, but the input is suspect.",
    },
    {
      severity: "Warning",
      name: "Fractional trip counts",
      mask: (r) => (r.Num_Trips_Today ?? 0) % 1 !== 0,
      why: "Half a trip doesn't exist — usually a sign of averaged or interpolated source data.",
    },
    {
      severity: "Warning",
      name: "Duplicate Date + Bus + Route rows",
      mask: (r) => (dupCounts.get(dupKey(r)) ?? 0) > 1,
      why: "The same bus-day counted twice inflates totals.",
    },
    {
      severity: "Info",
      name: "Unrecognised bus category",
      mask: (r) => r.Category_Unmapped === true,
      why: "Fell back to default emission factors.",
    },
    {
      severity: "Info",
      name: "Unrecognised fuel type",
      mask: (r) => r.Fuel_Unmapped === true,
      why: "Fell back to default emission factors.",
    },
    {
      severity: "Info",
      name: "Missing Euro standard",
      mask: (r) => !String(r.Euro_Standard ?? "").startsWith("Euro"),
      why: "Defaults to Euro III — NOx/PM for these rows are an assumption, not data.",
    },
  ];
}

export default function DataQuality() {
  const { rows, hasData } = useData();

  const checks = useMemo(() => buildChecks(rows), [rows]);

  const findings = useMemo(
    () =>
      checks.map((c) => {
        const affected = rows.filter(c.mask);
        return {
          ...c,
          affected,
          count: affected.length,
          pct: rows.length ? (affected.length / rows.length) * 100 : 0,
        };
      }),
    [checks, rows]
  );

  const [selectedName, setSelectedName] = useState<string>(() => checks[0]?.name ?? "");
  const selected = findings.find((f) => f.name === selectedName) ?? findings[0];

  const existingCols = useMemo(
    () => CANDIDATE_COLUMNS.filter((c) => rows.some((r) => r[c] !== undefined && r[c] !== null && r[c] !== "")),
    [rows]
  );

  const criticalCount = findings.filter((f) => f.severity === "Critical" && f.count > 0).length;
  const warningCount = findings.filter((f) => f.severity === "Warning" && f.count > 0).length;

  if (!hasData) {
    return <EmptyState description="Data-quality findings — impossible values, outliers, duplicates and unmapped codes — will appear here." />;
  }

  const handleDownload = () => {
    if (!selected) return;
    const csv = toCsv(selected.affected, existingCols);
    downloadCsv(`${selected.name.replace(/[^a-z0-9]+/gi, "_").toLowerCase()}_affected_rows.csv`, csv);
  };

  return (
    <div className="space-y-4">
      <Banner>
        A compliance tool is only as credible as its inputs. This module validates every loaded row and names what it
        finds — <strong>impossible values</strong>, <strong>outliers</strong>, <strong>duplicates</strong> and{" "}
        <strong>unmapped codes</strong> — with severity and affected-row counts.
      </Banner>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard label="Rows checked" value={rows.length.toLocaleString()} />
        <KpiCard
          label="Critical findings"
          value={criticalCount}
          deltaTone={criticalCount ? "bad" : "neutral"}
          sub={criticalCount ? "need review" : undefined}
        />
        <KpiCard label="Warnings" value={warningCount} deltaTone={warningCount ? "bad" : "neutral"} />
        <KpiCard label="Checks run" value={checks.length} />
      </div>

      <div>
        <SectionLabel>Findings</SectionLabel>
        <div className="overflow-auto rounded-md border border-border">
          <table className="w-full font-mono text-xs">
            <thead className="sticky top-0 bg-card2">
              <tr>
                <th className="px-3 py-2 text-left text-text-tert">Severity</th>
                <th className="px-3 py-2 text-left text-text-tert">Check</th>
                <th className="px-3 py-2 text-right text-text-tert">Rows affected</th>
                <th className="px-3 py-2 text-left text-text-tert">% of data</th>
              </tr>
            </thead>
            <tbody>
              {findings.map((f) => (
                <tr key={f.name} className="border-t border-border/50">
                  <td className="px-3 py-1.5">
                    <span className="inline-flex items-center gap-1.5">
                      <Circle className={`h-2.5 w-2.5 ${SEVERITY_COLOR[f.severity]}`} fill="currentColor" />
                      {f.severity}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-text-sec">{f.name}</td>
                  <td className="px-3 py-1.5 text-right text-text-prim">{f.count.toLocaleString()}</td>
                  <td className="px-3 py-1.5">
                    <div className="flex items-center gap-2">
                      <Progress value={f.pct} className="w-24" />
                      <span className="text-text-sec">{f.pct.toFixed(1)}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <SectionLabel>Inspect a finding</SectionLabel>
        <div className="mb-3 max-w-xs">
          <Select value={selectedName || checks[0]?.name} onValueChange={setSelectedName}>
            <SelectTrigger><SelectValue placeholder="Finding" /></SelectTrigger>
            <SelectContent>
              {checks.map((c) => (
                <SelectItem key={c.name} value={c.name}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {selected && (
          <>
            <p className="mb-3 text-[12px] leading-relaxed text-text-sec">{selected.why}</p>
            {selected.count === 0 ? (
              <div className="flex items-center gap-2 rounded-md border border-border bg-good-bg px-3 py-2.5 text-sm text-good">
                <CheckCircle2 className="h-4 w-4" />
                No rows triggered this check.
              </div>
            ) : (
              <>
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[11px] text-text-tert">
                    Showing {Math.min(200, selected.count).toLocaleString()} of {selected.count.toLocaleString()} affected rows
                  </span>
                  <Button variant="secondary" size="sm" onClick={handleDownload}>
                    <Download className="h-3.5 w-3.5" />
                    Download affected rows (CSV)
                  </Button>
                </div>
                <div className="max-h-96 overflow-auto rounded-md border border-border">
                  <table className="w-full font-mono text-xs">
                    <thead className="sticky top-0 bg-card2">
                      <tr>
                        {existingCols.map((c) => (
                          <th key={c} className="px-3 py-2 text-left text-text-tert">{c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {selected.affected.slice(0, 200).map((r, i) => (
                        <tr key={i} className="border-t border-border/50">
                          {existingCols.map((c) => (
                            <td key={c} className="px-3 py-1.5 text-text-sec">{String(r[c] ?? "")}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
