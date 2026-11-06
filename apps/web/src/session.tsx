import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { bindAuthLost, readMe, type AuthUser } from "./api";

type SessionValue = {
  user: AuthUser | null;
  ready: boolean;
  offline: boolean;
  setUser: (user: AuthUser | null) => void;
};

const SessionContext = createContext<SessionValue | null>(null);

const RETRY_MS = 2000;

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const [offline, setOffline] = useState(false);

  const load = useCallback((onFail: () => void) => {
    readMe()
      .then((me) => {
        setUser(me);
        setOffline(false);
        setReady(true);
      })
      .catch(() => {
        setOffline(true);
        onFail();
      });
  }, []);

  useEffect(() => {
    let timer: number | undefined;
    let alive = true;
    const attempt = () => {
      if (!alive) return;
      load(() => {
        if (alive) timer = window.setTimeout(attempt, RETRY_MS);
      });
    };
    attempt();
    return () => {
      alive = false;
      window.clearTimeout(timer);
    };
  }, [load]);

  useEffect(() => {
    bindAuthLost(() => setUser(null));
    return () => bindAuthLost(null);
  }, []);

  return <SessionContext.Provider value={{ user, ready, offline, setUser }}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession outside SessionProvider");
  return value;
}
