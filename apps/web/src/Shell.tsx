import { logout } from "./api";
import { useNav } from "./nav";
import { useSession } from "./session";
import type { ReactNode } from "react";

const LINKS = [
  { href: "/work", name: "work", label: "Việc của tôi" },
  { href: "/drama", name: "drama", label: "Drama" },
  { href: "/news", name: "news", label: "News" },
  { href: "/knowledge", name: "knowledge", label: "Kiến thức" },
  { href: "/account", name: "account", label: "Tài khoản" },
] as const;

export function Shell({ children }: { children: ReactNode }) {
  const { route, go } = useNav();
  const { user, setUser } = useSession();
  const current = route.name === "watch" ? "work" : route.name;
  const currentLabel = LINKS.find((link) => link.name === current)?.label ?? "Studio";

  return (
    <div className="app">
      <aside className="rail">
        <div className="brand-block">
          <p className="brand">omaishort</p>
          <p>Vertical story studio</p>
        </div>
        <nav>
          {LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className={current === link.name ? "on" : ""}
              onClick={(event) => {
                event.preventDefault();
                go(link.href);
              }}
            >
              {link.label}
            </a>
          ))}
        </nav>
        <div className="rail-foot">
          <p className="who">{user?.email}</p>
          <button
            type="button"
            className="ghost rail-logout"
            onClick={() => {
              void logout().then(() => {
                setUser(null);
                go("/login");
              });
            }}
          >
            Đăng xuất
          </button>
        </div>
      </aside>
      <main className="workspace">
        <header className="topbar">
          <div>
            <span className="topbar-label">Workspace</span>
            <strong>{currentLabel}</strong>
          </div>
          <div className="topbar-status">
            <span>Local render</span>
            <span>{user?.role || "user"}</span>
          </div>
        </header>
        <div className="stage">{children}</div>
      </main>
    </div>
  );
}
