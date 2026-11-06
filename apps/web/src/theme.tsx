import { useSyncExternalStore } from "react";

export const THEMES = [
  {
    id: "darkroom",
    label: "Phòng tối",
    note: "Than ấm, terracotta, tiêu đề Fraunces",
    swatch: ["#14110e", "#c45c26", "#f3ece3"],
  },
  {
    id: "paper",
    label: "Giấy báo",
    note: "Nền giấy sáng, mực đen, hợp tin tức",
    swatch: ["#f3eee5", "#a8461a", "#1f1b16"],
  },
  {
    id: "bay",
    label: "Bàn dựng",
    note: "Graphite lạnh, hổ phách, tiêu đề sans",
    swatch: ["#0e1012", "#e3a33b", "#e6eaee"],
  },
] as const;

export type ThemeId = (typeof THEMES)[number]["id"];

const KEY = "omaishort.theme";
const listeners = new Set<() => void>();

function isTheme(value: string | null): value is ThemeId {
  return THEMES.some((theme) => theme.id === value);
}

function stored(): ThemeId {
  try {
    const value = localStorage.getItem(KEY);
    return isTheme(value) ? value : "darkroom";
  } catch {
    return "darkroom";
  }
}

export function setTheme(id: ThemeId): void {
  document.documentElement.dataset.theme = id;
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* private mode: theme still applies for this tab */
  }
  listeners.forEach((listener) => listener());
}

export function initTheme(): void {
  const fromUrl = new URLSearchParams(window.location.search).get("theme");
  setTheme(isTheme(fromUrl) ? fromUrl : stored());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function current(): ThemeId {
  const value = document.documentElement.dataset.theme ?? null;
  return isTheme(value) ? value : "darkroom";
}

export function useTheme(): ThemeId {
  return useSyncExternalStore(subscribe, current, current);
}

export function ThemePicker({ withLabels = false }: { withLabels?: boolean }) {
  const active = useTheme();
  return (
    <div className={`theme-picker${withLabels ? " labeled" : ""}`} role="radiogroup" aria-label="Giao diện">
      {THEMES.map((theme) => (
        <button
          key={theme.id}
          type="button"
          role="radio"
          aria-checked={active === theme.id}
          className={`theme-option${active === theme.id ? " on" : ""}`}
          title={`${theme.label}: ${theme.note}`}
          onClick={() => setTheme(theme.id)}
        >
          <span className="theme-swatch" aria-hidden="true">
            {theme.swatch.map((color) => (
              <span key={color} style={{ background: color }} />
            ))}
          </span>
          {withLabels ? (
            <span className="theme-text">
              <strong>{theme.label}</strong>
              <small>{theme.note}</small>
            </span>
          ) : (
            <span className="sr-only">{theme.label}</span>
          )}
        </button>
      ))}
    </div>
  );
}
