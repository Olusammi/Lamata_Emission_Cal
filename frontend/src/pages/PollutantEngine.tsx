import { useMemo } from "react";
import Plot from "../components/charts/PlotlyPlot";
import type { Data } from "plotly.js";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { KpiCard } from "../components/charts/KpiCard";
import { ChartSwitcher } from "../components/charts/ChartSwitcher";
import { Banner, SectionLabel } from "../components/ui/banner";
import { plotlyBase, PALETTE } from "../components/charts/theme";
import { aggBy, mean, sortDesc, sum } from "../lib/aggregate";
import { effUnit, fmtKg } from "../lib/format";
import type { TripRow } from "../types";

const SYMBOLS = ["circle", "square", "diamond", "cross", "x", "triangle-up", "triangle-down", "star"];

export default function PollutantEngine() {
  const { rows, hasData, settings } = useData();
  const unit = effUnit(settings.basis);

  const operatorMelt = useMemo(() => {
    const top = sortDesc(aggBy(rows, "Operator", "CO2_kg", "sum")).slice(0, 10).map((d) => d.key);
    const out: { Operator: string; Pollutant: string; kg: number }[] = [];
    for (const op of top) {
      const bucket = rows.filter((r) => String(r.Operator ?? "—") === op);
      for (const pol of settings.pollutants) {
        out.push({ Operator: op, Pollutant: pol, kg: Math.round(sum(bucket, `${pol}_kg`) * 10) / 10 });
      }
    }
    return out;
  }, [rows, settings.pollutants]);

  const fuelMelt = useMemo(() => {
    const fuels = [...new Set(rows.map((r) => String(r.Fuel_Type ?? "")).filter(Boolean))].sort();
    const out: { Fuel_Type: string; Pollutant: string; kg: number }[] = [];
    for (const fuel of fuels) {
      const bucket = rows.filter((r) => r.Fuel_Type === fuel);
      for (const pol of settings.pollutants) {
        out.push({ Fuel_Type: fuel, Pollutant: pol, kg: Math.round(sum(bucket, `${pol}_kg`) * 10) / 10 });
      }
    }
    return out;
  }, [rows, settings.pollutants]);

  const noxScatter = useMemo(() => {
    if (!settings.pollutants.includes("NOx")) return null;
    const valid = rows.filter((r) => typeof r.Avg_Speed_kmh === "number" && typeof r.NOx_g_pkm === "number");
    if (!valid.length) return null;
    const hasEuro = valid.some((r) => r.Euro_Standard);
    const colorField: keyof TripRow = hasEuro ? "Euro_Standard" : "Bus_Category";
    const categories = [...new Set(valid.map((r) => String(r.Bus_Category ?? "—")))];
    const symbolMap = new Map(categories.map((c, i) => [c, SYMBOLS[i % SYMBOLS.length]]));
    const groups = [...new Set(valid.map((r) => String(r[colorField] ?? "—")))];
    const traces: Data[] = groups.map((g, i) => {
      const bucket = valid.filter((r) => String(r[colorField] ?? "—") === g);
      return {
        type: "scatter",
        mode: "markers",
        name: g,
        x: bucket.map((r) => r.Avg_Speed_kmh),
        y: bucket.map((r) => r.NOx_g_pkm),
        marker: {
          color: PALETTE[i % PALETTE.length],
          size: bucket.map((r) => Math.max(6, Math.min(30, Math.sqrt(Number(r.Ridership ?? 0))))),
          symbol: bucket.map((r) => symbolMap.get(String(r.Bus_Category ?? "—")) ?? "circle"),
        },
      } as Data;
    });
    return traces;
  }, [rows, settings.pollutants]);

  const heatmap = useMemo(() => {
    if (!settings.pollutants.includes("CO2")) return null;
    if (!rows.some((r) => r.Euro_Standard)) return null;
    const euroValues = [...new Set(rows.map((r) => String(r.Euro_Standard ?? "")).filter(Boolean))].sort();
    const fuelValues = [...new Set(rows.map((r) => String(r.Fuel_Type ?? "")).filter(Boolean))].sort();
    if (!euroValues.length || !fuelValues.length) return null;
    const z = euroValues.map((euro) =>
      fuelValues.map((fuel) => {
        const bucket = rows.filter((r) => r.Euro_Standard === euro && r.Fuel_Type === fuel);
        return bucket.length ? Math.round(mean(bucket, "CO2_g_pkm") * 10) / 10 : 0;
      })
    );
    return { euroValues, fuelValues, z };
  }, [rows, settings.pollutants]);

  if (!hasData) {
    return (
      <EmptyState description="Per-pollutant volumes by operator and fuel type, plus speed/Euro-class NOx diagnostics, will appear here." />
    );
  }

  return (
    <div className="space-y-4">
      <Banner>
        <strong>CO₂</strong> via IPCC Tier 2 stoichiometric. <strong>NOx</strong> and <strong>PM</strong> via COPERT V
        speed functions × Euro class multiplier × age deterioration. Electric buses: Scope 2 only (Nigeria grid 0.46
        kg CO₂e/kWh).
      </Banner>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {settings.pollutants.map((pol) => (
          <KpiCard key={pol} label={`Total ${pol}`} value={fmtKg(sum(rows, `${pol}_kg`))} />
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-border bg-card p-4">
          <ChartSwitcher
            data={operatorMelt}
            x="Operator"
            y="kg"
            color="Pollutant"
            kinds={["Bar", "Line", "Table"]}
            title="Pollutant volume by operator (top 10)"
            yLabel="kg"
          />
        </div>
        <div className="rounded-md border border-border bg-card p-4">
          <ChartSwitcher
            data={fuelMelt}
            x="Fuel_Type"
            y="kg"
            color="Pollutant"
            kinds={["Bar", "Area", "Table"]}
            barmode="stack"
            title="Pollutant volume by fuel type"
            yLabel="kg"
          />
        </div>
      </div>

      {noxScatter && (
        <div>
          <SectionLabel>Speed vs NOx intensity</SectionLabel>
          <div className="rounded-md border border-border bg-card p-4">
            <Plot
              data={noxScatter}
              layout={{
                ...plotlyBase(),
                height: 380,
                title: { text: "Speed vs NOx intensity — Euro class differentiation" },
                xaxis: { ...plotlyBase().xaxis, title: { text: "Avg speed (km/h)" } },
                yaxis: { ...plotlyBase().yaxis, title: { text: "NOx g/pkm" } },
              }}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%", height: 380 }}
              useResizeHandler
            />
          </div>
        </div>
      )}

      {heatmap && (
        <div>
          <SectionLabel>Euro class × Fuel type CO₂ heatmap</SectionLabel>
          <div className="rounded-md border border-border bg-card p-4">
            <Plot
              data={[
                {
                  type: "heatmap",
                  z: heatmap.z,
                  x: heatmap.fuelValues,
                  y: heatmap.euroValues,
                  colorscale: [
                    [0, "#22c55e"],
                    [0.5, "#fbbf24"],
                    [1, "#ef4444"],
                  ],
                  texttemplate: "%{z:.1f}",
                } as Data,
              ]}
              layout={{
                ...plotlyBase(),
                height: 340,
                title: { text: `Mean CO2 ${unit} — Euro class × fuel type` },
              }}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%", height: 340 }}
              useResizeHandler
            />
          </div>
        </div>
      )}
    </div>
  );
}
