import { useMemo, useState, type ReactNode } from "react";
import { Download } from "lucide-react";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { Banner, SectionLabel } from "../components/ui/banner";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Checkbox } from "../components/ui/checkbox";
import { Progress } from "../components/ui/progress";
import { Button } from "../components/ui/button";
import { ComplianceBadge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { isRevenue } from "../lib/aggregate";
import { fmtNum } from "../lib/format";
import { toCsv, downloadCsv } from "../lib/csv";
import type { TripRow } from "../types";

const ALL_COLUMNS = [
  "Date", "Bus_ID", "Route_Name", "Operator", "Bus_Category", "Fuel_Type", "Euro_Standard",
  "Vehicle_Age_years", "AC_Status", "Engine_Model", "Num_Trips_Today", "Route_Distance_km",
  "Avg_Speed_kmh", "Ridership", "load_factor", "CO2_kg", "NOx_kg", "PM_kg", "CO2_g_pkm",
  "Compliance", "Category_Unmapped", "Fuel_Unmapped",
];

const COMPLIANCE_OPTIONS = ["All", "Good", "Monitor", "Over Limit", "N/A"];

function renderCell(col: string, row: TripRow): ReactNode {
  const v = row[col];
  switch (col) {
    case "CO2_kg":
      return fmtNum(v as number | null | undefined, 3);
    case "NOx_kg":
      return fmtNum(v as number | null | undefined, 4);
    case "PM_kg":
      return fmtNum(v as number | null | undefined, 5);
    case "CO2_g_pkm":
      return fmtNum(v as number | null | undefined, 1);
    case "load_factor": {
      const n = Math.min(1, Math.max(0, Number(v ?? 0)));
      return (
        <div className="flex items-center gap-2">
          <Progress value={n * 100} className="w-16" />
          <span>{n.toFixed(2)}</span>
        </div>
      );
    }
    case "Compliance":
      return <ComplianceBadge flag={row.Compliance} />;
    case "Category_Unmapped":
    case "Fuel_Unmapped":
      return v ? "Yes" : "No";
    default:
      return String(v ?? "—");
  }
}

export default function DeepSearch() {
  const { rows, hasData } = useData();

  const [dateStart, setDateStart] = useState("");
  const [dateEnd, setDateEnd] = useState("");
  const [operatorQuery, setOperatorQuery] = useState("");
  const [categoryQuery, setCategoryQuery] = useState("");
  const [fuelQuery, setFuelQuery] = useState("");
  const [euroQuery, setEuroQuery] = useState("");
  const [busIdQuery, setBusIdQuery] = useState("");
  const [complianceFilter, setComplianceFilter] = useState("All");
  const [revenueOnly, setRevenueOnly] = useState(false);
  const [unmappedOnly, setUnmappedOnly] = useState(false);

  const dateBounds = useMemo(() => {
    const dates = rows.map((r) => r.Date).filter((d): d is string => !!d).sort();
    return { min: dates[0] ?? "", max: dates[dates.length - 1] ?? "" };
  }, [rows]);

  const out = useMemo(() => {
    const effStart = dateStart || dateBounds.min;
    const effEnd = dateEnd || dateBounds.max;
    return rows.filter((r) => {
      if (effStart && r.Date && r.Date < effStart) return false;
      if (effEnd && r.Date && r.Date > effEnd) return false;
      if (operatorQuery && !String(r.Operator ?? "").toLowerCase().includes(operatorQuery.toLowerCase())) return false;
      if (categoryQuery && !String(r.Bus_Category ?? "").toLowerCase().includes(categoryQuery.toLowerCase())) return false;
      if (fuelQuery && !String(r.Fuel_Type ?? "").toLowerCase().includes(fuelQuery.toLowerCase())) return false;
      if (euroQuery && !String(r.Euro_Standard ?? "").toLowerCase().includes(euroQuery.toLowerCase())) return false;
      if (busIdQuery && !String(r.Bus_ID ?? "").toLowerCase().includes(busIdQuery.toLowerCase())) return false;
      if (complianceFilter !== "All" && (r.Compliance ?? "N/A") !== complianceFilter) return false;
      if (revenueOnly && !isRevenue(r)) return false;
      if (unmappedOnly && !(r.Category_Unmapped || r.Fuel_Unmapped)) return false;
      return true;
    });
  }, [rows, dateStart, dateEnd, dateBounds, operatorQuery, categoryQuery, fuelQuery, euroQuery, busIdQuery, complianceFilter, revenueOnly, unmappedOnly]);

  const existingCols = useMemo(
    () => ALL_COLUMNS.filter((c) => rows.some((r) => r[c] !== undefined && r[c] !== null && r[c] !== "")),
    [rows]
  );

  if (!hasData) {
    return <EmptyState description="Filter and export the full calculated manifest — every emission column, every trip." />;
  }

  const handleDownload = () => {
    const csv = toCsv(out, existingCols);
    downloadCsv("deep_search_export.csv", csv);
  };

  return (
    <div className="space-y-4">
      <Banner>
        Filter and export the full calculated manifest. All emission columns reflect current sidebar{" "}
        <strong>methodology</strong>, <strong>pollutants</strong>, and quick filters.
      </Banner>

      <div>
        <SectionLabel>Advanced filters</SectionLabel>
        <div className="rounded-md border border-border bg-card p-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <Label className="mb-1 block">Date start</Label>
              <Input type="date" value={dateStart || dateBounds.min} onChange={(e) => setDateStart(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1 block">Date end</Label>
              <Input type="date" value={dateEnd || dateBounds.max} onChange={(e) => setDateEnd(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1 block">Operator</Label>
              <Input placeholder="Search operator…" value={operatorQuery} onChange={(e) => setOperatorQuery(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1 block">Bus ID</Label>
              <Input placeholder="Search bus ID…" value={busIdQuery} onChange={(e) => setBusIdQuery(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1 block">Bus category</Label>
              <Input placeholder="Search category…" value={categoryQuery} onChange={(e) => setCategoryQuery(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1 block">Fuel type</Label>
              <Input placeholder="Search fuel type…" value={fuelQuery} onChange={(e) => setFuelQuery(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1 block">Euro standard</Label>
              <Input placeholder="Search Euro standard…" value={euroQuery} onChange={(e) => setEuroQuery(e.target.value)} />
            </div>
            <div>
              <Label className="mb-1 block">Compliance</Label>
              <Select value={complianceFilter} onValueChange={setComplianceFilter}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {COMPLIANCE_OPTIONS.map((o) => (
                    <SelectItem key={o} value={o}>{o}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-6">
            <div className="flex items-center gap-2">
              <Checkbox id="revenue-only" checked={revenueOnly} onCheckedChange={(v) => setRevenueOnly(v === true)} />
              <Label htmlFor="revenue-only" className="cursor-pointer normal-case tracking-normal text-text-sec">Revenue trips only</Label>
            </div>
            <div className="flex items-center gap-2">
              <Checkbox id="unmapped-only" checked={unmappedOnly} onCheckedChange={(v) => setUnmappedOnly(v === true)} />
              <Label htmlFor="unmapped-only" className="cursor-pointer normal-case tracking-normal text-text-sec">Unmapped category/fuel only</Label>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <span className="text-[12px] text-text-sec">
          {out.length.toLocaleString()} records matched of {rows.length.toLocaleString()} total
        </span>
        <Button variant="secondary" size="sm" onClick={handleDownload}>
          <Download className="h-3.5 w-3.5" />
          Download CSV
        </Button>
      </div>

      {out.length > 500 && (
        <p className="text-[11px] text-text-tert">
          Showing first 500 of {out.length.toLocaleString()} — refine filters or export the full CSV.
        </p>
      )}

      <div className="max-h-[32rem] overflow-auto rounded-md border border-border">
        <table className="w-full font-mono text-xs">
          <thead className="sticky top-0 bg-card2">
            <tr>
              {existingCols.map((c) => (
                <th key={c} className="whitespace-nowrap px-3 py-2 text-left text-text-tert">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {out.slice(0, 500).map((r, i) => (
              <tr key={i} className="border-t border-border/50">
                {existingCols.map((c) => (
                  <td key={c} className="whitespace-nowrap px-3 py-1.5 text-text-sec">{renderCell(c, r)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
