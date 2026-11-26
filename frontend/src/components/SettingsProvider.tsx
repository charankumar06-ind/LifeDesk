import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import type { Settings } from "../lib/types";

const fallback: Settings = {
  display_name: "",
  role: "",
  workspace: "Personal desk",
  time_format: "24h",
  week_start: "monday",
  day_start: "08:30",
  day_end: "19:00",
  focus_block_minutes: 90,
  default_study_minutes: 120,
  buffer_minutes: 10,
  min_block_minutes: 30,
};

const SettingsContext = createContext<{ settings: Settings; refresh: () => void }>({
  settings: fallback,
  refresh: () => undefined,
});

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(fallback);

  const refresh = useCallback(() => {
    api
      .settings()
      .then((value) => setSettings({ ...fallback, ...value }))
      .catch(() => {
        /* layout still works with defaults; pages surface their own errors */
      });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const value = useMemo(() => ({ settings, refresh }), [settings, refresh]);
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings() {
  return useContext(SettingsContext);
}
