import { useMemo, useState } from "react";
import Plot from "./PlotlyPlot";
import type { Data, Layout } from "plotly.js";
import { BarChart3, LineChart, AreaChart, PieChart, Table2 } from "lucide-react";
import { cn } from "../../lib/utils";
import { PALETTE, plotlyBase } from "./theme";

export type ChartKind = "Bar" | "Line" | "Area" | "Pie" | "Table";

const ICONS: Record<ChartKind, React.ComponentType<{ className?: string }>> = {
  Bar: BarChart3, Line: LineChart, Area: AreaChart, Pie: PieChart, Table: Table2,
};

interface ChartSwitcherProps {
  data: Record<string, unknown>[];
  x: string;
  y: string | string[];
  kinds?: ChartKind[];
  defaultKind?: ChartKind;
  color?: string; // field to split into series
  title?: string;
  yLabel?: string;
  height?: number;
  sortDesc?: boolean;
  barmode?: "group" | "stack";
}

export function ChartSwitcher({
  data,
  x,
  y,
  kinds = ["Bar", "Line", "Area", "Pie", "Table"],
  defaultKind,
  color,
  title,
  yLabel,
  height = 340,
  sortDesc = false,
  barmode = "group",
}: ChartSwitcherProps) {
  const yCols = Array.isArray(y) ? y : [y];
  const availableKinds = kinds.filter((k) => !(k === "Pie" && (yCols.length > 1 || color)));
  const [kind, setKind] = useState<ChartKind>(defaultKind && availableKinds.includes(defaultKind) ? defaultKind : availableKinds[0]);

  const sorted = useMemo(() => {
    if (!sortDesc || kind === "Line" || kind === "Area") return data;
    return [...data].sort((a, b) => Number(b[yCols[0]] ?? 0) - Number(a[yCols[0]] ?? 0));
  }, [data, sortDesc, kind, yCols]);

  if (!data.length) {
    return (
      <div className="flex h-40 items-center justify-center rounded-md border border-dashed border-border text-sm text-text-tert">
        No data for the current filters.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        {title && <div className="font-mono text-[11px] font-medium uppercase tracking-wide text-text-tert">{title}</div>}
        <div className="ml-auto flex gap-1 rounded-md border border-border bg-card2 p-0.5">
          {availableKinds.map((k) => {
            const Icon = ICONS[k];
            return (
              <button
                key={k}
                type="button"
                onClick={() => setKind(k)}
                aria-label={k}
                aria-pressed={kind === k}
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded transition-colors",
                  kind === k ? "bg-accent text-white" : "text-text-tert hover:text-text-sec"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
              </button>
            );
          })}
        </div>
      </div>
      {kind === "Table" ? (
        <ChartTable data={sorted} x={x} y={yCols} />
      ) : (
        <ChartPlot kind={kind} data={sorted} x={x} y={yCols} color={color} height={height} yLabel={yLabel} barmode={barmode} />
      )}
    </div>
  );
}

function ChartTable({ data, x, y }: { data: Record<string, unknown>[]; x: string; y: string[] }) {
  const cols = [x, ...y];
  return (
    <div className="max-h-80 overflow-auto rounded-md border border-border">
      <table className="w-full font-mono text-xs">
        <thead className="sticky top-0 bg-card2">
          <tr>
            {cols.map((c) => (
              <th key={c} className="border-b border-border px-3 py-2 text-left text-text-tert">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-b border-border/50 last:border-0">
              {cols.map((c) => (
                <td key={c} className="px-3 py-1.5 text-text-sec">{String(row[c] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChartPlot({
  kind, data, x, y, color, height, yLabel, barmode,
}: {
  kind: ChartKind; data: Record<string, unknown>[]; x: string; y: string[]; color?: string;
  height: number; yLabel?: string; barmode: "group" | "stack";
}) {
  const base = plotlyBase();
  const layout: Partial<Layout> = {
    ...base,
    height,
    barmode,
    yaxis: { ...base.yaxis, title: { text: yLabel || "" } },
    showlegend: y.length > 1 || !!color,
  } as Partial<Layout>;

  let traces: Data[];
  if (kind === "Pie") {
    traces = [{
      type: "pie",
      labels: data.map((r) => String(r[x])),
      values: data.map((r) => Number(r[y[0]] ?? 0)),
      hole: 0.45,
      marker: { colors: PALETTE },
      textinfo: "percent",
    }];
  } else if (color) {
    const groups = [...new Set(data.map((r) => String(r[color])))];
    traces = groups.map((g, i) => {
      const rows = data.filter((r) => String(r[color]) === g);
      return {
        type: kind === "Line" || kind === "Area" ? "scatter" : "bar",
        mode: kind === "Line" || kind === "Area" ? "lines+markers" : undefined,
        fill: kind === "Area" ? "tozeroy" : undefined,
        name: g,
        x: rows.map((r) => r[x]),
        y: rows.map((r) => r[y[0]]),
        marker: { color: PALETTE[i % PALETTE.length] },
      } as Data;
    });
  } else {
    traces = y.map((col, i) => ({
      type: kind === "Line" || kind === "Area" ? "scatter" : "bar",
      mode: kind === "Line" || kind === "Area" ? "lines+markers" : undefined,
      fill: kind === "Area" ? "tozeroy" : undefined,
      name: col,
      x: data.map((r) => r[x]),
      y: data.map((r) => r[col]),
      marker: { color: PALETTE[i % PALETTE.length] },
    } as Data));
  }

  return (
    <Plot
      data={traces}
      layout={layout}
      config={{ displayModeBar: false, responsive: true }}
      style={{ width: "100%", height }}
      useResizeHandler
    />
  );
}
