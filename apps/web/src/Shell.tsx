import { logout } from "./api";
import { useNav } from "./nav";
import { useSession } from "./session";
import { ThemePicker } from "./theme";
import type { ReactNode } from "react";

const LINKS = [
  {
    href: "/work",
    name: "work",
    label: "Việc của tôi",
    icon: "M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6Zm0 9.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25Zm9.75-9.75A2.25 2.25 0 0 1 15.75 3.75H18a2.25 2.25 0 0 1 2.25 2.25v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6Zm0 9.75a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 15.75V18A2.25 2.25 0 0 1 18 20.25h-2.25A2.25 2.25 0 0 1 13.5 18v-2.25Z",
  },
  {
    href: "/drama",
    name: "drama",
    label: "Drama",
    icon: "M15.91 11.672a.375.375 0 0 1 0 .656l-6.54 3.78a.375.375 0 0 1-.563-.328V8.22a.375.375 0 0 1 .563-.327l6.54 3.78Z",
  },
  {
    href: "/news",
    name: "news",
    label: "News",
    icon: "M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 0 1-2.25 2.25M16.5 7.5V18a2.25 2.25 0 0 0 2.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 0 0 2.25 2.25h13.5",
  },
  {
    href: "/knowledge",
    name: "knowledge",
    label: "Kiến thức",
    icon: "M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342",
  },
  {
    href: "/account",
    name: "account",
    label: "Tài khoản",
    icon: "M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0",
  },
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
          <div className="brand-row">
            <span className="brand-mark" aria-hidden="true">O</span>
            <div>
              <p className="brand">omaishort</p>
              <p className="brand-sub">Studio Console</p>
            </div>
          </div>
        </div>

        <div className="rail-section">
          <span className="rail-group-label">Navigation</span>
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
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d={link.icon} />
                </svg>
                <span>{link.label}</span>
              </a>
            ))}
          </nav>
        </div>

        <div className="rail-section">
          <span className="rail-group-label">Public</span>
          <nav>
            <a href="/vi">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582" />
              </svg>
              <span>Trang giới thiệu</span>
            </a>
          </nav>
        </div>

        <div className="rail-foot">
          <div className="user-chip">
            <span className="user-avatar" aria-hidden="true">
              {(user?.display_name || user?.email || "U").slice(0, 1).toUpperCase()}
            </span>
            <div className="user-meta">
              <strong>{user?.display_name || "Operator"}</strong>
              <p className="who">{user?.email}</p>
            </div>
          </div>
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
          <div className="topbar-breadcrumbs">
            <span className="topbar-label">omaishort</span>
            <span className="topbar-sep">/</span>
            <strong>{currentLabel}</strong>
            {route.name === "watch" ? (
              <>
                <span className="topbar-sep">/</span>
                <code className="topbar-job-id">{route.id}</code>
              </>
            ) : null}
          </div>
          <div className="topbar-status">
            <ThemePicker />
            <span className="topbar-badge">
              <span className="topbar-dot" aria-hidden="true" />
              Local Engine
            </span>
            <span className="topbar-role">{user?.role || "user"}</span>
          </div>
        </header>
        <div className="stage">{children}</div>
      </main>
    </div>
  );
}
