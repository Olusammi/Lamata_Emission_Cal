// Reads the current theme's CSS custom properties into literal values —
// Plotly's layout options need real color strings, not var(--x) refs.
export function plotlyBase() {
  const style = getComputedStyle(document.documentElement);
  const v = (name: string) => style.getPropertyValue(name).trim() || undefined;
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: v("--font-body") || "Inter, sans-serif", size: 12, color: v("--text-sec") || "#8fa49a" },
    margin: { l: 8, r: 8, t: 36, b: 8 },
    legend: { orientation: "h" as const, bgcolor: "rgba(0,0,0,0)" },
    xaxis: { gridcolor: v("--border") || "#233029", zerolinecolor: v("--border") || "#233029" },
    yaxis: { gridcolor: v("--border") || "#233029", zerolinecolor: v("--border") || "#233029" },
  };
}

export const PALETTE = ["#1E73BE", "#3ddc84", "#5cc8c8", "#ff5252", "#c9a8ff", "#ffd166", "#7fb8a8", "#8fa49a"];
