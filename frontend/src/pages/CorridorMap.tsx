import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import { DeckGL } from "@deck.gl/react";
import { PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { Loader2 } from "lucide-react";
import { useData } from "../context/DataContext";
import { useTheme } from "../theme/ThemeProvider";
import { EmptyState } from "../components/layout/EmptyState";
import { Banner, SectionLabel } from "../components/ui/banner";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { ChartSwitcher } from "../components/charts/ChartSwitcher";
import { effUnit } from "../lib/format";
import { api, ApiError } from "../lib/api";
import type { Pollutant } from "../types";

interface CorridorGeometry {
  path: [number, number][];
}

interface GeometryResponse {
  corridors: Record<string, CorridorGeometry>;
  center: { lat: number; lon: number };
  map_styles: { Dark: string; Light: string; Voyager: string };
}

interface CorridorAgg {
  Corridor: string;
  Total_kg: number;
  Eff: number;
  Trips: number;
  Buses: number;
  Pax: number;
}

interface AggregateResponse {
  corridors: CorridorAgg[];
}

type BaseMapName = "Dark" | "Light" | "Voyager";
type ColorBy = "total" | "eff";

interface ViewState {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
}

interface PathDatum {
  name: string;
  path: [number, number][];
  color: [number, number, number, number];
  width: number;
  total: string;
  eff: string;
  trips: number;
  buses: number;
  pax: number;
}

interface PointDatum {
  name: string;
  pos: [number, number];
}

function colorFor(value: number, vmax: number): [number, number, number, number] {
  const t = Math.max(0, Math.min(1, value / vmax));
  const from: [number, number, number] = [62, 242, 160];
  const to: [number, number, number] = [255, 99, 99];
  const r = Math.round(from[0] + (to[0] - from[0]) * t);
  const g = Math.round(from[1] + (to[1] - from[1]) * t);
  const b = Math.round(from[2] + (to[2] - from[2]) * t);
  return [r, g, b, 210];
}

export default function CorridorMap() {
  const { rows, hasData, settings } = useData();
  const { mode } = useTheme();

  const pollutantOptions = useMemo(() => {
    const avail = settings.pollutants.filter((p): p is Pollutant => p === "CO2" || p === "NOx" || p === "PM");
    return avail.length ? avail : (["CO2"] as Pollutant[]);
  }, [settings.pollutants]);

  const [pollutant, setPollutant] = useState<Pollutant>(pollutantOptions[0]);
  const [colorBy, setColorBy] = useState<ColorBy>("total");
  const [baseMap, setBaseMap] = useState<BaseMapName>(mode === "dark" ? "Dark" : "Light");

  useEffect(() => {
    if (!pollutantOptions.includes(pollutant)) setPollutant(pollutantOptions[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollutantOptions]);

  const [geometry, setGeometry] = useState<GeometryResponse | null>(null);
  const [geomError, setGeomError] = useState<string | null>(null);

  const [aggData, setAggData] = useState<AggregateResponse | null>(null);
  const [aggLoading, setAggLoading] = useState(false);
  const [aggError, setAggError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasData) return;
    let cancelled = false;
    api
      .get<GeometryResponse>("/corridors/geometry")
      .then((res) => {
        if (!cancelled) setGeometry(res);
      })
      .catch((e) => {
        if (!cancelled) setGeomError(e instanceof ApiError ? e.message : "Failed to load corridor geometry.");
      });
    return () => {
      cancelled = true;
    };
  }, [hasData]);

  useEffect(() => {
    if (!hasData) return;
    let cancelled = false;
    setAggLoading(true);
    setAggError(null);
    api
      .post<AggregateResponse>("/corridors/aggregate", { rows, pollutant })
      .then((res) => {
        if (!cancelled) setAggData(res);
      })
      .catch((e) => {
        if (!cancelled) setAggError(e instanceof ApiError ? e.message : "Failed to aggregate corridors.");
      })
      .finally(() => {
        if (!cancelled) setAggLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, pollutant, hasData]);

  const unit = effUnit(settings.basis);

  const tableData = useMemo(() => {
    if (!aggData) return [];
    return aggData.corridors.map((c) => ({
      Corridor: c.Corridor,
      [`${pollutant} kg`]: Math.round(c.Total_kg * 10) / 10,
      [unit]: Math.round(c.Eff * 10) / 10,
      Rows: c.Trips,
      Passengers: c.Pax,
    }));
  }, [aggData, pollutant, unit]);

  if (!hasData) {
    return (
      <EmptyState description="A WebGL corridor map coloured by emission intensity, with a per-corridor totals table below it, will appear here." />
    );
  }

  return (
    <div className="space-y-6">
      <Banner>
        Schematic transit corridors coloured by emission intensity. Routes are matched to corridors by name
        keywords for now — when per-route latitude/longitude columns are added to the manifest, this map will
        plot exact route geometry automatically.
      </Banner>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">Pollutant</label>
          <Select value={pollutant} onValueChange={(v) => setPollutant(v as Pollutant)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {pollutantOptions.map((p) => (
                <SelectItem key={p} value={p}>
                  {p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">Colour by</label>
          <Select value={colorBy} onValueChange={(v) => setColorBy(v as ColorBy)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="total">Total emissions (kg)</SelectItem>
              <SelectItem value="eff">{`Efficiency (${unit})`}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-wide text-text-tert">Base map</label>
          <Select value={baseMap} onValueChange={(v) => setBaseMap(v as BaseMapName)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="Dark">Dark</SelectItem>
              <SelectItem value="Light">Light</SelectItem>
              <SelectItem value="Voyager">Voyager</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {geomError && <div className="text-sm text-over">{geomError}</div>}
      {aggError && <div className="text-sm text-over">{aggError}</div>}

      <div className="relative h-[560px] w-full overflow-hidden rounded-md border border-border">
        {!geometry ? (
          <div className="flex h-full w-full items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-text-tert" />
          </div>
        ) : (
          <CorridorMapCanvas
            geometry={geometry}
            aggData={aggData}
            baseMap={baseMap}
            colorBy={colorBy}
            unit={unit}
          />
        )}
        {aggLoading && (
          <div className="pointer-events-none absolute right-3 top-3 flex items-center gap-1.5 rounded-md border border-border bg-card2/90 px-2 py-1 text-[11px] text-text-sec">
            <Loader2 className="h-3 w-3 animate-spin" />
            Updating corridors…
          </div>
        )}
      </div>

      <div>
        <SectionLabel>Corridor totals</SectionLabel>
        <ChartSwitcher
          data={tableData}
          x="Corridor"
          y={`${pollutant} kg`}
          kinds={["Bar", "Pie", "Table"]}
          defaultKind="Table"
          sortDesc
          height={320}
        />
      </div>

      <p className="text-xs text-text-tert">
        Corridor geometry is schematic. Add Route_Lat / Route_Lon columns to the manifest to unlock exact
        per-route plotting.
      </p>
    </div>
  );
}

function CorridorMapCanvas({
  geometry,
  aggData,
  baseMap,
  colorBy,
  unit,
}: {
  geometry: GeometryResponse;
  aggData: AggregateResponse | null;
  baseMap: BaseMapName;
  colorBy: ColorBy;
  unit: string;
}) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [viewState, setViewState] = useState<ViewState>({
    longitude: geometry.center.lon,
    latitude: geometry.center.lat,
    zoom: 10.4,
    pitch: 35,
    bearing: 0,
  });

  useEffect(() => {
    if (!mapContainerRef.current) return;
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: geometry.map_styles[baseMap],
      center: [geometry.center.lon, geometry.center.lat],
      zoom: 10.4,
      pitch: 35,
      attributionControl: false,
      interactive: false,
    });
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geometry, baseMap]);

  useEffect(() => {
    mapRef.current?.jumpTo({
      center: [viewState.longitude, viewState.latitude],
      zoom: viewState.zoom,
      bearing: viewState.bearing,
      pitch: viewState.pitch,
    });
  }, [viewState]);

  const pathData = useMemo<PathDatum[]>(() => {
    if (!aggData) return [];
    const values = aggData.corridors.map((c) => (colorBy === "total" ? c.Total_kg : c.Eff));
    const vmax = Math.max(1e-9, ...values);
    return aggData.corridors
      .filter((c) => geometry.corridors[c.Corridor])
      .map((c) => {
        const value = colorBy === "total" ? c.Total_kg : c.Eff;
        return {
          name: c.Corridor,
          path: geometry.corridors[c.Corridor].path,
          color: colorFor(value, vmax),
          width: 60 + 240 * Math.min(value / vmax, 1),
          total: `${c.Total_kg.toFixed(0)} kg`,
          eff: `${c.Eff.toFixed(1)} ${unit}`,
          trips: c.Trips,
          buses: c.Buses,
          pax: c.Pax,
        };
      });
  }, [aggData, geometry, colorBy, unit]);

  const pointData = useMemo<PointDatum[]>(
    () =>
      Object.entries(geometry.corridors).flatMap(([name, c]) =>
        [c.path[0], c.path[c.path.length - 1]].map((pos) => ({ name, pos }))
      ),
    [geometry]
  );

  const layers = useMemo(
    () => [
      new PathLayer<PathDatum>({
        id: "corridors",
        data: pathData,
        getPath: (d) => d.path,
        getColor: (d) => d.color,
        getWidth: (d) => d.width,
        widthMinPixels: 4,
        capRounded: true,
        jointRounded: true,
        pickable: true,
      }),
      new ScatterplotLayer<PointDatum>({
        id: "corridor-points",
        data: pointData,
        getPosition: (d) => d.pos,
        getRadius: 350,
        getFillColor: [238, 243, 240, 200],
        getLineColor: [30, 115, 190],
        lineWidthMinPixels: 2,
        stroked: true,
        pickable: false,
      }),
    ],
    [pathData, pointData]
  );

  return (
    <>
      <div ref={mapContainerRef} className="absolute inset-0" />
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: vs }) => setViewState(vs as ViewState)}
        controller
        layers={layers}
        style={{ position: "absolute", inset: "0" }}
        getTooltip={({ object }) => {
          const d = object as PathDatum | undefined;
          if (!d || !d.name) return null;
          return {
            html: `<b>${d.name}</b><br/>${d.total} · ${d.eff}<br/>${d.trips} trips · ${d.buses} buses · ${d.pax} pax`,
            style: {
              backgroundColor: "#151d1c",
              color: "#eef3f0",
              fontSize: "12px",
              borderRadius: "4px",
              padding: "6px 10px",
            },
          };
        }}
      />
    </>
  );
}
