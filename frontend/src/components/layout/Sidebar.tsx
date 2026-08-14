import {
  Activity, Network, CloudFog, Bus, Map, HeartPulse, TrendingUp,
  ClipboardCheck, SlidersHorizontal, Search, Calculator, Table2,
  Upload, Database, RefreshCw, X,
} from "lucide-react";
import { useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { useData } from "../../context/DataContext";
import { useTheme } from "../../theme/ThemeProvider";
import { cn } from "../../lib/utils";
import { api } from "../../lib/api";
import { Switch } from "../ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { Button } from "../ui/button";

const NAV = [
  { to: "/", label: "Dashboard", icon: Activity },
  { to: "/fleet-intelligence", label: "Fleet Intelligence", icon: Network },
  { to: "/pollutant-engine", label: "Pollutant Engine", icon: CloudFog },
  { to: "/bus-efficiency", label: "Bus Efficiency", icon: Bus },
  { to: "/corridor-map", label: "Corridor Map", icon: Map },
  { to: "/fleet-health", label: "Fleet Health", icon: HeartPulse },
  { to: "/forecast", label: "Forecast", icon: TrendingUp },
  { to: "/data-quality", label: "Data Quality", icon: ClipboardCheck },
  { to: "/what-if", label: "What-If", icon: SlidersHorizontal },
  { to: "/trip-inspector", label: "Trip Inspector", icon: Search },
  { to: "/formula-explainer", label: "Formula Explainer", icon: Calculator },
  { to: "/deep-search", label: "Deep Search", icon: Table2 },
];

export function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { mode, toggleMode, preset, setPreset, presetNames, accentHex } = useTheme();
  const { uploadFiles, loadFromDb, loading, dataSource } = useData();
  const [dbState, setDbState] = useState<{ state: string; message: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const checkDb = async () => {
    try {
      const res = await api.get<{ state: string; message: string }>("/data/db-status", false);
      setDbState(res);
    } catch {
      setDbState({ state: "error", message: "Could not reach the backend." });
    }
  };

  const dotColor: Record<string, string> = {
    connected: "#3EF2A0", empty: "#FFC24B", unconfigured: "#5c7268", error: "#FF6363",
  };

  return (
    <>
      {open && <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={onClose} />}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-border bg-sidebar transition-transform lg:static lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-3">
            <div
              className="flex h-9 w-9 items-center justify-center rounded border-2 font-display text-xs font-bold"
              style={{ borderColor: accentHex, color: accentHex }}
            >
              FE
            </div>
            <div>
              <div className="font-display text-sm font-semibold text-text-prim">Fleet Emissions Console</div>
              <div className="font-mono text-[9px] tracking-wide text-text-tert">TRANSIT FLEET INTELLIGENCE</div>
            </div>
          </div>
          <button onClick={onClose} className="text-text-tert hover:text-text-prim lg:hidden" aria-label="Close menu">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex items-center justify-between px-4 py-3">
          <span className="font-mono text-[10.5px] text-text-sec">DARK MODE</span>
          <Switch checked={mode === "dark"} onCheckedChange={toggleMode} />
        </div>
        <div className="px-4 pb-3">
          <Select value={preset} onValueChange={setPreset}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {presetNames.map((p) => (
                <SelectItem key={p} value={p}>{p}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              onClick={onClose}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-md border-l-[3px] border-transparent px-3 py-2 text-[12.5px] text-text-sec transition-colors hover:bg-card2",
                  isActive && "border-l-accent bg-card2 font-medium text-accent"
                )
              }
            >
              <Icon className="h-[15px] w-[15px] shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="space-y-3 border-t border-border p-4">
          <div>
            <div className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wide text-text-tert">Data input</div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={(e) => {
                const files = e.target.files ? Array.from(e.target.files) : [];
                if (files.length) uploadFiles(files);
                e.target.value = "";
              }}
            />
            <Button
              variant="secondary"
              size="sm"
              className="w-full justify-start"
              disabled={loading}
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="h-3.5 w-3.5" />
              {loading ? "Processing…" : "Upload manifest(s)"}
            </Button>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between font-mono text-[10px] font-semibold uppercase tracking-wide text-text-tert">
              <span>Database</span>
              <button onClick={checkDb} className="text-text-tert hover:text-text-prim" aria-label="Check database status">
                <RefreshCw className="h-3 w-3" />
              </button>
            </div>
            {dbState && (
              <div className="mb-2 flex items-center gap-1.5 text-[11px] text-text-sec">
                <span style={{ color: dotColor[dbState.state] }}>●</span>
                {dbState.message}
              </div>
            )}
            <Button
              variant="secondary"
              size="sm"
              className="w-full justify-start"
              disabled={loading}
              onClick={loadFromDb}
            >
              <Database className="h-3.5 w-3.5" />
              Load from database
            </Button>
          </div>

          {dataSource && (
            <div className="font-mono text-[10px] text-text-tert">Source: {dataSource === "upload" ? "upload" : "Supabase"}</div>
          )}

          <CalculationSettings />

          <div className="font-mono text-[10px] leading-relaxed text-text-tert/70">
            Factors: IPCC 2006 Tier 2 · COPERT V
            <br />
            Euro II–VI NOx/PM multipliers · Age deterioration
            <br />
            A/C per-trip flag · Engine model correction
            <br />
            Nigeria grid: 0.46 kg CO₂e/kWh (IEA 2023)
          </div>
        </div>
      </aside>
    </>
  );
}

function CalculationSettings() {
  const { settings, setSettings } = useData();
  const togglePollutant = (p: "CO2" | "NOx" | "PM") => {
    const has = settings.pollutants.includes(p);
    setSettings({ pollutants: has ? settings.pollutants.filter((x) => x !== p) : [...settings.pollutants, p] });
  };

  return (
    <div>
      <div className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wide text-text-tert">Calculation</div>
      <div className="space-y-2">
        <div>
          <label className="mb-1 block font-mono text-[10px] text-text-tert">Method</label>
          <Select value={settings.methodology} onValueChange={(v) => setSettings({ methodology: v as typeof settings.methodology })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="COPERT">COPERT</SelectItem>
              <SelectItem value="Hybrid">Hybrid</SelectItem>
              <SelectItem value="IPCC">IPCC</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block font-mono text-[10px] text-text-tert">Pollutants</label>
          <div className="flex gap-3">
            {(["CO2", "NOx", "PM"] as const).map((p) => (
              <label key={p} className="flex items-center gap-1.5 text-[11px] text-text-sec">
                <input
                  type="checkbox"
                  checked={settings.pollutants.includes(p)}
                  onChange={() => togglePollutant(p)}
                  className="h-3.5 w-3.5 accent-accent"
                />
                {p}
              </label>
            ))}
          </div>
        </div>
        <div>
          <label className="mb-1 block font-mono text-[10px] text-text-tert">Emission basis</label>
          <Select value={settings.basis} onValueChange={(v) => setSettings({ basis: v as typeof settings.basis })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="passenger">Per passenger</SelectItem>
              <SelectItem value="vehicle">Per vehicle</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 flex justify-between font-mono text-[10px] text-text-tert">
            <span>Ambient temp</span><span>{settings.ambientC}°C</span>
          </label>
          <input
            type="range"
            min={15}
            max={40}
            value={settings.ambientC}
            onChange={(e) => setSettings({ ambientC: Number(e.target.value) })}
            className="w-full accent-accent"
          />
        </div>
      </div>
    </div>
  );
}
