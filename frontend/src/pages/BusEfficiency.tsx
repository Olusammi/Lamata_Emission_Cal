import { useMemo } from "react";
import Plot from "../components/charts/PlotlyPlot";
import type { Data } from "plotly.js";
import { AlertTriangle } from "lucide-react";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { Banner, SectionLabel, Tip } from "../components/ui/banner";
import { ComplianceBadge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { plotlyBase, PALETTE } from "../components/charts/theme";
import { groupBy, isRevenue, mean, sum } from "../lib/aggregate";
import { effUnit } from "../lib/format";
import type { Basis, TripRow } from "../types";

const PASSENGER_THRESHOLDS: Record<string, [number, number]> = {
  "High Capacity": [30, 55],
  Midi: [45, 75],
  Mini: [60, 95],
};
const VEHICLE_THRESHOLDS: Record<string, [number, number]> = {
  "High Capacity": [1500, 2100],
  Midi: [1000, 1400],
  Mini: [500, 750],
};

function complianceFlag(gpkm: number, category: string, basis: Basis): "Good" | "Monitor" | "Over Limit" {
  const table = basis === "passenger" ? PASSENGER_THRESHOLDS : VEHICLE_THRESHOLDS;
  const fallback: [number, number] = basis === "passenger" ? [40, 70] : [1200, 1700];
  const t = table[category] ?? fallback;
  if (gpkm <= t[0]) return "Good";
  if (gpkm <= t[1]) return "Monitor";
  return "Over Limit";
}

export default function BusEfficiency() {
  const { rows, hasData, settings } = useData();
  const unit = effUnit(settings.basis);
  const co2On = settings.pollutants.includes("CO2");

  const revenueRows = useMemo(() => rows.filter(isRevenue), [rows]);

  const categoryFuelEuroGroups = useMemo(() => {
    const g = groupBy(revenueRows, (r) => `${r.Bus_Category}||${r.Fuel_Type}||${r.Euro_Standard ?? "—"}`);
    return [...g.entries()].map(([key, bucket]) => {
      const [category, fuel, euro] = key.split("||");
      const avgGpkm = mean(bucket, "CO2_g_pkm");
      return {
        category,
        fuel,
        euro,
        avgGpkm,
        totalKg: sum(bucket, "CO2_kg"),
        trips: bucket.length,
        totalRidership: sum(bucket, "Ridership"),
        avgAge: mean(bucket, "Vehicle_Age_years"),
        compliance: complianceFlag(avgGpkm, category, settings.basis),
      };
    }).sort((a, b) => a.avgGpkm - b.avgGpkm);
  }, [revenueRows, settings.basis]);

  const categoryEuro = useMemo(() => {
    const g = groupBy(revenueRows, (r) => `${r.Bus_Category}||${r.Euro_Standard ?? "—"}`);
    return [...g.entries()].map(([key, bucket]) => {
      const [category, euro] = key.split("||");
      return { category, euro, avgGpkm: Math.round(mean(bucket, "CO2_g_pkm") * 10) / 10 };
    });
  }, [revenueRows]);

  const categoryEuroTraces = useMemo<Data[]>(() => {
    const euroValues = [...new Set(categoryEuro.map((r) => r.euro))];
    return euroValues.map((euro, i) => {
      const bucket = categoryEuro.filter((r) => r.euro === euro);
      return {
        type: "bar",
        name: euro,
        x: bucket.map((r) => r.category),
        y: bucket.map((r) => r.avgGpkm),
        text: bucket.map((r) => `${r.avgGpkm.toFixed(1)}`),
        textposition: "outside",
        marker: { color: PALETTE[i % PALETTE.length] },
      } as Data;
    });
  }, [categoryEuro]);

  const loadScatter = useMemo<Data[]>(() => {
    const valid = revenueRows.filter((r) => typeof r.load_factor === "number" && typeof r.CO2_g_pkm === "number");
    const categories = [...new Set(valid.map((r) => String(r.Bus_Category ?? "—")))];
    return categories.map((cat, i) => {
      const bucket = valid.filter((r) => String(r.Bus_Category ?? "—") === cat);
      return {
        type: "scatter",
        mode: "markers",
        name: cat,
        x: bucket.map((r) => r.load_factor),
        y: bucket.map((r) => r.CO2_g_pkm),
        marker: {
          color: PALETTE[i % PALETTE.length],
          size: bucket.map((r) => Math.max(6, Math.min(30, Number(r.Route_Distance_km ?? 0) / 2))),
        },
      } as Data;
    });
  }, [revenueRows]);

  const busRanking = useMemo(() => {
    const g = groupBy(revenueRows, (r) => r.Bus_ID);
    const list = [...g.entries()].map(([busId, bucket]) => {
      const gpkm = mean(bucket, "CO2_g_pkm");
      const first: TripRow = bucket[0];
      return {
        busId,
        gpkm,
        totalKg: sum(bucket, "CO2_kg"),
        trips: bucket.length,
        operator: String(first.Operator ?? "—"),
        category: String(first.Bus_Category ?? "—"),
        fuel: String(first.Fuel_Type ?? "—"),
        euro: String(first.Euro_Standard ?? "—"),
        age: first.Vehicle_Age_years,
        compliance: complianceFlag(gpkm, String(first.Bus_Category ?? ""), settings.basis),
      };
    });
    return list.sort((a, b) => a.gpkm - b.gpkm);
  }, [revenueRows, settings.basis]);

  const overLimitGroups = useMemo(
    () => categoryFuelEuroGroups.filter((g) => g.compliance === "Over Limit"),
    [categoryFuelEuroGroups]
  );

  if (!hasData) {
    return <EmptyState description="Per-category efficiency rankings, compliance status and load-factor diagnostics will appear here." />;
  }

  if (!co2On) {
    return (
      <div className="space-y-4">
        <Banner>
          Efficiency is measured as CO₂ grams per {settings.basis === "passenger" ? "passenger-km" : "vehicle-km"}{" "}
          (<strong>{unit}</strong>) — lower is better.
        </Banner>
        <div className="rounded-md border border-border bg-card p-4 text-sm text-text-sec">
          Enable CO₂ in the sidebar to view efficiency metrics.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Banner>
        Efficiency is measured as CO₂ grams per {settings.basis === "passenger" ? "passenger-km" : "vehicle-km"} (
        <strong>{unit}</strong>) — lower is better. Compliance thresholds
        {settings.basis === "passenger"
          ? ": High Capacity ≤30 Good / ≤55 Monitor; Midi ≤45 / ≤75; Mini ≤60 / ≤95."
          : ": High Capacity ≤1500 Good / ≤2100 Monitor; Midi ≤1000 / ≤1400; Mini ≤500 / ≤750."}
      </Banner>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="rounded-md border border-border bg-card p-4 lg:col-span-2">
          <Plot
            data={categoryEuroTraces}
            layout={{
              ...plotlyBase(),
              height: 360,
              barmode: "group",
              title: { text: "Average CO₂ per passenger-km by category" },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%", height: 360 }}
            useResizeHandler
          />
        </div>
        <div className="max-h-[360px] overflow-auto rounded-md border border-border">
          <table className="w-full font-mono text-xs">
            <thead className="sticky top-0 bg-card2">
              <tr>
                <th className="px-2 py-2 text-left text-text-tert">Category</th>
                <th className="px-2 py-2 text-left text-text-tert">Fuel</th>
                <th className="px-2 py-2 text-right text-text-tert">{unit}</th>
                <th className="px-2 py-2 text-left text-text-tert">Status</th>
              </tr>
            </thead>
            <tbody>
              {categoryFuelEuroGroups.map((g) => (
                <tr key={`${g.category}-${g.fuel}-${g.euro}`} className="border-t border-border/50">
                  <td className="px-2 py-1.5 text-text-sec">{g.category}</td>
                  <td className="px-2 py-1.5 text-text-sec">{g.fuel}</td>
                  <td className="px-2 py-1.5 text-right text-text-prim">{g.avgGpkm.toFixed(1)}</td>
                  <td className="px-2 py-1.5"><ComplianceBadge flag={g.compliance} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-md border border-border bg-card p-4">
        <Plot
          data={loadScatter}
          layout={{
            ...plotlyBase(),
            height: 360,
            title: { text: "Load factor vs CO₂ intensity — fill your buses" },
            xaxis: { ...plotlyBase().xaxis, title: { text: "Load factor" } },
            yaxis: { ...plotlyBase().yaxis, title: { text: unit } },
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%", height: 360 }}
          useResizeHandler
        />
      </div>

      <div>
        <SectionLabel>Per-bus efficiency ranking</SectionLabel>
        <div className="max-h-96 overflow-auto rounded-md border border-border">
          <table className="w-full font-mono text-xs">
            <thead className="sticky top-0 bg-card2">
              <tr>
                <th className="px-2 py-2 text-left text-text-tert">Bus ID</th>
                <th className="px-2 py-2 text-left text-text-tert">Operator</th>
                <th className="px-2 py-2 text-left text-text-tert">Category</th>
                <th className="px-2 py-2 text-left text-text-tert">Fuel</th>
                <th className="px-2 py-2 text-left text-text-tert">Euro</th>
                <th className="px-2 py-2 text-right text-text-tert">Age</th>
                <th className="px-2 py-2 text-left text-text-tert">{unit}</th>
                <th className="px-2 py-2 text-right text-text-tert">Trips</th>
                <th className="px-2 py-2 text-right text-text-tert">Total kg</th>
                <th className="px-2 py-2 text-left text-text-tert">Status</th>
              </tr>
            </thead>
            <tbody>
              {busRanking.map((b) => (
                <tr key={b.busId} className="border-t border-border/50">
                  <td className="px-2 py-1.5 text-text-sec">{b.busId}</td>
                  <td className="px-2 py-1.5 text-text-sec">{b.operator}</td>
                  <td className="px-2 py-1.5 text-text-sec">{b.category}</td>
                  <td className="px-2 py-1.5 text-text-sec">{b.fuel}</td>
                  <td className="px-2 py-1.5 text-text-sec">{b.euro}</td>
                  <td className="px-2 py-1.5 text-right text-text-sec">{b.age ?? "—"}</td>
                  <td className="px-2 py-1.5">
                    <div className="flex items-center gap-2">
                      <Progress value={Math.min(100, (b.gpkm / 200) * 100)} className="w-16" />
                      <span className="text-text-prim">{b.gpkm.toFixed(1)}</span>
                    </div>
                  </td>
                  <td className="px-2 py-1.5 text-right text-text-sec">{b.trips}</td>
                  <td className="px-2 py-1.5 text-right text-text-sec">{b.totalKg.toFixed(1)}</td>
                  <td className="px-2 py-1.5"><ComplianceBadge flag={b.compliance} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {overLimitGroups.length > 0 && (
        <div>
          <SectionLabel>
            <span className="inline-flex items-center gap-1.5">
              <AlertTriangle className="h-3 w-3" />
              Recommended actions
            </span>
          </SectionLabel>
          {overLimitGroups.map((g) => (
            <Tip key={`${g.category}-${g.fuel}-${g.euro}`}>
              <strong>{g.category} / {g.fuel}</strong> averaging <strong>{g.avgGpkm.toFixed(1)} g/pkm</strong>. Upgrade
              to Euro V or VI (−50–95% NOx), reduce terminal idle time, or increase ridership via dynamic scheduling.
            </Tip>
          ))}
        </div>
      )}
    </div>
  );
}
