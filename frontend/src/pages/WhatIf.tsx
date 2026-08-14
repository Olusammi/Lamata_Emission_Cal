import { useState } from "react";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { KpiCard } from "../components/charts/KpiCard";
import { ChartSwitcher } from "../components/charts/ChartSwitcher";
import { Banner, SectionLabel } from "../components/ui/banner";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { api, ApiError } from "../lib/api";

type ConvertTo = "CNG" | "Electric";
type EuroTarget = "No change" | "Euro IV" | "Euro V" | "Euro VI";
type AcPolicy = "No change" | "All A/C off" | "All A/C on";

interface WhatIfResponse {
  baseline: Record<string, number>;
  scenario: Record<string, number>;
  rows_modified: number;
  rows_total: number;
}

export default function WhatIf() {
  const { rows, hasData, settings } = useData();

  const [convertN, setConvertN] = useState(0);
  const [convertTo, setConvertTo] = useState<ConvertTo>("CNG");
  const [euroTarget, setEuroTarget] = useState<EuroTarget>("No change");
  const [speedGain, setSpeedGain] = useState(0);
  const [acPolicy, setAcPolicy] = useState<AcPolicy>("No change");

  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<WhatIfResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runScenario = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await api.post<WhatIfResponse>("/calc/whatif", {
        rows,
        methodology: settings.methodology,
        pollutants: settings.pollutants,
        ambient_c: settings.ambientC,
        convert_n: convertN,
        convert_to: convertTo,
        euro_target: euroTarget,
        speed_gain: speedGain,
        ac_policy: acPolicy,
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not run scenario.");
    } finally {
      setRunning(false);
    }
  };

  if (!hasData) {
    return (
      <EmptyState description="Fleet planning, not just reporting: pick interventions and the scenario is recomputed through the real emissions engine." />
    );
  }

  const baselineCo2 = result?.baseline.CO2;
  const scenarioCo2 = result?.scenario.CO2;
  const deltaT = baselineCo2 != null && scenarioCo2 != null ? (scenarioCo2 - baselineCo2) / 1000 : null;
  const deltaPct = baselineCo2 && scenarioCo2 != null ? (scenarioCo2 / baselineCo2 - 1) * 100 : null;

  const chartData = result
    ? settings.pollutants
        .filter((p) => p in result.baseline)
        .map((p) => ({
          Pollutant: p === "CO2" ? "CO₂ (t)" : `${p} (kg)`,
          Baseline: p === "CO2" ? result.baseline[p] / 1000 : result.baseline[p],
          Scenario: p === "CO2" ? result.scenario[p] / 1000 : result.scenario[p],
        }))
    : [];

  return (
    <div className="space-y-6">
      <Banner>
        Fleet planning, not just reporting: pick interventions and the scenario is recomputed through the real emissions
        engine — same math, modified fleet. Baseline is the currently filtered data, so you can also scenario-test a
        single operator or corridor.
      </Banner>

      <div className="grid gap-6 sm:grid-cols-2">
        <div className="space-y-4 rounded-md border border-border bg-card p-4">
          <div>
            <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wide text-text-tert">
              Convert N worst CO₂ diesel buses… ({convertN})
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={convertN}
              onChange={(e) => setConvertN(Number(e.target.value))}
              className="w-full accent-accent"
            />
          </div>
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">Convert to</label>
            <Select value={convertTo} onValueChange={(v) => setConvertTo(v as ConvertTo)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="CNG">CNG</SelectItem>
                <SelectItem value="Electric">Electric</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">Euro standard target</label>
            <Select value={euroTarget} onValueChange={(v) => setEuroTarget(v as EuroTarget)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="No change">No change</SelectItem>
                <SelectItem value="Euro IV">Euro IV</SelectItem>
                <SelectItem value="Euro V">Euro V</SelectItem>
                <SelectItem value="Euro VI">Euro VI</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-4 rounded-md border border-border bg-card p-4">
          <div>
            <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-wide text-text-tert">
              Average speed improvement (km/h) ({speedGain})
            </label>
            <input
              type="range"
              min={0}
              max={15}
              value={speedGain}
              onChange={(e) => setSpeedGain(Number(e.target.value))}
              className="w-full accent-accent"
            />
          </div>
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">A/C policy</label>
            <Select value={acPolicy} onValueChange={(v) => setAcPolicy(v as AcPolicy)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="No change">No change</SelectItem>
                <SelectItem value="All A/C off">All A/C off</SelectItem>
                <SelectItem value="All A/C on">All A/C on</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button disabled={running} onClick={runScenario}>
          {running ? "Running scenario…" : "Run scenario"}
        </Button>
        {error && <p className="text-sm text-over">{error}</p>}
      </div>

      {result && (
        <>
          <div>
            <SectionLabel>Scenario result</SectionLabel>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <KpiCard label="Baseline CO₂" value={baselineCo2 != null ? `${(baselineCo2 / 1000).toFixed(1)} t` : "—"} />
              <KpiCard
                label="Scenario CO₂"
                value={scenarioCo2 != null ? `${(scenarioCo2 / 1000).toFixed(1)} t` : "—"}
                sub={
                  deltaT != null && deltaPct != null
                    ? `${deltaT >= 0 ? "+" : ""}${deltaT.toFixed(1)} t (${deltaPct >= 0 ? "+" : ""}${deltaPct.toFixed(1)}%)`
                    : undefined
                }
                deltaTone={deltaT != null ? (deltaT > 0 ? "bad" : "good") : "neutral"}
              />
              <KpiCard label="Rows modified" value={result.rows_modified.toLocaleString()} />
            </div>
          </div>

          <div className="rounded-md border border-border bg-card p-4">
            <ChartSwitcher
              data={chartData}
              x="Pollutant"
              y={["Baseline", "Scenario"]}
              kinds={["Bar", "Table"]}
              defaultKind="Bar"
              title="Baseline vs scenario"
              height={340}
            />
          </div>

          <p className="text-[11px] leading-relaxed text-text-tert">
            Scenario totals use the same methodology, basis and ambient temperature as the rest of the console. Electric
            conversions add Nigerian-grid Scope 2 CO₂ — they are cleaner, not free.
          </p>
        </>
      )}
    </div>
  );
}
