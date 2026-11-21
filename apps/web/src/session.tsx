import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { bindAuthLost, hasSessionHint, readMe, type AuthUser } from "./api";

type SessionValue = {
  user: AuthUser | null;
  ready: boolean;
  offline: boolean;
  setUser: (user: AuthUser | null) => void;
  refreshMe: () => Promise<AuthUser | null>;
  ensureSessionLoaded: () => void;
};

const SessionContext = createContext<SessionValue | null>(null);

const RETRY_MS = 2000;
const STUDIO_PREFIXES = ["/login", "/register", "/work", "/drama", "/news", "/knowledge", "/account", "/admin", "/watch"];

function isStudioPath(pathname: string): boolean {
  return STUDIO_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const [offline, setOffline] = useState(false);
  const startedRef = useRef(false);
  const timerRef = useRef<number | undefined>(undefined);
  const aliveRef = useRef(true);

  const load = useCallback((onFail: () => void) => {
    readMe()
      .then((me) => {
        if (!aliveRef.current) return;
        setUser(me);
        setOffline(false);
        setReady(true);
      })
      .catch(() => {
        if (!aliveRef.current) return;
        setOffline(true);
        onFail();
      });
  }, []);

  const ensureSessionLoaded = useCallback(() => {
    if (startedRef.current) return;
    startedRef.current = true;
    const attempt = () => {
      if (!aliveRef.current) return;
      load(() => {
        if (aliveRef.current) timerRef.current = window.setTimeout(attempt, RETRY_MS);
      });
    };
    attempt();
  }, [load]);

  const refreshMe = useCallback(async (): Promise<AuthUser | null> => {
    try {
      const me = await readMe();
      setUser(me);
      setOffline(false);
      setReady(true);
      return me;
    } catch {
      return null;
    }
  }, []);

  useEffect(() => {
    aliveRef.current = true;
    if (isStudioPath(window.location.pathname) || hasSessionHint()) {
      ensureSessionLoaded();
    }
    return () => {
      aliveRef.current = false;
      startedRef.current = false;
      window.clearTimeout(timerRef.current);
    };
  }, [ensureSessionLoaded]);

  useEffect(() => {
    bindAuthLost(() => setUser(null));
    return () => bindAuthLost(null);
  }, []);

  return (
    <SessionContext.Provider value={{ user, ready, offline, setUser, refreshMe, ensureSessionLoaded }}>
      {children}
    </SessionContext.Provider>
  );
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession outside SessionProvider");
  return value;
}
