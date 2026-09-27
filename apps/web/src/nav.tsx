import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type Route =
  | { name: "login" }
  | { name: "register" }
  | { name: "work" }
  | { name: "drama" }
  | { name: "news" }
  | { name: "knowledge" }
  | { name: "account" }
  | { name: "watch"; id: string };

const NAMES = new Set(["login", "register", "work", "drama", "news", "knowledge", "account"]);

export function parsePath(path: string): Route {
  const clean = path.split("?")[0].replace(/\/+$/, "") || "/";
  const watch = clean.match(/^\/watch\/([^/]+)$/);
  if (watch) return { name: "watch", id: decodeURIComponent(watch[1]) };
  const leaf = clean.slice(1);
  if (NAMES.has(leaf)) return { name: leaf } as Route;
  return { name: "work" };
}

export function pathFor(route: Route): string {
  if (route.name === "watch") return `/watch/${encodeURIComponent(route.id)}`;
  if (route.name === "work") return "/work";
  return `/${route.name}`;
}

type NavValue = { route: Route; go: (path: string) => void };

const NavContext = createContext<NavValue | null>(null);

export function NavProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState(() => parsePath(window.location.pathname));

  useEffect(() => {
    const onPop = () => setRoute(parsePath(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const go = useCallback((path: string) => {
    if (window.location.pathname !== path) window.history.pushState({}, "", path);
    setRoute(parsePath(path));
  }, []);

  return <NavContext.Provider value={{ route, go }}>{children}</NavContext.Provider>;
}

export function useNav(): NavValue {
  const value = useContext(NavContext);
  if (!value) throw new Error("useNav outside NavProvider");
  return value;
}
