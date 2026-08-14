import { useEffect, useMemo, useState } from "react";
import Plot from "../components/charts/PlotlyPlot";
import { Loader2, Save } from "lucide-react";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { Banner, SectionLabel, Tip } from "../components/ui/banner";
import { KpiCard } from "../components/charts/KpiCard";
import { Progress } from "../components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Button } from "../components/ui/button";
import { plotlyBase } from "../components/charts/theme";
import { api, ApiError } from "../lib/api";
import { fmtNum } from "../lib/format";
import { cn } from "../lib/utils";

interface HealthRow {
  Bus_ID: string;
  Operator: string;
  Category: string;
  Fuel: string;
  Days: number;
  Anomalous_days: number;
  Avg_CO2_g_km: number;
  Worst_self_z: number;
  Avg_iso_score: number;
  Anomaly_rate: number;
  Health: "Insufficient data" | "Investigate" | "Watch" | "Healthy";
}

interface AnomRow {
  Bus_ID: string;
  Date: string;
  CO2_g_km: number;
  is_anomaly: boolean;
  self_z: number;
  iso_outlier: boolean;
  iso_score: number;
  [key: string]: unknown;
}

interface AnomaliesResponse {
  ready: boolean;
  rows: AnomRow[];
  summary: HealthRow[];
}

const HEALTH_CLASS: Record<string, string> = {
  Investigate: "bg-over-bg text-over",
  Watch: "bg-monitor-bg text-monitor",
  Healthy: "bg-good-bg text-good",
};

