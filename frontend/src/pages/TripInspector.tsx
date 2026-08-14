import { useEffect, useMemo, useState } from "react";
import Plot from "../components/charts/PlotlyPlot";
import { useData } from "../context/DataContext";
import { EmptyState } from "../components/layout/EmptyState";
import { KpiCard } from "../components/charts/KpiCard";
import { Gauge } from "../components/charts/Gauge";
import { plotlyBase } from "../components/charts/theme";
import { Banner, SectionLabel, Tip } from "../components/ui/banner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { api, ApiError } from "../lib/api";
import { isTrueish } from "../lib/format";
import type { TripRow } from "../types";

interface TripBreakdown {
  hot_running: number;
  cold_start: number;
  idling: number;
  ac_load: number;
  grid_electric: number;
  total_g: number;
}

const BAR_ITEMS: { key: keyof Omit<TripBreakdown, "total_g">; label: string; color: string }[] = [
  { key: "hot_running", label: "Hot running", color: "#1E73BE" },
  { key: "cold_start", label: "Cold start", color: "#ffb84d" },
  { key: "idling", label: "Idling", color: "#ff5252" },
  { key: "ac_load", label: "A/C load", color: "#3ddc84" },
  { key: "grid_electric", label: "Grid (EV)", color: "#c9a8ff" },
];

const CAPACITY_THRESHOLDS: Record<string, [number, number]> = {
  "High Capacity": [30, 55],
  Midi: [45, 75],
  Mini: [60, 95],
};

