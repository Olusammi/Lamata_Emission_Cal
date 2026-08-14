// Thin fetch wrapper: attaches the JWT access token, retries once after
// a silent refresh on 401, and throws ApiError with the backend's detail
// message so callers can show it directly.

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function setTokens(access: string | null, refresh: string | null) {
  accessToken = access;
  refreshToken = refresh;
  if (access && refresh) {
    sessionStorage.setItem("lamata.refresh", refresh);
  } else {
    sessionStorage.removeItem("lamata.refresh");
  }
}

export function loadPersistedRefreshToken() {
  refreshToken = sessionStorage.getItem("lamata.refresh");
  return refreshToken;
}

export function getAccessToken() {
  return accessToken;
}

async function doRefresh(): Promise<boolean> {
  if (!refreshToken) return false;
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return true;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  form?: Record<string, string | number | boolean>;
  files?: { field: string; file: File }[];
  auth?: boolean; // default true
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, form, files, auth = true } = opts;

  const doFetch = async (): Promise<Response> => {
    const headers: Record<string, string> = {};
    let payload: BodyInit | undefined;

    if (files) {
      const fd = new FormData();
      for (const f of files) fd.append(f.field, f.file);
      if (form) for (const [k, v] of Object.entries(form)) fd.append(k, String(v));
      payload = fd;
    } else if (form) {
      const fd = new URLSearchParams();
      for (const [k, v] of Object.entries(form)) fd.append(k, String(v));
      headers["Content-Type"] = "application/x-www-form-urlencoded";
      payload = fd;
    } else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }

    if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;

    return fetch(`${API_BASE}${path}`, { method, headers, body: payload });
  };

  let res = await doFetch();
  if (res.status === 401 && auth) {
    const refreshed = await doRefresh();
    if (refreshed) res = await doFetch();
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // non-JSON error body — keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, auth = true) => request<T>(path, { method: "GET", auth }),
  post: <T>(path: string, body?: unknown, auth = true) => request<T>(path, { method: "POST", body, auth }),
  postForm: <T>(path: string, form: Record<string, string | number | boolean>, auth = true) =>
    request<T>(path, { method: "POST", form, auth }),
  postFiles: <T>(path: string, files: { field: string; file: File }[], form?: Record<string, string | number | boolean>) =>
    request<T>(path, { method: "POST", files, form }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
