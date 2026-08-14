import { AnimatePresence, motion } from "framer-motion";
import { useData } from "../../context/DataContext";
import { Chip } from "../ui/badge";
import { Button } from "../ui/button";

const LABELS: Record<string, string> = {
  operator: "Operator", euro: "Euro", fuel: "Fuel", category: "Category", month: "Month",
};
const COLORS: Record<string, "blue" | "purple" | "green" | "amber"> = {
  operator: "blue", euro: "purple", fuel: "green", category: "amber",
};

export function FilterBar() {
  const { filters, setFilter, clearFilters } = useData();
  const active = (Object.keys(filters) as (keyof typeof filters)[]).filter(
    (k) => k !== "dateRange" && filters[k]
  );
  const hasDateRange = !!filters.dateRange;

  if (!active.length && !hasDateRange) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: "auto" }}
        exit={{ opacity: 0, height: 0 }}
        className="mb-3 flex flex-wrap items-center gap-2 rounded-md border border-filter-bdr bg-card2 px-3 py-2 text-[12px]"
      >
        <span className="font-medium text-text-sec">Active filters:</span>
        {active.map((k) => (
          <Chip key={k} color={COLORS[k] ?? "gray"} onRemove={() => setFilter(k, null)}>
            {LABELS[k]}: {String(filters[k])}
          </Chip>
        ))}
        {hasDateRange && filters.dateRange && (
          <Chip color="blue" onRemove={() => setFilter("dateRange", null)}>
            Date range: {filters.dateRange[0]} → {filters.dateRange[1]}
          </Chip>
        )}
        <Button variant="ghost" size="sm" className="ml-auto h-6 px-2 text-[11px]" onClick={clearFilters}>
          Clear all
        </Button>
      </motion.div>
    </AnimatePresence>
  );
}
