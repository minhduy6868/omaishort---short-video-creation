import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { readMe, type AuthUser } from "./api";

type SessionValue = {
  user: AuthUser | null;
  ready: boolean;
  setUser: (user: AuthUser | null) => void;
};

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  const load = useCallback(() => {
    void readMe().then((me) => {
      setUser(me);
      setReady(true);
    });
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return <SessionContext.Provider value={{ user, ready, setUser }}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession outside SessionProvider");
  return value;
}
