// Shape of one computed trip row, as returned by POST /data/upload and
// POST /data/load-db (backend/routers/data.py::_rows_out). Optional
// fields reflect that not every manifest carries every column.
export interface TripRow {
  Date?: string;
  Month?: string;
  Route_Name?: string;
  Bus_ID: string;
  Operator?: string;
  Bus_Category: string;
  Fuel_Type: string;
  Route_Distance_km?: number;
  Avg_Speed_kmh?: number;
  Ridership?: number;
  Revenue_Trip?: boolean;
  Euro_Standard?: string;
  Vehicle_Age_years?: number;
  AC_Status?: boolean | string;
  Num_Trips_Today?: number;
  Engine_Model?: string;
  Source_File?: string;
  Category_Unmapped?: boolean;
  Fuel_Unmapped?: boolean;
  Compliance?: "Good" | "Monitor" | "Over Limit" | "N/A";
  load_factor?: number;
  euro_nox_mult?: number;
  age_co2_mult?: number;
  ac_uplift_kg?: number;
  CO2_kg?: number; CO2_g_km?: number; CO2_g_pkm?: number;
  NOx_kg?: number; NOx_g_km?: number; NOx_g_pkm?: number;
  PM_kg?: number; PM_g_km?: number; PM_g_pkm?: number;
  id?: number; // present only for DB-loaded rows
  [key: string]: unknown;
}

export type Pollutant = "CO2" | "NOx" | "PM";
export type Methodology = "COPERT" | "Hybrid" | "IPCC";
export type Basis = "passenger" | "vehicle";

export interface EngineSettings {
  methodology: Methodology;
  pollutants: Pollutant[];
  basis: Basis;
  ambientC: number;
}

export interface FileLogEntry {
  name: string;
  rows: number;
  status: "ok" | "error";
  detail: string;
  cols?: string[];
}

export interface UploadResponse {
  rows: TripRow[];
  file_log: FileLogEntry[];
  auto_log: Record<string, string>;
  row_count: number;
}

export interface ActiveFilters {
  operator: string | null;
  euro: string | null;
  fuel: string | null;
  category: string | null;
  month: string | null;
  dateRange: [string, string] | null;
}

export const EMPTY_FILTERS: ActiveFilters = {
  operator: null, euro: null, fuel: null, category: null, month: null, dateRange: null,
};

export interface DbUpload {
  source_file: string;
  rows: number;
  first: string;
  last: string;
}
