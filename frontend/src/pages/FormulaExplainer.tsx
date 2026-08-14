import { useEffect, useMemo, useState } from "react";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { Gauge } from "../components/charts/Gauge";
import { Banner, SectionLabel, Tip } from "../components/ui/banner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { api, ApiError } from "../lib/api";
import type { TripRow } from "../types";

interface FormulaStep {
  title: string;
  formula: string | null;
  substitution: string | null;
  result: string | null;
  note: string | null;
}

interface FormulaStepsResponse {
  fuel: string;
  steps: FormulaStep[];
  total_kg: number;
  gauge: { value: number; good: number; monitor: number } | null;
  capacity: number;
}

const ANY = "__any__";

export default function FormulaExplainer() {
  const { rows, hasData, settings } = useData();

  const operators = useMemo(() => [...new Set(rows.map((r) => r.Operator).filter(Boolean))].sort() as string[], [rows]);
  const [operator, setOperator] = useState<string>(ANY);

  const busIds = useMemo(() => {
    const d = operator === ANY ? rows : rows.filter((r) => r.Operator === operator);
    return [...new Set(d.map((r) => r.Bus_ID))].filter(Boolean).sort();
  }, [rows, operator]);
  const [busId, setBusId] = useState<string | null>(null);

  useEffect(() => {
    if (busIds.length && (!busId || !busIds.includes(busId))) setBusId(busIds[0]);
    if (!busIds.length) setBusId(null);
  }, [busIds, busId]);

  const trips = useMemo(() => (busId ? rows.filter((r) => r.Bus_ID === busId) : []), [rows, busId]);
  const [tripIdx, setTripIdx] = useState<number | null>(null);

  useEffect(() => {
    setTripIdx(trips.length ? 0 : null);
  }, [busId, trips.length]);

  const selectedRow: TripRow | null = tripIdx != null ? trips[tripIdx] ?? null : null;

  const [data, setData] = useState<FormulaStepsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedRow) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setFetchError(null);
    api
      .post<FormulaStepsResponse>("/calc/formula-steps", {
        row: selectedRow,
        methodology: settings.methodology,
        ambient_c: settings.ambientC,
      })
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (!cancelled) setFetchError(e instanceof ApiError ? e.message : "Could not load formula steps.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRow, settings.methodology, settings.ambientC]);

  if (!hasData) {
    return (
      <EmptyState description="Pick a trip to walk through every multiplier and addend the emissions engine applies to it, with your data's actual numbers substituted in." />
    );
  }

  return (
    <div className="space-y-6">
      <Banner>
        Pick any trip below and this walks through every multiplier and addend the <strong>{settings.methodology}</strong>{" "}
        engine applies to it, in order, with your data's actual numbers substituted in — so the final kg CO₂ figure isn't a
        black box.
      </Banner>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">Operator</label>
          <Select value={operator} onValueChange={(v) => setOperator(v)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any</SelectItem>
              {operators.map((o) => (
                <SelectItem key={o} value={o}>
                  {o}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">Bus ID</label>
          <Select value={busId ?? ""} onValueChange={(v) => setBusId(v)}>
            <SelectTrigger>
              <SelectValue placeholder="Select bus" />
            </SelectTrigger>
            <SelectContent>
              {busIds.map((b) => (
                <SelectItem key={b} value={b}>
                  {b}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">Trip</label>
          <Select value={tripIdx != null ? String(tripIdx) : ""} onValueChange={(v) => setTripIdx(Number(v))}>
            <SelectTrigger>
              <SelectValue placeholder="Select trip" />
            </SelectTrigger>
            <SelectContent>
              {trips.map((t, i) => (
                <SelectItem key={i} value={String(i)}>
                  {`${t.Date ?? "—"} · ${String(t.Route_Name ?? "—").slice(0, 28)}`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {fetchError && <p className="text-sm text-over">{fetchError}</p>}

      {!selectedRow && (
        <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-sm text-text-tert">
          Pick an operator, bus and trip to see the formula walkthrough.
        </div>
      )}

      {loading && (
        <div className="flex h-40 items-center justify-center rounded-md border border-dashed border-border text-sm text-text-tert">
          Loading formula steps…
        </div>
      )}

      {data && !loading && (
        <div className="space-y-4">
          {data.steps.map((step, i) => (
            <div key={i} className="rounded-md border border-border bg-card p-4">
              <SectionLabel>{step.title}</SectionLabel>
              {step.formula && (
                <div className="rounded bg-card2 px-3 py-2 font-mono text-xs text-text-sec">{step.formula}</div>
              )}
              {step.substitution && (
                <div className="mt-1.5 rounded bg-card2 px-3 py-2 font-mono text-xs text-text-tert">{step.substitution}</div>
              )}
              {step.result && <div className="mt-1 font-mono text-lg font-semibold text-text-prim">{step.result}</div>}
              {step.note && <div className="mt-2"><Tip>{step.note}</Tip></div>}
            </div>
          ))}

          {data.gauge && (
            <div className="flex justify-center rounded-md border border-border bg-card p-4">
              <Gauge value={data.gauge.value} good={data.gauge.good} monitor={data.gauge.monitor} />
            </div>
          )}

          <details className="rounded-md border border-border bg-card p-4">
            <summary className="cursor-pointer font-mono text-xs uppercase tracking-wide text-text-tert">
              Where every constant comes from
            </summary>
            <div className="mt-3 space-y-2 text-sm text-text-sec">
              <ul className="list-disc space-y-1.5 pl-5">
                <li>
                  <strong>Base factors</strong> — IPCC 2006 Tier 2 + COPERT V West-Africa fleet calibration, Euro III
                  reference.
                </li>
                <li>
                  <strong>Euro class multipliers (NOx/PM only)</strong> — EEA COPERT V Technical Report No 12, Table 4.1.
                  CO₂ is not adjusted by Euro class — after-treatment changes pollutant chemistry, not carbon output.
                </li>
                <li>
                  <strong>Age deterioration</strong> — COPERT degradation model: +0.4%/yr CO₂, +1.5%/yr NOx
                  (diesel/petrol), +2.0%/yr PM.
                </li>
                <li>
                  <strong>Cold start</strong> — EMEP/EEA Guidebook Table 3-27, applied to the first 5km of each trip,
                  scaled by trips/day.
                </li>
                <li>
                  <strong>A/C uplift</strong> — CARB 2021, 8% CO₂ uplift for heavy-duty buses in warm climates, applied
                  per-trip only when AC_Status is true for that row.
                </li>
                <li>
                  <strong>Electric grid factor</strong> — IEA 2023 regional estimate for Nigeria: 0.46 kg CO₂e/kWh.
                </li>
                <li>
                  <strong>Speed-correction curves (COPERT/Hybrid NOx &amp; PM)</strong> — fitted functions approximating
                  COPERT V speed bands.
                </li>
              </ul>
            </div>
          </details>
        </div>
      )}
    </div>
  );
}
