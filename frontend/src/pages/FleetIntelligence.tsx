import { useMemo } from "react";
import Plot from "../components/charts/PlotlyPlot";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { Banner, SectionLabel } from "../components/ui/banner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { aggBy, groupBy, isRevenue, mean, sum } from "../lib/aggregate";
import { plotlyBase, PALETTE } from "../components/charts/theme";
import { fmtKg } from "../lib/format";
import type { TripRow } from "../types";

export default function FleetIntelligence() {
  const { rows, hasData, settings } = useData();
  const co2On = settings.pollutants.includes("CO2");

  const byEngine = useMemo(() => {
    const rev = rows.filter(isRevenue);
    const g = groupBy(rev, (r) => r.Engine_Model || "—");
    return [...g.entries()]
      .map(([engine, bucket]) => ({
        engine,
        avgCo2: mean(bucket, "CO2_g_pkm"),
        totalCo2: sum(bucket, "CO2_kg"),
        trips: bucket.length,
        avgAge: mean(bucket, "Vehicle_Age_years"),
      }))
      .sort((a, b) => a.avgCo2 - b.avgCo2);
  }, [rows]);

  const byEuroCategory = useMemo(() => {
    const g = groupBy(rows, (r) => `${r.Euro_Standard}||${r.Bus_Category}`);
    return [...g.entries()].map(([key, bucket]) => {
      const [euro, category] = key.split("||");
      return { euro, category, co2: mean(bucket, "CO2_g_pkm"), trips: bucket.length };
    });
  }, [rows]);

  const euroNox = useMemo(() => aggBy(rows, "Euro_Standard", "NOx_g_pkm", "mean").sort((a, b) => b.value - a.value), [rows]);

  const ageByFuel = useMemo(() => {
    const rev = rows.filter(isRevenue);
    const g = groupBy(rev, (r) => `${r.Vehicle_Age_years}||${r.Fuel_Type}`);
    return [...g.entries()].map(([key, bucket]) => {
      const [age, fuel] = key.split("||");
      return { age: Number(age), fuel, co2: mean(bucket, "CO2_g_pkm"), trips: bucket.length };
    });
  }, [rows]);

  const ageDist = useMemo(() => {
    const seen = new Set<string>();
    const buses: TripRow[] = [];
    for (const r of rows) {
      if (r.Bus_ID && !seen.has(r.Bus_ID)) { seen.add(r.Bus_ID); buses.push(r); }
    }
    return buses.map((b) => Number(b.Vehicle_Age_years ?? 0));
  }, [rows]);

  const acStats = useMemo(() => {
    const on = rows.filter((r) => String(r.AC_Status).toLowerCase() === "true");
    const off = rows.filter((r) => String(r.AC_Status).toLowerCase() !== "true");
    const uplift = sum(rows, "ac_uplift_kg");
    const co2Total = sum(rows, "CO2_kg") || 0.001;
    return { on: on.length, off: off.length, uplift, upliftPct: (uplift / co2Total) * 100 };
  }, [rows]);

  const acByRoute = useMemo(() => {
    const g = groupBy(rows, (r) => `${r.Route_Name}||${String(r.AC_Status).toLowerCase() === "true" ? "A/C On" : "A/C Off"}`);
    return [...g.entries()].map(([key, bucket]) => {
      const [route, ac] = key.split("||");
      return { route, ac, co2: mean(bucket, "CO2_g_pkm") };
    });
  }, [rows]);

  if (!hasData) {
    return <EmptyState description="Engine-family league tables, Euro-class comparisons and operator breakdowns will appear here." />;
  }

  return (
    <div className="space-y-4">
      <Banner>
        Drill into individual buses and engine families. See how <strong>Euro standard</strong>, <strong>vehicle age</strong>,{" "}
        <strong>A/C status</strong>, and <strong>engine model</strong> compound to drive each vehicle's emission profile.
      </Banner>

      <Tabs defaultValue="engine">
        <TabsList>
          <TabsTrigger value="engine">By Engine Model</TabsTrigger>
          <TabsTrigger value="euro">By Euro Standard</TabsTrigger>
          <TabsTrigger value="age">By Vehicle Age</TabsTrigger>
          <TabsTrigger value="ac">A/C Impact</TabsTrigger>
        </TabsList>

        <TabsContent value="engine">
          <SectionLabel>CO₂ per engine family</SectionLabel>
          {co2On && byEngine.length > 0 && (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="rounded-md border border-border bg-card p-4 lg:col-span-2">
                <Plot
                  data={[{
                    type: "bar", x: byEngine.map((e) => e.engine), y: byEngine.map((e) => Math.round(e.avgCo2 * 10) / 10),
                    marker: { color: byEngine.map((e) => e.avgCo2), colorscale: [[0, "#22c55e"], [1, "#ef4444"]] },
                    text: byEngine.map((e) => `${e.avgCo2.toFixed(1)} g`), textposition: "outside",
                  }]}
                  layout={{ ...plotlyBase(), height: 340, title: { text: "Average CO₂ g/pkm by engine model" } }}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: "100%", height: 340 }}
                  useResizeHandler
                />
              </div>
              <div className="max-h-[340px] overflow-auto rounded-md border border-border">
                <table className="w-full font-mono text-xs">
                  <thead className="sticky top-0 bg-card2"><tr>
                    <th className="px-2 py-2 text-left text-text-tert">Engine</th>
                    <th className="px-2 py-2 text-right text-text-tert">g/pkm</th>
                    <th className="px-2 py-2 text-right text-text-tert">Total kg</th>
                  </tr></thead>
                  <tbody>
                    {byEngine.map((e) => (
                      <tr key={e.engine} className="border-t border-border/50">
                        <td className="px-2 py-1.5 text-text-sec">{e.engine}</td>
                        <td className="px-2 py-1.5 text-right text-text-prim">{e.avgCo2.toFixed(1)}</td>
                        <td className="px-2 py-1.5 text-right text-text-sec">{e.totalCo2.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="euro">
          <SectionLabel>Euro class emission comparison</SectionLabel>
          <div className="rounded-md border border-border bg-card p-4">
            <Plot
              data={[...new Set(byEuroCategory.map((r) => r.category))].map((cat, i) => {
                const bucket = byEuroCategory.filter((r) => r.category === cat);
                return {
                  type: "bar", name: cat, x: bucket.map((r) => r.euro), y: bucket.map((r) => Math.round(r.co2 * 10) / 10),
                  marker: { color: PALETTE[i % PALETTE.length] },
                };
              })}
              layout={{ ...plotlyBase(), height: 340, barmode: "group", title: { text: "Average CO₂ g/pkm by Euro class and bus category" } }}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%", height: 340 }}
              useResizeHandler
            />
          </div>
          {settings.pollutants.includes("NOx") && euroNox.length > 0 && (
            <div className="mt-4 rounded-md border border-border bg-card p-4">
              <Plot
                data={[{
                  type: "bar", x: euroNox.map((r) => r.key), y: euroNox.map((r) => Math.round(r.value * 100) / 100),
                  marker: { color: euroNox.map((r) => r.value), colorscale: [[0, "#22c55e"], [1, "#ef4444"]] },
                }]}
                layout={{ ...plotlyBase(), height: 320, title: { text: "Average NOx g/pkm by Euro class" } }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: "100%", height: 320 }}
                useResizeHandler
              />
            </div>
          )}
        </TabsContent>

        <TabsContent value="age">
          <SectionLabel>Age deterioration curve</SectionLabel>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded-md border border-border bg-card p-4">
              <Plot
                data={[...new Set(ageByFuel.map((r) => r.fuel))].map((fuel, i) => {
                  const bucket = ageByFuel.filter((r) => r.fuel === fuel);
                  return {
                    type: "scatter", mode: "markers", name: fuel,
                    x: bucket.map((r) => r.age), y: bucket.map((r) => Math.round(r.co2 * 10) / 10),
                    marker: { color: PALETTE[i % PALETTE.length], size: bucket.map((r) => Math.max(6, Math.min(24, r.trips))) },
                  };
                })}
                layout={{ ...plotlyBase(), height: 320, title: { text: "CO₂ intensity vs vehicle age by fuel type" } }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: "100%", height: 320 }}
                useResizeHandler
              />
            </div>
            <div className="rounded-md border border-border bg-card p-4">
              <Plot
                data={[{ type: "histogram", x: ageDist, marker: { color: "#1E73BE" } }]}
                layout={{ ...plotlyBase(), height: 320, title: { text: "Fleet age distribution" } }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: "100%", height: 320 }}
                useResizeHandler
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="ac">
          <SectionLabel>A/C impact on CO₂</SectionLabel>
          <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <MiniStat label="A/C ON trips" value={acStats.on.toLocaleString()} />
            <MiniStat label="A/C OFF trips" value={acStats.off.toLocaleString()} />
            <MiniStat label="Total A/C uplift" value={fmtKg(acStats.uplift)} />
            <MiniStat label="A/C % of CO₂" value={`${acStats.upliftPct.toFixed(1)}%`} />
          </div>
          <div className="rounded-md border border-border bg-card p-4">
            <Plot
              data={["A/C On", "A/C Off"].map((ac) => {
                const bucket = acByRoute.filter((r) => r.ac === ac);
                return {
                  type: "bar", name: ac, x: bucket.map((r) => r.route), y: bucket.map((r) => Math.round(r.co2 * 10) / 10),
                  marker: { color: ac === "A/C On" ? "#ef4444" : "#22c55e" },
                };
              })}
              layout={{ ...plotlyBase(), height: 340, barmode: "group", title: { text: "CO₂ g/pkm — A/C on vs off by route" } }}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%", height: 340 }}
              useResizeHandler
            />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-border bg-card px-3 py-2.5">
      <div className="font-mono text-[9.5px] uppercase tracking-wide text-text-tert">{label}</div>
      <div className="font-mono text-lg font-semibold text-text-prim">{value}</div>
    </div>
  );
}
