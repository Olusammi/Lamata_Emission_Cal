import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, api, loadPersistedRefreshToken, setTokens } from "../lib/api";

interface TokenPair {
  access_token: string;
  refresh_token: string;
}
interface Me {
  username: string;
  role: "admin" | "viewer";
}

interface AuthContextValue {
  user: Me | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMe = useCallback(async () => {
    try {
      const me = await api.get<Me>("/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    // Try to resume a session from the persisted refresh token (sessionStorage
    // survives a page reload but not a closed tab/browser — a middle ground
    // between "log in every request" and a long-lived localStorage token).
    (async () => {
      const refresh = loadPersistedRefreshToken();
      if (refresh) {
        try {
          const pair = await api.post<TokenPair>("/auth/refresh", { refresh_token: refresh }, false);
          setTokens(pair.access_token, pair.refresh_token);
          await fetchMe();
        } catch {
          setTokens(null, null);
        }
      }
      setLoading(false);
    })();
  }, [fetchMe]);

  const login = useCallback(
    async (username: string, password: string) => {
      setError(null);
      try {
        const pair = await api.post<TokenPair>("/auth/login", { username, password }, false);
        setTokens(pair.access_token, pair.refresh_token);
        await fetchMe();
        return true;
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Login failed.");
        return false;
      }
    },
    [fetchMe]
  );

  const logout = useCallback(() => {
    setTokens(null, null);
    setUser(null);
    api.post("/auth/logout").catch(() => {});
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
