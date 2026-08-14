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
import { aggBy } from "../lib/aggregate";
import { api, ApiError } from "../lib/api";
import { fmtNum } from "../lib/format";

type Target = "co2" | "ridership";

interface ForecastPoint {
  Date: string;
  forecast: number;
  lo: number;
  hi: number;
  actual: number | null;
  is_history: boolean;
}

interface ForecastResponse {
  ready: boolean;
  points: ForecastPoint[];
}

interface RiskRow {
  Bus_ID: string;
  Operator: string;
  Category: string;
  Euro: string;
  Age: number;
  Days: number;
  Breaches_so_far: number;
  Risk_score: number;
  Risk_band: "High" | "Elevated" | "Low";
}

interface RiskResponse {
  ready: boolean;
  rows: RiskRow[];
}

const RISK_COLORS: Record<string, string> = { High: "#FF6363", Elevated: "#FFC24B", Low: "#3EF2A0" };

export default function Forecast() {
  const { rows, hasData } = useData();
  const [target, setTarget] = useState<Target>("co2");
  const [horizon, setHorizon] = useState(30);

  const [fcLoading, setFcLoading] = useState(false);
  const [fcError, setFcError] = useState<string | null>(null);
  const [fcData, setFcData] = useState<ForecastResponse | null>(null);

  const [riskLoading, setRiskLoading] = useState(false);
  const [riskError, setRiskError] = useState<string | null>(null);
  const [riskData, setRiskData] = useState<RiskResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const dailyAgg = useMemo(() => {
    const field = target === "co2" ? "CO2_kg" : "Ridership";
    return aggBy(rows, "Date", field, "sum")
      .slice()
      .sort((a, b) => a.key.localeCompare(b.key))
      .map((d) => ({ Date: d.key, value: Math.round(d.value * 100) / 100 }));
  }, [rows, target]);

  useEffect(() => {
    if (!hasData) return;
    let cancelled = false;
    setFcLoading(true);
    setFcError(null);
    api
      .post<ForecastResponse>("/ml/forecast", { rows: dailyAgg, value_col: "value", horizon_days: horizon })
      .then((res) => {
        if (!cancelled) setFcData(res);
      })
      .catch((e) => {
        if (!cancelled) setFcError(e instanceof ApiError ? e.message : "Failed to compute forecast.");
      })
      .finally(() => {
        if (!cancelled) setFcLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dailyAgg, horizon, hasData]);

  useEffect(() => {
    if (!hasData) return;
    let cancelled = false;
    setRiskLoading(true);
    setRiskError(null);
    api
      .post<RiskResponse>("/ml/risk", { rows })
      .then((res) => {
        if (!cancelled) setRiskData(res);
      })
      .catch((e) => {
        if (!cancelled) setRiskError(e instanceof ApiError ? e.message : "Failed to score compliance risk.");
      })
      .finally(() => {
        if (!cancelled) setRiskLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, hasData]);

  const forecastStats = useMemo(() => {
    if (!fcData || !fcData.ready) return null;
    const sorted = [...fcData.points].sort((a, b) => a.Date.localeCompare(b.Date));
    const history = sorted.filter((p) => p.is_history);
    const future = sorted.filter((p) => !p.is_history);
    const next7 = future.slice(0, 7);
    const next7Avg = next7.length ? next7.reduce((s, p) => s + p.forecast, 0) / next7.length : 0;
    const projectedTotal = future.reduce((s, p) => s + p.forecast, 0);
    const lastHistory = history[history.length - 1]?.forecast ?? 0;
    const lastFuture = future[future.length - 1]?.forecast ?? 0;
    const trendPct = lastHistory ? (lastFuture / lastHistory - 1) * 100 : 0;
    return { sorted, history, future, next7Avg, projectedTotal, trendPct };
  }, [fcData]);

  const riskBandCounts = useMemo(() => {
    if (!riskData) return [];
    const counts: Record<string, number> = { High: 0, Elevated: 0, Low: 0 };
    for (const r of riskData.rows) counts[r.Risk_band] = (counts[r.Risk_band] ?? 0) + 1;
    return (["High", "Elevated", "Low"] as const).map((band) => ({ band, count: counts[band] ?? 0 }));
  }, [riskData]);

  const handleSaveRisk = async () => {
    if (!riskData) return;
    setSaveMsg(null);
    setSaving(true);
    try {
      const res = await api.post<{ saved: number; error: string | null }>("/ml/risk/save", { rows: riskData.rows });
      setSaveMsg(res.error ? res.error : `Saved ${res.saved} risk scores.`);
    } catch (e) {
      setSaveMsg(e instanceof ApiError ? e.message : "Failed to save risk scores.");
    } finally {
      setSaving(false);
    }
  };

  if (!hasData) {
    return (
      <EmptyState description="A trend + weekday forecast with an uncertainty band, and a compliance breach risk model, will appear here." />
    );
  }

  return (
    <div className="space-y-6">
      <Banner>
        Transparent forecasting: linear trend + weekday pattern, with a band showing how wrong the model has
        typically been on history. With a month or two of data this is honest short-range projection, not
        prophecy — the band says so. Below it, a gradient-boosted model scores each bus's compliance breach risk
        so enforcement can be proactive.
      </Banner>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">
            Forecast target
          </label>
          <Select value={target} onValueChange={(v) => setTarget(v as Target)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="co2">Fleet CO₂ (kg/day)</SelectItem>
              <SelectItem value="ridership">Ridership (pax/day)</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">
            {`Horizon (days) (${horizon})`}
          </label>
          <input
            type="range"
            min={7}
            max={60}
            value={horizon}
            onChange={(e) => setHorizon(Number(e.target.value))}
            className="h-9 w-full accent-accent"
          />
        </div>
      </div>

      {fcLoading && (
        <div className="flex items-center gap-2 text-sm text-text-sec">
          <Loader2 className="h-4 w-4 animate-spin" />
          Fitting trend + weekday model…
        </div>
      )}
      {fcError && <div className="text-sm text-over">{fcError}</div>}
      {!fcLoading && !fcError && fcData && !fcData.ready && (
        <Tip>Need at least 14 days of history for a forecast.</Tip>
      )}

      {!fcLoading && !fcError && fcData && fcData.ready && forecastStats && (
        <>
          <div className="rounded-md border border-border bg-card p-4">
            <Plot
              data={[
                {
                  type: "scatter",
                  mode: "lines",
                  name: "hi",
                  x: forecastStats.sorted.map((p) => p.Date),
                  y: forecastStats.sorted.map((p) => p.hi),
                  line: { width: 0 },
                  showlegend: false,
                  hoverinfo: "skip",
                },
                {
                  type: "scatter",
                  mode: "lines",
                  name: "95% band",
                  x: forecastStats.sorted.map((p) => p.Date),
                  y: forecastStats.sorted.map((p) => p.lo),
                  fill: "tonexty",
                  fillcolor: "rgba(30,115,190,0.15)",
                  line: { width: 0 },
                },
                {
                  type: "scatter",
                  mode: "lines+markers",
                  name: "Actual",
                  x: forecastStats.history.map((p) => p.Date),
                  y: forecastStats.history.map((p) => p.actual),
                  line: { color: "#1E73BE" },
                },
                {
                  type: "scatter",
                  mode: "lines",
                  name: "Forecast",
                  x: forecastStats.sorted.map((p) => p.Date),
                  y: forecastStats.sorted.map((p) => p.forecast),
                  line: { dash: "dash", color: "#3EF2A0" },
                },
              ]}
              layout={{ ...plotlyBase(), height: 380, title: { text: "Forecast with 95% confidence band" } }}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%", height: 380 }}
              useResizeHandler
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <KpiCard label="Next 7-day avg" value={fmtNum(forecastStats.next7Avg, 0)} />
            <KpiCard label={`Projected total (${horizon}d)`} value={fmtNum(forecastStats.projectedTotal, 0)} />
            <KpiCard
              label="Trend over horizon"
              value={`${forecastStats.trendPct >= 0 ? "+" : ""}${forecastStats.trendPct.toFixed(1)}%`}
            />
          </div>
        </>
      )}

      <div>
        <SectionLabel>Compliance breach risk</SectionLabel>

        {riskLoading && (
          <div className="flex items-center gap-2 text-sm text-text-sec">
            <Loader2 className="h-4 w-4 animate-spin" />
            Scoring compliance breach risk…
          </div>
        )}
        {riskError && <div className="text-sm text-over">{riskError}</div>}
        {!riskLoading && !riskError && riskData && !riskData.ready && (
          <Tip>Not enough Over-Limit examples in the current filter to train the risk model.</Tip>
        )}

        {!riskLoading && !riskError && riskData && riskData.ready && (
          <>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <div className="max-h-96 overflow-auto rounded-md border border-border">
                  <table className="w-full font-mono text-xs">
                    <thead className="sticky top-0 bg-card2">
                      <tr>
                        <th className="px-2 py-2 text-left text-text-tert">Bus ID</th>
                        <th className="px-2 py-2 text-left text-text-tert">Operator</th>
                        <th className="px-2 py-2 text-left text-text-tert">Category</th>
                        <th className="px-2 py-2 text-left text-text-tert">Euro</th>
                        <th className="px-2 py-2 text-right text-text-tert">Age</th>
                        <th className="px-2 py-2 text-right text-text-tert">Days</th>
                        <th className="px-2 py-2 text-right text-text-tert">Breaches</th>
                        <th className="px-2 py-2 text-left text-text-tert">Risk score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {riskData.rows.slice(0, 25).map((r) => (
                        <tr key={r.Bus_ID} className="border-t border-border/50">
                          <td className="px-2 py-1.5 text-text-prim">{r.Bus_ID}</td>
                          <td className="px-2 py-1.5 text-text-sec">{r.Operator}</td>
                          <td className="px-2 py-1.5 text-text-sec">{r.Category}</td>
                          <td className="px-2 py-1.5 text-text-sec">{r.Euro}</td>
                          <td className="px-2 py-1.5 text-right text-text-sec">{r.Age}</td>
                          <td className="px-2 py-1.5 text-right text-text-sec">{r.Days}</td>
                          <td className="px-2 py-1.5 text-right text-text-sec">{r.Breaches_so_far}</td>
                          <td className="px-2 py-1.5">
                            <div className="flex items-center gap-2">
                              <Progress value={Math.round(r.Risk_score * 100)} className="w-16" />
                              <span className="text-text-sec">{(r.Risk_score * 100).toFixed(0)}%</span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="rounded-md border border-border bg-card p-4">
                <Plot
                  data={[
                    {
                      type: "pie",
                      labels: riskBandCounts.map((b) => b.band),
                      values: riskBandCounts.map((b) => b.count),
                      hole: 0.5,
                      marker: { colors: riskBandCounts.map((b) => RISK_COLORS[b.band]) },
                      textinfo: "label+percent",
                    },
                  ]}
                  layout={{ ...plotlyBase(), height: 300, title: { text: "Risk band distribution" } }}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: "100%", height: 300 }}
                  useResizeHandler
                />
              </div>
            </div>

            <div className="mt-4">
              <Button variant="secondary" onClick={handleSaveRisk} disabled={saving}>
                <Save className="h-4 w-4" />
                {saving ? "Saving…" : "Save risk scores to database"}
              </Button>
              {saveMsg && <div className="mt-2 text-xs text-text-sec">{saveMsg}</div>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
