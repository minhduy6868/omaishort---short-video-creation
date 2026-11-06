import { useState, useSyncExternalStore } from "react";

export const THEMES = [
  {
    id: "brutal",
    label: "Khối thô",
    note: "Neo-brutalism: viền đen dày, bóng cứng, vàng và cam",
    swatch: ["#fff4d6", "#ff5c39", "#111111"],
  },
  {
    id: "soft",
    label: "Gối mềm",
    note: "Soft UI: khối nổi, ô nhập lõm, bóng mềm hai chiều",
    swatch: ["#e4e8ee", "#2f5bea", "#1f2633"],
  },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

const DEFAULT_THEME: ThemeId = "brutal";
const CACHE_KEY = "omaishort.site-theme";
const listeners = new Set<() => void>();

function isTheme(value: unknown): value is ThemeId {
  return THEMES.some((theme) => theme.id === value);
}

function cached(): ThemeId {
  try {
    const value = localStorage.getItem(CACHE_KEY);
    return isTheme(value) ? value : DEFAULT_THEME;
  } catch {
    return DEFAULT_THEME;
  }
}

function apply(id: ThemeId): void {
  document.documentElement.dataset.theme = id;
  listeners.forEach((listener) => listener());
}

function remember(id: ThemeId): void {
  apply(id);
  try {
    localStorage.setItem(CACHE_KEY, id);
  } catch {
    /* private mode: theme still applies for this tab */
  }
}

/** The admin picks the site theme on the server; `?theme=` previews one without saving. */
export function initTheme(): void {
  const preview = new URLSearchParams(window.location.search).get("theme");
  if (isTheme(preview)) {
    apply(preview);
    return;
  }
  apply(cached());
  void fetch("/site/theme")
    .then((res) => (res.ok ? res.json() : null))
    .then((body: { theme?: unknown } | null) => {
      if (isTheme(body?.theme)) remember(body.theme);
    })
    .catch(() => undefined);
}

export async function saveSiteTheme(id: ThemeId): Promise<void> {
  const res = await fetch("/site/theme", {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ theme: id }),
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(body?.detail || `Không lưu được giao diện (${res.status})`);
  }
  remember(id);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function current(): ThemeId {
  const value = document.documentElement.dataset.theme ?? null;
  return isTheme(value) ? value : DEFAULT_THEME;
}

export function useTheme(): ThemeId {
  return useSyncExternalStore(subscribe, current, current);
}

export function SiteThemePicker({ editable }: { editable: boolean }) {
  const active = useTheme();
  const [saving, setSaving] = useState<ThemeId | null>(null);
  const [error, setError] = useState("");

  const choose = (id: ThemeId) => {
    if (!editable || saving || id === active) return;
    setSaving(id);
    setError("");
    saveSiteTheme(id)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setSaving(null));
  };

  return (
    <>
      <div className="theme-picker labeled" role="radiogroup" aria-label="Giao diện toàn site">
        {THEMES.map((theme) => (
          <button
            key={theme.id}
            type="button"
            role="radio"
            aria-checked={active === theme.id}
            disabled={!editable || saving !== null}
            className={`theme-option${active === theme.id ? " on" : ""}`}
            title={`${theme.label}: ${theme.note}`}
            onClick={() => choose(theme.id)}
          >
            <span className="theme-swatch" aria-hidden="true">
              {theme.swatch.map((color) => (
                <span key={color} style={{ background: color }} />
              ))}
            </span>
            <span className="theme-text">
              <strong>{theme.label}</strong>
              <small>{saving === theme.id ? "Đang lưu…" : theme.note}</small>
            </span>
          </button>
        ))}
      </div>
      {error ? <p className="err">{error}</p> : null}
    </>
  );
}
