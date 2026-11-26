import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "../lib/api";
import type { AuthStatus, AuthUser } from "../lib/types";

interface AuthContextValue {
  status: AuthStatus | null;
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  setup: (displayName: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  status: null,
  user: null,
  loading: true,
  error: null,
  login: async () => undefined,
  setup: async () => undefined,
  logout: async () => undefined,
  refresh: async () => undefined,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const next = await api.authStatus();
      setStatus(next);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The authentication service is unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onUnauthorized = () => {
      setStatus((current) =>
        current ? { ...current, authenticated: false, user: null } : current,
      );
    };
    window.addEventListener("lifedesk:unauthorized", onUnauthorized);
    return () => window.removeEventListener("lifedesk:unauthorized", onUnauthorized);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const next = await api.login(username, password);
    setStatus(next);
    setError(null);
  }, []);

  const setup = useCallback(
    async (displayName: string, username: string, password: string) => {
      const next = await api.setup(displayName, username, password);
      setStatus(next);
      setError(null);
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setStatus((current) =>
        current ? { ...current, authenticated: false, user: null } : current,
      );
    }
  }, []);

  const value = useMemo(
    () => ({
      status,
      user: status?.user ?? null,
      loading,
      error,
      login,
      setup,
      logout,
      refresh,
    }),
    [status, loading, error, login, setup, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