export default function TripInspector() {
  const { rows, hasData, settings } = useData();

  const busIds = useMemo(() => [...new Set(rows.map((r) => r.Bus_ID))].filter(Boolean).sort(), [rows]);
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

  const [breakdown, setBreakdown] = useState<TripBreakdown | null>(null);
  const [loadingBreakdown, setLoadingBreakdown] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedRow) {
      setBreakdown(null);
      return;
    }
    let cancelled = false;
    setLoadingBreakdown(true);
    setFetchError(null);
    api
      .post<TripBreakdown>("/calc/trip-breakdown", {
        row: selectedRow,
        methodology: settings.methodology,
        ambient_c: settings.ambientC,
      })
      .then((res) => {
        if (!cancelled) setBreakdown(res);
      })
      .catch((e) => {
        if (!cancelled) setFetchError(e instanceof ApiError ? e.message : "Could not load trip breakdown.");
      })
      .finally(() => {
        if (!cancelled) setLoadingBreakdown(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedRow, settings.methodology, settings.ambientC]);

  if (!hasData) {
    return (
      <EmptyState description="Select a single trip to see a full breakdown: hot running, cold start (scaled by Num_Trips_Today), idling, A/C load (only when AC_Status = True), and grid electricity for EVs." />
    );
  }

  const co2On = settings.pollutants.includes("CO2");
  const noxOn = settings.pollutants.includes("NOx");

  const pieItems = breakdown ? BAR_ITEMS.map((b) => ({ ...b, value: breakdown[b.key] })).filter((b) => b.value > 0) : [];

  const idleSave = breakdown ? (breakdown.idling * 0.5) / 1000 : 0;
  const acSave = breakdown ? (breakdown.ac_load * 0.3) / 1000 : 0;
  const tripSave = breakdown ? (breakdown.cold_start * 0.2) / 1000 : 0;
  const totalSave = idleSave + acSave + tripSave;

  return (
    <div className="space-y-6">
      <Banner>
        Select a single trip to see a full breakdown: hot running, cold start (scaled by <code>Num_Trips_Today</code>),
        idling, A/C load (only when <code>AC_Status</code> = True), and grid electricity for EVs.
      </Banner>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
                  {`${t.Date ?? "—"} · ${t.Route_Name ?? "—"} · ${t.Route_Distance_km ?? "—"} km · ${t.Ridership ?? "—"} pax`}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {fetchError && <p className="text-sm text-over">{fetchError}</p>}

      {!selectedRow && (
        <div className="flex h-32 items-center justify-center rounded-md border border-dashed border-border text-sm text-text-tert">
          Pick a bus and trip to see the breakdown.
        </div>
      )}

      {selectedRow && (
        <>
          <div>
            <SectionLabel>Vehicle metadata</SectionLabel>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
              <KpiCard label="Bus category" value={selectedRow.Bus_Category ?? "—"} />
              <KpiCard label="Fuel type" value={selectedRow.Fuel_Type ?? "—"} />
              <KpiCard label="Euro standard" value={selectedRow.Euro_Standard ?? "—"} />
              <KpiCard label="Vehicle age" value={`${selectedRow.Vehicle_Age_years ?? "—"} yr`} />
              <KpiCard label="Engine" value={selectedRow.Engine_Model ?? "—"} />
              <KpiCard label="A/C status" value={isTrueish(selectedRow.AC_Status) ? "On" : "Off"} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KpiCard label="Distance" value={`${selectedRow.Route_Distance_km ?? "—"} km`} />
            <KpiCard label="Avg speed" value={`${selectedRow.Avg_Speed_kmh ?? "—"} km/h`} />
            <KpiCard label="Ridership" value={selectedRow.Ridership?.toLocaleString() ?? "—"} />
            <KpiCard label="Trips today" value={selectedRow.Num_Trips_Today ?? "—"} />
          </div>

          <div>
            <SectionLabel>Emission source breakdown (CO₂)</SectionLabel>

            {loadingBreakdown && (
              <div className="flex h-40 items-center justify-center rounded-md border border-dashed border-border text-sm text-text-tert">
                Loading breakdown…
              </div>
            )}

            {breakdown && !loadingBreakdown && (
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-3 rounded-md border border-border bg-card p-4">
                  <div className="space-y-2.5">
                    {BAR_ITEMS.map((b) => {
                      const value = breakdown[b.key];
                      const pct = breakdown.total_g > 0 ? (value / breakdown.total_g) * 100 : 0;
                      return (
                        <div key={b.key} className="flex items-center gap-3">
                          <div className="w-[90px] shrink-0 text-[11px] text-text-sec">{b.label}</div>
                          <div className="relative h-4 flex-1 overflow-hidden rounded bg-card2">
                            <div className="h-full rounded" style={{ width: `${pct}%`, background: b.color }} />
                          </div>
                          <div className="w-16 shrink-0 text-right font-mono text-[11px] text-text-prim">
                            {(value / 1000).toFixed(3)} kg
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  <div className="rounded-md border border-border bg-card2 p-3 text-center">
                    <div className="font-mono text-[10px] uppercase tracking-wide text-text-tert">Total CO₂ this trip</div>
                    <div className="mt-1 font-mono text-2xl font-semibold text-text-prim">
                      {(breakdown.total_g / 1000).toFixed(3)} kg
                    </div>
                  </div>

                  {co2On && selectedRow.CO2_g_pkm != null && (
                    <Gauge
                      value={selectedRow.CO2_g_pkm}
                      good={(CAPACITY_THRESHOLDS[selectedRow.Bus_Category] ?? [40, 70])[0]}
                      monitor={(CAPACITY_THRESHOLDS[selectedRow.Bus_Category] ?? [40, 70])[1]}
                    />
                  )}
                </div>

                <div className="space-y-3">
                  <div className="rounded-md border border-border bg-card p-4">
                    {pieItems.length > 0 ? (
                      <Plot
                        data={[
                          {
                            type: "pie",
                            labels: pieItems.map((p) => p.label),
                            values: pieItems.map((p) => p.value),
                            hole: 0.5,
                            marker: { colors: pieItems.map((p) => p.color) },
                            textinfo: "percent",
                          },
                        ]}
                        layout={{ ...plotlyBase(), height: 280, title: { text: "Source split" } }}
                        config={{ displayModeBar: false, responsive: true }}
                        style={{ width: "100%", height: 280 }}
                        useResizeHandler
                      />
                    ) : (
                      <div className="flex h-40 items-center justify-center text-sm text-text-tert">No emission sources.</div>
                    )}
                  </div>

                  {selectedRow.age_co2_mult != null && (
                    <Tip>
                      Age deterioration adds <strong>+{((selectedRow.age_co2_mult - 1) * 100).toFixed(1)}%</strong> to base
                      CO₂ factors.
                    </Tip>
                  )}
                  {selectedRow.euro_nox_mult != null && noxOn && (
                    <Tip>
                      Euro {selectedRow.Euro_Standard} NOx multiplier: <strong>{selectedRow.euro_nox_mult.toFixed(2)}×</strong>{" "}
                      vs Euro III baseline.
                    </Tip>
                  )}
                  {isTrueish(selectedRow.AC_Status) && selectedRow.ac_uplift_kg != null && (
                    <Tip>
                      A/C ON adds <strong>{(selectedRow.ac_uplift_kg * 1000).toFixed(1)} g CO₂</strong> (+8% of hot running).
                    </Tip>
                  )}
                </div>
              </div>
            )}
          </div>

          {breakdown && !loadingBreakdown && (
            <div>
              <SectionLabel>Reduction potential</SectionLabel>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <KpiCard label="Cut idle 50%" value={`−${idleSave.toFixed(3)} kg`} deltaTone="good" />
                <KpiCard label="Pre-cool at depot" value={`−${acSave.toFixed(3)} kg`} deltaTone="good" />
                <KpiCard label="Reduce daily trips" value={`−${tripSave.toFixed(3)} kg`} deltaTone="good" />
                <KpiCard
                  label="Combined saving"
                  value={`−${totalSave.toFixed(3)} kg`}
                  sub={breakdown.total_g > 0 ? `${((totalSave / (breakdown.total_g / 1000)) * 100).toFixed(0)}% reduction` : undefined}
                  deltaTone="good"
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
