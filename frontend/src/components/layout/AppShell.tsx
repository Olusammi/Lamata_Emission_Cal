import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { FilterBar } from "./FilterBar";
import { AiAssistant } from "../ai/AiAssistant";

const TITLES: Record<string, string> = {
  "/": "Fleet Dashboard",
  "/fleet-intelligence": "Fleet Intelligence",
  "/pollutant-engine": "Pollutant Engine",
  "/bus-efficiency": "Bus Efficiency",
  "/corridor-map": "Corridor Map",
  "/fleet-health": "Fleet Health",
  "/forecast": "Forecast",
  "/data-quality": "Data Quality",
  "/what-if": "What-If Simulator",
  "/trip-inspector": "Trip Inspector",
  "/formula-explainer": "Formula Explainer",
  "/deep-search": "Deep Search",
};

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const title = TITLES[location.pathname] ?? "Fleet Emissions Console";

  return (
    <div className="flex h-screen overflow-hidden bg-app">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title={title} onMenu={() => setMenuOpen(true)} />
        <main className="flex-1 overflow-y-auto p-4 lg:p-6">
          <FilterBar />
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.15 }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <AiAssistant />
    </div>
  );
}
