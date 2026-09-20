import type { Job, StoryDraft } from "./types";

export type VoiceOption = { id: string; language: string; label: string };

export type AuthUser = {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
};

export type AttachmentRow = {
  id: string;
  kind: string;
  filename: string;
  mime: string;
  byte_size: number;
  sha256: string;
  created_at: string;
};

type AuthPayload = {
  user: AuthUser;
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
};

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

function headers(extra?: HeadersInit, json = false): Headers {
  const out = new Headers(extra);
  if (json && !out.has("Content-Type")) out.set("Content-Type", "application/json");
  if (accessToken && !out.has("Authorization")) out.set("Authorization", `Bearer ${accessToken}`);
  return out;
}

async function parseError(res: Response, fallback: string): Promise<Error> {
  try {
    const data = (await res.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return new Error(data.detail);
  } catch {
    /* ignore */
  }
  return new Error(fallback);
}

// These endpoints must never trigger a refresh retry (they mint/rotate the session themselves).
const NO_REFRESH = ["/auth/refresh", "/auth/login", "/auth/register", "/auth/logout"];

async function request(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const res = await fetch(path, { credentials: "include", ...init, headers: headers(init.headers) });
  if (res.status !== 401 || !retry || NO_REFRESH.some((p) => path.startsWith(p))) return res;
  const refreshed = await fetch("/auth/refresh", { method: "POST", credentials: "include" });
  if (!refreshed.ok) {
    setAccessToken(null);
    return res;
  }
  const payload = (await refreshed.json()) as AuthPayload;
  setAccessToken(payload.access_token);
  return request(path, init, false);
}

export function dataFileUrl(abs: string | undefined): string | null {
  if (!abs) return null;
  const norm = abs.replace(/\\/g, "/");
  const idx = norm.toLowerCase().lastIndexOf("/data/");
  if (idx === -1) return null;
  return `/files/${norm.slice(idx + "/data/".length)}`;
}

export async function register(email: string, password: string, displayName?: string): Promise<AuthUser> {
  const res = await request(
    "/auth/register",
    {
      method: "POST",
      headers: headers(undefined, true),
      body: JSON.stringify({ email, password, display_name: displayName || null }),
    },
    false,
  );
  if (!res.ok) throw await parseError(res, "Could not register");
  const payload = (await res.json()) as AuthPayload;
  setAccessToken(payload.access_token);
  return payload.user;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const res = await request(
    "/auth/login",
    {
      method: "POST",
      headers: headers(undefined, true),
      body: JSON.stringify({ email, password }),
    },
    false,
  );
  if (!res.ok) throw await parseError(res, "Could not sign in");
  const payload = (await res.json()) as AuthPayload;
  setAccessToken(payload.access_token);
  return payload.user;
}

export async function logout(): Promise<void> {
  await request("/auth/logout", { method: "POST" }, false);
  setAccessToken(null);
}

export async function readMe(): Promise<AuthUser | null> {
  // retry=true so a reload after the 15-min access cookie expires refreshes from the refresh cookie.
  const res = await request("/auth/me");
  if (!res.ok) return null;
  return (await res.json()) as AuthUser;
}

export async function createJob(draft: StoryDraft): Promise<{ id: string }> {
  const res = await request("/jobs", {
    method: "POST",
    headers: headers(undefined, true),
    body: JSON.stringify(draft),
  });
  if (!res.ok) throw await parseError(res, "Could not create job");
  return (await res.json()) as { id: string };
}

export async function readJob(id: string): Promise<Job> {
  const res = await request(`/jobs/${id}`);
  if (!res.ok) throw new Error("job not found");
  return (await res.json()) as Job;
}

export async function readVoices(language?: string): Promise<VoiceOption[]> {
  const q = language ? `?language=${encodeURIComponent(language)}` : "";
  const res = await fetch(`/voices${q}`, { credentials: "include" });
  if (!res.ok) return [];
  const data = (await res.json()) as { voices?: VoiceOption[] };
  return Array.isArray(data.voices) ? data.voices : [];
}

export async function uploadAttachment(kind: string, file: File): Promise<AttachmentRow> {
  const body = new FormData();
  body.append("file", file);
  const res = await request(`/attachments?kind=${encodeURIComponent(kind)}`, { method: "POST", body });
  if (!res.ok) throw await parseError(res, "Upload failed");
  return (await res.json()) as AttachmentRow;
}

export async function listAttachments(): Promise<AttachmentRow[]> {
  const res = await request("/attachments");
  if (!res.ok) return [];
  const data = (await res.json()) as { attachments?: AttachmentRow[] };
  return Array.isArray(data.attachments) ? data.attachments : [];
}

export type ProviderStatus = {
  grok_image?: boolean;
  grok_video?: boolean;
  grok_hub?: boolean;
  grok_hub_authed?: boolean;
  drama_motion?: string;
  image?: Record<string, boolean>;
  video?: Record<string, boolean>;
  tts?: Record<string, boolean>;
  chatgpt_web?: boolean;
  chatgpt_web_authed?: boolean;
};

export async function readProviders(): Promise<ProviderStatus | null> {
  const res = await request("/providers");
  if (!res.ok) return null;
  return (await res.json()) as ProviderStatus;
}