export default function FleetHealth() {
  const { rows, hasData } = useData();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AnomaliesResponse | null>(null);
  const [selectedBus, setSelectedBus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!hasData) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .post<AnomaliesResponse>("/ml/anomalies", { rows })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : "Failed to run anomaly detection.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, hasData]);

  const league = useMemo(() => {
    if (!data) return [];
    return data.summary
      .filter((r) => r.Health !== "Insufficient data")
      .slice()
      .sort((a, b) => b.Anomaly_rate - a.Anomaly_rate || b.Worst_self_z - a.Worst_self_z)
      .slice(0, 40);
  }, [data]);

  useEffect(() => {
    if (!league.length) {
      setSelectedBus(null);
      return;
    }
    setSelectedBus((prev) => (prev && league.some((r) => r.Bus_ID === prev) ? prev : league[0].Bus_ID));
  }, [league]);

  const busRows = useMemo(() => {
    if (!data || !selectedBus) return [];
    return data.rows
      .filter((r) => r.Bus_ID === selectedBus)
      .slice()
      .sort((a, b) => a.Date.localeCompare(b.Date));
  }, [data, selectedBus]);

  const kpis = useMemo(() => {
    if (!data) return null;
    const investigate = data.summary.filter((r) => r.Health === "Investigate").length;
    const watch = data.summary.filter((r) => r.Health === "Watch").length;
    const anomDays = data.rows.filter((r) => r.is_anomaly).length;
    return { total: data.summary.length, investigate, watch, anomDays, totalDays: data.rows.length };
  }, [data]);

  const handleSave = async () => {
    if (!data) return;
    setSaveMsg(null);
    setSaving(true);
    try {
      const res = await api.post<{ saved: number; error: string | null }>("/ml/anomalies/save", {
        summary: data.summary,
      });
      setSaveMsg(res.error ? res.error : `Saved ${res.saved} health scores.`);
    } catch (e) {
      setSaveMsg(e instanceof ApiError ? e.message : "Failed to save health scores.");
    } finally {
      setSaving(false);
    }
  };

  if (!hasData) {
    return (
      <EmptyState description="Anomaly-detection health scores per bus, and a drill-down chart of CO₂ drift over time, will appear here." />
    );
  }

  return (
    <div className="space-y-6">
      <Banner>
        Machine-learning anomaly detection. Two checks per bus-day: is this bus drifting from its own normal
        CO₂/km (z-score), and does it stand out from its peer group of same-category, same-fuel buses (Isolation
        Forest)? Persistent anomalies usually mean injectors, filters, brakes or tyres — worth a workshop visit
        before they become breakdowns.
      </Banner>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-text-sec">
          <Loader2 className="h-4 w-4 animate-spin" />
          Training anomaly models on the current (filtered) fleet…
        </div>
      )}

      {error && <div className="text-sm text-over">{error}</div>}

      {!loading && !error && data && !data.ready && (
        <Tip>Not enough data to train on — need at least ~50 rows with CO₂ enabled.</Tip>
      )}

      {!loading && !error && data && data.ready && kpis && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard label="Buses analysed" value={kpis.total} />
            <KpiCard
              label="Investigate"
              value={kpis.investigate}
              sub={kpis.investigate ? "priority list" : undefined}
              deltaTone={kpis.investigate > 0 ? "bad" : "neutral"}
            />
            <KpiCard label="Watch" value={kpis.watch} />
            <KpiCard label="Anomalous bus-days" value={`${kpis.anomDays}/${kpis.totalDays}`} />
          </div>

          <div>
            <SectionLabel>Bus health league — worst first</SectionLabel>
            <div className="max-h-96 overflow-auto rounded-md border border-border">
              <table className="w-full font-mono text-xs">
                <thead className="sticky top-0 bg-card2">
                  <tr>
                    <th className="px-2 py-2 text-left text-text-tert">Bus ID</th>
                    <th className="px-2 py-2 text-left text-text-tert">Operator</th>
                    <th className="px-2 py-2 text-left text-text-tert">Category</th>
                    <th className="px-2 py-2 text-left text-text-tert">Fuel</th>
                    <th className="px-2 py-2 text-right text-text-tert">Days</th>
                    <th className="px-2 py-2 text-left text-text-tert">Anomaly rate</th>
                    <th className="px-2 py-2 text-right text-text-tert">Avg CO2 g/km</th>
                    <th className="px-2 py-2 text-right text-text-tert">Worst z</th>
                    <th className="px-2 py-2 text-left text-text-tert">Health</th>
                  </tr>
                </thead>
                <tbody>
                  {league.map((r) => (
                    <tr key={r.Bus_ID} className="border-t border-border/50">
                      <td className="px-2 py-1.5 text-text-prim">{r.Bus_ID}</td>
                      <td className="px-2 py-1.5 text-text-sec">{r.Operator}</td>
                      <td className="px-2 py-1.5 text-text-sec">{r.Category}</td>
                      <td className="px-2 py-1.5 text-text-sec">{r.Fuel}</td>
                      <td className="px-2 py-1.5 text-right text-text-sec">{r.Days}</td>
                      <td className="px-2 py-1.5">
                        <div className="flex items-center gap-2">
                          <Progress value={Math.round(r.Anomaly_rate * 100)} className="w-16" />
                          <span className="text-text-sec">{(r.Anomaly_rate * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="px-2 py-1.5 text-right text-text-sec">{fmtNum(r.Avg_CO2_g_km, 0)}</td>
                      <td className="px-2 py-1.5 text-right text-text-sec">{r.Worst_self_z.toFixed(1)}</td>
                      <td className="px-2 py-1.5">
                        <span
                          className={cn(
                            "inline-block rounded px-2 py-0.5 font-mono text-[10.5px] font-semibold tracking-wide",
                            HEALTH_CLASS[r.Health] ?? "bg-card2 text-text-tert"
                          )}
                        >
                          {r.Health}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <SectionLabel>Inspect one bus</SectionLabel>
            <div className="max-w-xs">
              <Select value={selectedBus ?? undefined} onValueChange={setSelectedBus}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a bus" />
                </SelectTrigger>
                <SelectContent>
                  {league.map((r) => (
                    <SelectItem key={r.Bus_ID} value={r.Bus_ID}>
                      {r.Bus_ID}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedBus && busRows.length > 0 && (
              <div className="mt-3 rounded-md border border-border bg-card p-4">
                <Plot
                  data={[
                    {
                      type: "scatter",
                      mode: "lines+markers",
                      name: "CO2 g/km",
                      x: busRows.map((r) => r.Date),
                      y: busRows.map((r) => r.CO2_g_km),
                      line: { color: "#1E73BE" },
                    },
                    {
                      type: "scatter",
                      mode: "markers",
                      name: "Anomaly",
                      x: busRows.filter((r) => r.is_anomaly).map((r) => r.Date),
                      y: busRows.filter((r) => r.is_anomaly).map((r) => r.CO2_g_km),
                      marker: { symbol: "x", size: 11, color: "#FF6363" },
                    },
                  ]}
                  layout={{ ...plotlyBase(), height: 340, title: { text: `CO₂ g/km — ${selectedBus}` } }}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: "100%", height: 340 }}
                  useResizeHandler
                />
              </div>
            )}
          </div>

          <div>
            <Button variant="secondary" onClick={handleSave} disabled={saving}>
              <Save className="h-4 w-4" />
              {saving ? "Saving…" : "Save health scores to database"}
            </Button>
            {saveMsg && <div className="mt-2 text-xs text-text-sec">{saveMsg}</div>}
          </div>
        </>
      )}
    </div>
  );
}
