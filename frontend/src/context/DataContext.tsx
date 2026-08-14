import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import type {
  ActiveFilters,
  EngineSettings,
  FileLogEntry,
  TripRow,
  UploadResponse,
} from "../types";
import { EMPTY_FILTERS } from "../types";

type DataSource = "upload" | "database" | null;

interface DataContextValue {
  allRows: TripRow[];
  rows: TripRow[]; // after active filters
  dataSource: DataSource;
  fileLog: FileLogEntry[];
  autoLog: Record<string, string>;
  loading: boolean;
  error: string | null;
  settings: EngineSettings;
  setSettings: (s: Partial<EngineSettings>) => void;
  filters: ActiveFilters;
  setFilter: <K extends keyof ActiveFilters>(key: K, value: ActiveFilters[K]) => void;
  clearFilters: () => void;
  uploadFiles: (files: File[]) => Promise<void>;
  loadFromDb: () => Promise<void>;
  hasData: boolean;
}

const DataContext = createContext<DataContextValue | null>(null);

const DEFAULT_SETTINGS: EngineSettings = {
  methodology: "Hybrid",
  pollutants: ["CO2", "NOx"],
  basis: "passenger",
  ambientC: 28,
};

export function DataProvider({ children }: { children: ReactNode }) {
  const [allRows, setAllRows] = useState<TripRow[]>([]);
  const [dataSource, setDataSource] = useState<DataSource>(null);
  const [fileLog, setFileLog] = useState<FileLogEntry[]>([]);
  const [autoLog, setAutoLog] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settingsState, setSettingsState] = useState<EngineSettings>(DEFAULT_SETTINGS);
  const [filters, setFilters] = useState<ActiveFilters>(EMPTY_FILTERS);

  const setSettings = useCallback((s: Partial<EngineSettings>) => {
    setSettingsState((prev) => ({ ...prev, ...s }));
  }, []);

  const setFilter = useCallback(<K extends keyof ActiveFilters>(key: K, value: ActiveFilters[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }, []);

  const clearFilters = useCallback(() => setFilters(EMPTY_FILTERS), []);

  const runUpload = useCallback(
    async (files: File[]) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.postFiles<UploadResponse>(
          "/data/upload",
          files.map((f) => ({ field: "files", file: f })),
          {
            method: settingsState.methodology,
            pollutants: settingsState.pollutants.join(","),
            ambient: settingsState.ambientC,
            basis: settingsState.basis,
          }
        );
        setAllRows(res.rows);
        setFileLog(res.file_log);
        setAutoLog(res.auto_log);
        setDataSource("upload");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed.");
      } finally {
        setLoading(false);
      }
    },
    [settingsState]
  );

  const loadFromDb = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.postForm<{ rows: TripRow[]; row_count: number }>("/data/load-db", {
        method: settingsState.methodology,
        pollutants: settingsState.pollutants.join(","),
        ambient: settingsState.ambientC,
        basis: settingsState.basis,
      });
      setAllRows(res.rows);
      setFileLog([]);
      setAutoLog({});
      setDataSource("database");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load from database.");
    } finally {
      setLoading(false);
    }
  }, [settingsState]);

  const rows = useMemo(() => {
    let d = allRows;
    if (filters.operator) d = d.filter((r) => r.Operator === filters.operator);
    if (filters.euro) d = d.filter((r) => r.Euro_Standard === filters.euro);
    if (filters.fuel) d = d.filter((r) => r.Fuel_Type === filters.fuel);
    if (filters.category) d = d.filter((r) => r.Bus_Category === filters.category);
    if (filters.month) d = d.filter((r) => r.Month === filters.month);
    if (filters.dateRange) {
      const [start, end] = filters.dateRange;
      d = d.filter((r) => r.Date && r.Date >= start && r.Date <= end);
    }
    return d;
  }, [allRows, filters]);

  const value: DataContextValue = {
    allRows,
    rows,
    dataSource,
    fileLog,
    autoLog,
    loading,
    error,
    settings: settingsState,
    setSettings,
    filters,
    setFilter,
    clearFilters,
    uploadFiles: runUpload,
    loadFromDb,
    hasData: allRows.length > 0,
  };

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useData() {
  const ctx = useContext(DataContext);
  if (!ctx) throw new Error("useData must be used inside DataProvider");
  return ctx;
}
