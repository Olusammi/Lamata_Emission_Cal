import { Bus } from "lucide-react";
import { useData } from "../../context/DataContext";

export function EmptyState({ description }: { description: string }) {
  const { error } = useData();
  return (
    <div className="flex min-h-[58vh] flex-col items-center justify-center gap-4 text-center">
      <Bus className="h-12 w-12 text-text-tert" />
      <h2 className="text-xl font-semibold text-text-prim">Awaiting route manifest</h2>
      <p className="max-w-md text-sm leading-relaxed text-text-sec">{description}</p>
      <p className="max-w-lg text-sm leading-relaxed text-text-sec">
        Upload one or more monthly manifests in the sidebar — CSV or Excel (.xlsx) — or load from the database.
        <br />
        <br />
        Required columns: <code className="rounded bg-card2 px-1.5 py-0.5 text-[11px] text-accent">Date Route_Name Bus_ID Operator Bus_Category Fuel_Type Route_Distance_km Avg_Speed_kmh Ridership Revenue_Trip</code>
      </p>
      {error && <p className="text-sm text-over">{error}</p>}
    </div>
  );
}
