// Shared state every page needs: the bell's count, this week's tokens, the theme.
// Polled every 20 s, and refreshed right away after anything that changes it.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Status } from "./api";

type Ctx = { status: Status | null; online: boolean; refresh: () => void; theme: string; setTheme: (id: string, save?: boolean) => void };
const StatusContext = createContext<Ctx | null>(null);

/** Put a theme on the page now (and remember it for the next load, see index.html). */
export function applyTheme(id: string) {
  document.documentElement.dataset.theme = id;
  try { localStorage.setItem("theme", id); } catch { /* private mode: the backend still has it */ }
}

export function StatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [online, setOnline] = useState(true);
  const [theme, setThemeState] = useState(document.documentElement.dataset.theme || "cs");

  const refresh = useCallback(() => {
    api.status().then((s) => { setStatus(s); setOnline(true); }, () => setOnline(false));
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 20_000);
    return () => clearInterval(t);
  }, [refresh]);

  // The secretary's saved theme wins over the browser's memory (e.g. you changed it on another
  // device). This runs only when the *saved* theme arrives or changes, so a hover preview in the
  // theme picker isn't undone mid-hover.
  const savedTheme = status?.theme;
  useEffect(() => {
    if (savedTheme) { setThemeState(savedTheme); applyTheme(savedTheme); }
  }, [savedTheme]);

  const setTheme = useCallback((id: string, save = true) => {
    setThemeState(id);
    applyTheme(id);
    if (save) api.setTheme(id).then(refresh, () => {});
  }, [refresh]);

  return <StatusContext.Provider value={{ status, online, refresh, theme, setTheme }}>{children}</StatusContext.Provider>;
}

export function useStatus(): Ctx {
  const ctx = useContext(StatusContext);
  if (!ctx) throw new Error("useStatus outside StatusProvider");
  return ctx;
}
