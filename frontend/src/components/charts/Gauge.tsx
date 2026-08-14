// Port of app.py's gauge_svg() — the semicircular compliance instrument
// used in Trip Inspector and Formula Explainer. Colors read live CSS
// custom properties so they follow the active theme/mode.
interface GaugeProps {
  value: number;
  good: number;
  monitor: number;
  unit?: string;
  maxVal?: number;
}

export function Gauge({ value, good, monitor, unit = "g CO₂/pkm", maxVal }: GaugeProps) {
  const flag = value <= good ? "Good" : value <= monitor ? "Monitor" : "Over Limit";
  const statusClass =
    flag === "Good" ? "bg-good-bg text-good" : flag === "Monitor" ? "bg-monitor-bg text-monitor" : "bg-over-bg text-over";

  const max = maxVal ?? Math.max(monitor * 1.6, value * 1.1, 1);
  const pct = Math.max(0, Math.min(value / max, 1));
  const angle = 180 * pct;
  const rad = ((180 - angle) * Math.PI) / 180;
  const cx = 110, cy = 110, r = 80;
  const nx = cx + r * Math.cos(rad) * 0.62;
  const ny = cy - r * Math.sin(rad) * 0.62;
  const goodFrac = Math.min(good / max, 1);
  const monFrac = Math.min(monitor / max, 1);

  const arcPath = (f0: number, f1: number) => {
    const a0 = 180 - 180 * f0;
    const a1 = 180 - 180 * f1;
    const r0 = (a0 * Math.PI) / 180;
    const r1 = (a1 * Math.PI) / 180;
    const x0 = cx + r * Math.cos(r0), y0 = cy - r * Math.sin(r0);
    const x1 = cx + r * Math.cos(r1), y1 = cy - r * Math.sin(r1);
    return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${r} ${r} 0 0 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
  };

  return (
    <div className="flex flex-col items-center text-center">
      <svg width={220} height={128} viewBox="0 0 220 128">
        <path d={arcPath(0, goodFrac)} fill="none" stroke="#3ddc84" strokeWidth={14} strokeLinecap="round" />
        <path d={arcPath(goodFrac, monFrac)} fill="none" stroke="#ff9d2e" strokeWidth={14} strokeLinecap="round" />
        <path d={arcPath(monFrac, 1)} fill="none" stroke="#ff5252" strokeWidth={14} strokeLinecap="round" />
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="var(--text-prim)" strokeWidth={3} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={6} fill="var(--text-prim)" />
      </svg>
      <div className="mt-1 font-mono text-2xl font-semibold text-text-prim">
        {value.toFixed(1)}
        <span className="ml-1 font-sans text-xs text-text-sec">{unit}</span>
      </div>
      <div className={`mt-2 inline-block rounded px-2.5 py-1 font-mono text-[10.5px] font-semibold tracking-wide ${statusClass}`}>
        {flag.toUpperCase()}
      </div>
    </div>
  );
}
