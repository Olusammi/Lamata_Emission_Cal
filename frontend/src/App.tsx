import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import { AppShell } from "./components/layout/AppShell";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import FleetIntelligence from "./pages/FleetIntelligence";
import PollutantEngine from "./pages/PollutantEngine";
import BusEfficiency from "./pages/BusEfficiency";
import CorridorMap from "./pages/CorridorMap";
import FleetHealth from "./pages/FleetHealth";
import Forecast from "./pages/Forecast";
import DataQuality from "./pages/DataQuality";
import WhatIf from "./pages/WhatIf";
import TripInspector from "./pages/TripInspector";
import FormulaExplainer from "./pages/FormulaExplainer";
import DeepSearch from "./pages/DeepSearch";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) {
    return <div className="flex h-screen items-center justify-center text-text-tert">Loading…</div>;
  }
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/fleet-intelligence" element={<FleetIntelligence />} />
        <Route path="/pollutant-engine" element={<PollutantEngine />} />
        <Route path="/bus-efficiency" element={<BusEfficiency />} />
        <Route path="/corridor-map" element={<CorridorMap />} />
        <Route path="/fleet-health" element={<FleetHealth />} />
        <Route path="/forecast" element={<Forecast />} />
        <Route path="/data-quality" element={<DataQuality />} />
        <Route path="/what-if" element={<WhatIf />} />
        <Route path="/trip-inspector" element={<TripInspector />} />
        <Route path="/formula-explainer" element={<FormulaExplainer />} />
        <Route path="/deep-search" element={<DeepSearch />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
