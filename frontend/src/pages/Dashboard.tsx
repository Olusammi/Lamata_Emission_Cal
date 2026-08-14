import { useMemo, useState } from "react";
import { FileText, Download } from "lucide-react";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { KpiCard } from "../components/charts/KpiCard";
import { ChartSwitcher } from "../components/charts/ChartSwitcher";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Button } from "../components/ui/button";
import { Banner, SectionLabel } from "../components/ui/banner";
import { aggBy, isRevenue, mean, sortDesc, sum } from "../lib/aggregate";
import { effUnit, fmtGkm, fmtKg, fmtT } from "../lib/format";
import { api } from "../lib/api";
import type { TripRow } from "../types";

export default function Dashboard() {
  const { rows, allRows, hasData, settings, filters, setFilter } = useData();
  const [building, setBuilding] = useState(false);
  const [reportHtml, setReportHtml] = useState<string | null>(null);

  const unit = effUnit(settings.basis);

  const stats = useMemo(() => {
    const revenue = rows.filter(isRevenue);
    return {
      totalTrips: rows.length,
      totalPax: sum(rows, "Ridership"),
      co2Total: sum(rows, "CO2_kg"),
      avgEff: mean(revenue, "CO2_g_pkm"),
      overLimit: rows.filter((r) => r.Compliance === "Over Limit").length,
      acUplift: sum(rows, "ac_uplift_kg"),
      acTrips: rows.filter((r) => String(r.AC_Status).toLowerCase() === "true").length,
    };
  }, [rows]);

  const uniqueVals = (field: keyof TripRow) => [...new Set(allRows.map((r) => String(r[field] ?? "")).filter(Boolean))].sort();

  const opCo2 = useMemo(() => sortDesc(aggBy(rows, "Operator", "CO2_kg", "sum")).slice(0, 12).map((d) => ({ Operator: d.key, CO2_kg: Math.round(d.value * 10) / 10 })), [rows]);
  const euroEff = useMemo(() => aggBy(rows, "Euro_Standard", "CO2_g_pkm", "mean").map((d) => ({ "Euro Standard": d.key, "Avg intensity": Math.round(d.value * 10) / 10 })), [rows]);
  const dailyCo2 = useMemo(() => {
    const g = aggBy(rows, "Date", "CO2_kg", "sum");
    return [...g].sort((a, b) => a.key.localeCompare(b.key)).map((d) => ({ Date: d.key, CO2_kg: Math.round(d.value * 10) / 10 }));
  }, [rows]);
  const complianceCt = useMemo(() => {
    const g = aggBy(rows, "Compliance", "Bus_ID", "count");
    return g.map((d) => ({ Status: d.key, Trips: d.value }));
  }, [rows]);
  const ageEff = useMemo(() => aggBy(rows, "Vehicle_Age_years", "CO2_g_pkm", "mean").map((d) => ({ "Vehicle age (yrs)": d.key, "Avg intensity": Math.round(d.value * 10) / 10 })), [rows]);

  const buildReport = async () => {
    setBuilding(true);
    try {
      const top = sortDesc(aggBy(rows, "Bus_ID", "CO2_kg", "sum")).slice(0, 10);
      const comp = rows.reduce<Record<string, number>>((acc, r) => {
        const k = r.Compliance ?? "N/A";
        acc[k] = (acc[k] ?? 0) + 1;
        return acc;
      }, {});
      let aiPara = "";
      try {
        const status = await api.get<{ configured: boolean }>("/ai/status");
        if (status.configured) {
          const res = await api.post<{ text: string; ok: boolean }>("/ai/report-narrative", {
            rows, pollutants: settings.pollutants, basis: settings.basis,
            methodology: settings.methodology, ambient_c: settings.ambientC,
          });
          if (res.ok) aiPara = `<h2>Executive summary</h2><p>${escapeHtml(res.text)}</p>`;
        }
      } catch {
        // AI is optional — report still builds without it
      }
      const dates = `${rows[0]?.Date ?? ""} → ${rows[rows.length - 1]?.Date ?? ""}`;
      const rowsHtml = top
        .map((t) => `<tr><td>${escapeHtml(t.key)}</td><td style="text-align:right">${t.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td></tr>`)
        .join("");
      const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Fleet Emissions Console — Summary</title>
<style>body{font-family:Arial,Helvetica,sans-serif;color:#16211c;margin:36px;}
h1{font-size:22px;border-bottom:3px solid #0E8F5F;padding-bottom:8px;}
h2{font-size:15px;margin-top:26px;color:#0E8F5F;}
table{border-collapse:collapse;width:100%;font-size:13px;}
td,th{border:1px solid #d6e5dc;padding:6px 10px;text-align:left;}
th{background:#e8f1ec;} .kpi{display:inline-block;margin:8px 22px 8px 0;}
.kpi b{font-size:20px;display:block;} .kpi span{font-size:11px;color:#667;}</style></head><body>
<h1>Fleet Emissions Console — Fleet Summary</h1>
<p>Period: ${dates} · Methodology: ${settings.methodology} · Basis: ${unit} · Ambient: ${settings.ambientC} °C</p>${aiPara}
<h2>Key figures</h2>
<div class="kpi"><b>${fmtT(stats.co2Total)}</b><span>Total CO₂</span></div>
<div class="kpi"><b>${stats.avgEff.toFixed(1)}</b><span>Avg ${unit}</span></div>
<div class="kpi"><b>${new Set(rows.map((r) => r.Bus_ID)).size.toLocaleString()}</b><span>Buses</span></div>
<div class="kpi"><b>${rows.length.toLocaleString()}</b><span>Trip rows</span></div>
<div class="kpi"><b>${stats.totalPax.toLocaleString()}</b><span>Passengers</span></div>
<h2>Compliance</h2>
<p>Good: ${(comp.Good ?? 0).toLocaleString()} · Monitor: ${(comp.Monitor ?? 0).toLocaleString()} · Over Limit: ${(comp["Over Limit"] ?? 0).toLocaleString()}</p>
<h2>Top 10 CO₂ emitters</h2>
<table><tr><th>Bus</th><th>kg CO₂</th></tr>${rowsHtml}</table>
<p style="margin-top:30px;font-size:11px;color:#889;">Generated by Fleet Emissions Console.</p>
</body></html>`;
      setReportHtml(html);
    } finally {
      setBuilding(false);
    }
  };

  const downloadReport = () => {
    if (!reportHtml) return;
    const blob = new Blob([reportHtml], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "fleet_summary_report.html";
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!hasData) {
    return <EmptyState description="Fleet-wide KPIs, compliance donut, daily emissions trend and attribute filters will appear here." />;
  }

  return (
    <div className="space-y-6">
      <Banner>
        Real-time fleet overview using <strong>{settings.methodology}</strong> methodology. Emission
        factors include Euro class corrections, vehicle age deterioration, A/C status, and engine model adjustments.
      </Banner>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <KpiCard label="Total trips" value={stats.totalTrips.toLocaleString()} />
        <KpiCard label="Total passengers" value={stats.totalPax.toLocaleString()} />
        <KpiCard label="Total CO₂" value={fmtKg(stats.co2Total)} sub={`${fmtT(stats.co2Total)} tonnes`} />
        <KpiCard label="Fleet efficiency" value={fmtGkm(stats.avgEff, unit)} />
        <KpiCard label="Over-limit trips" value={stats.overLimit} deltaTone={stats.overLimit ? "bad" : "neutral"} sub={stats.overLimit ? "need review" : undefined} />
        <KpiCard label="A/C CO₂ uplift" value={fmtKg(stats.acUplift)} sub={`${stats.acTrips} A/C trips`} />
      </div>

      <div>
        <SectionLabel>Filter by attribute — applies across all modules</SectionLabel>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <AttrSelect label="Operator" value={filters.operator} options={uniqueVals("Operator")} onChange={(v) => setFilter("operator", v)} />
          <AttrSelect label="Euro standard" value={filters.euro} options={uniqueVals("Euro_Standard")} onChange={(v) => setFilter("euro", v)} />
          <AttrSelect label="Fuel type" value={filters.fuel} options={uniqueVals("Fuel_Type")} onChange={(v) => setFilter("fuel", v)} />
          <AttrSelect label="Bus category" value={filters.category} options={uniqueVals("Bus_Category")} onChange={(v) => setFilter("category", v)} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-border bg-card p-4">
          <ChartSwitcher data={opCo2} x="Operator" y="CO2_kg" kinds={["Pie", "Bar", "Table"]} defaultKind="Pie" title="CO₂ share by operator (top 12)" yLabel="kg CO₂" sortDesc height={360} />
        </div>
        <div className="rounded-md border border-border bg-card p-4">
          <ChartSwitcher data={euroEff} x="Euro Standard" y="Avg intensity" kinds={["Bar", "Line", "Table"]} title="Average CO₂ intensity by Euro class" yLabel={unit} sortDesc height={360} />
        </div>
      </div>

      <div className="rounded-md border border-border bg-card p-4">
        <ChartSwitcher data={dailyCo2} x="Date" y="CO2_kg" kinds={["Area", "Line", "Bar", "Table"]} defaultKind="Area" title="Daily CO₂ total" yLabel="kg CO₂" height={340} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-border bg-card p-4">
          <ChartSwitcher data={complianceCt} x="Status" y="Trips" kinds={["Bar", "Pie", "Table"]} title="Trips by compliance status" yLabel="Trips" height={340} />
        </div>
        <div className="rounded-md border border-border bg-card p-4">
          <ChartSwitcher data={ageEff} x="Vehicle age (yrs)" y="Avg intensity" kinds={["Bar", "Line", "Area", "Table"]} title="CO₂ intensity vs vehicle age" yLabel={unit} height={340} />
        </div>
      </div>

      <div>
        <SectionLabel>Report</SectionLabel>
        <div className="flex items-center gap-3">
          <Button variant="secondary" disabled={building} onClick={buildReport}>
            <FileText className="h-4 w-4" />
            {building ? "Building…" : "Build summary report"}
          </Button>
          {reportHtml && (
            <Button variant="outline" onClick={downloadReport}>
              <Download className="h-4 w-4" />
              Download report (HTML)
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function AttrSelect({
  label, value, options, onChange,
}: { label: string; value: string | null; options: string[]; onChange: (v: string | null) => void }) {
  return (
    <div>
      <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">{label}</label>
      <Select value={value ?? "__all__"} onValueChange={(v) => onChange(v === "__all__" ? null : v)}>
        <SelectTrigger><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="__all__">All</SelectItem>
          {options.map((o) => (
            <SelectItem key={o} value={o}>{o}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function escapeHtml(s: string): string {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}
