import type { Job, JobStorageInfo, StoryDraft } from "./types";

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
let refreshInflight: Promise<boolean> | null = null;
let onAuthLost: (() => void) | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function bindAuthLost(handler: (() => void) | null) {
  onAuthLost = handler;
}

async function refreshSession(): Promise<boolean> {
  if (!refreshInflight) {
    refreshInflight = (async () => {
      const refreshed = await fetch("/auth/refresh", { method: "POST", credentials: "include" });
      if (!refreshed.ok) {
        setAccessToken(null);
        onAuthLost?.();
        return false;
      }
      const payload = (await refreshed.json()) as AuthPayload;
      setAccessToken(payload.access_token);
      return true;
    })().finally(() => {
      refreshInflight = null;
    });
  }
  return refreshInflight;
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
  const ok = await refreshSession();
  if (!ok) return res;
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
  if (res.status >= 500) throw new Error(`API unavailable (${res.status})`);
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

export async function listJobs(): Promise<Job[]> {
  const res = await request("/jobs");
  if (!res.ok) throw await parseError(res, "Không tải được danh sách job");
  const data = (await res.json()) as { jobs?: Job[] };
  return Array.isArray(data.jobs) ? data.jobs : [];
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
  chatgpt_web_chat?: string;
};

export async function startChatgptLogin(): Promise<{ status: string }> {
  const res = await request("/providers/chatgpt-login", { method: "POST" });
  if (!res.ok) throw await parseError(res, "Could not open ChatGPT");
  return (await res.json()) as { status: string };
}

export async function startGrokLogin(): Promise<{ status: string }> {
  const res = await request("/providers/grok-login", { method: "POST" });
  if (!res.ok) throw await parseError(res, "Could not open Grok");
  return (await res.json()) as { status: string };
}

export async function openChatgptContent(): Promise<{ status: string }> {
  const res = await request("/providers/chatgpt-open", { method: "POST" });
  if (!res.ok) throw await parseError(res, "Could not open ChatGPT");
  return (await res.json()) as { status: string };
}

export type ElevenLabsVoice = { id: string; name: string };

export type ElevenLabsHub = {
  enabled: boolean;
  configured: boolean;
  mode?: "anonymous" | "api";
  model_id?: string;
  voice_id: string;
  voice_name: string;
  key_hint: string;
  voices: ElevenLabsVoice[];
  error?: string;
};

export async function readElevenLabs(): Promise<ElevenLabsHub> {
  const res = await request("/providers/elevenlabs");
  if (!res.ok) throw await parseError(res, "Could not read ElevenLabs");
  return (await res.json()) as ElevenLabsHub;
}

export async function saveElevenLabs(body: {
  api_key?: string;
  voice_id?: string;
  enabled?: boolean;
  mode?: "anonymous" | "api";
  model_id?: string;
}): Promise<ElevenLabsHub> {
  const res = await request("/providers/elevenlabs", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseError(res, "Could not save ElevenLabs");
  return (await res.json()) as ElevenLabsHub;
}

export async function readProviders(): Promise<ProviderStatus | null> {
  const res = await request("/providers");
  if (!res.ok) return null;
  return (await res.json()) as ProviderStatus;
}

export type StorageSummary = {
  data_dir: string;
  jobs_bytes: number;
  jobs_files: number;
  job_dirs_count: number;
  mp4_count: number;
  mp4_bytes: number;
  attachments_local_bytes: number;
  attachments_local_files: number;
  total_local_bytes: number;
  orphan_job_ids: string[];
};

export type LocalVideoEntry = {
  id: string;
  title: string;
  kind: string;
  status: string;
  stage: string;
  progress?: string;
  user_id?: string | null;
  user_email?: string | null;
  created_at?: string;
  updated_at?: string;
  download_url?: string | null;
  watch_url: string;
  storage: JobStorageInfo;
};

export type AdminStats = {
  users_total: number;
  operators_total: number;
  jobs_total: number;
  jobs_by_status: Record<string, number>;
  attachments_total: number;
  attachments_bytes: number;
  db_backend: string;
};

export type AdminSettings = {
  site_theme: string;
  themes: string[];
  signup_enabled: boolean;
};

export type AdminOverview = {
  stats: AdminStats;
  storage: StorageSummary;
  settings: AdminSettings;
  providers: ProviderStatus;
};

export type AdminUserRow = {
  id: string;
  email: string;
  display_name: string | null;
  role: "operator" | "creator" | string;
  locked: boolean;
  locked_until: string | null;
  failed_logins: number;
  jobs_count: number;
  attachments_count: number;
  attachments_bytes: number;
  created_at?: string;
  updated_at?: string;
};

export async function compactJobStorage(jobId: string): Promise<JobStorageInfo> {
  const res = await request(`/jobs/${encodeURIComponent(jobId)}/compact`, { method: "POST" });
  if (!res.ok) throw await parseError(res, "Không dọn được file tạm của job");
  return (await res.json()) as JobStorageInfo;
}

export async function deleteJob(jobId: string, keepDb = false): Promise<{ freed_bytes: number }> {
  const q = keepDb ? "?keep_db=true" : "";
  const res = await request(`/jobs/${encodeURIComponent(jobId)}${q}`, { method: "DELETE" });
  if (!res.ok) throw await parseError(res, "Không xóa được job");
  return (await res.json()) as { freed_bytes: number };
}

export async function listLocalVideos(allUsers = false): Promise<{ videos: LocalVideoEntry[]; summary: StorageSummary | null }> {
  const q = allUsers ? "?all_users=true" : "";
  const res = await request(`/storage/videos${q}`);
  if (!res.ok) throw await parseError(res, "Không tải được danh sách video local");
  return (await res.json()) as { videos: LocalVideoEntry[]; summary: StorageSummary | null };
}

export async function readAdminOverview(): Promise<AdminOverview> {
  const res = await request("/admin/overview");
  if (!res.ok) throw await parseError(res, "Không tải được tổng quan admin");
  return (await res.json()) as AdminOverview;
}

export async function listAdminUsers(): Promise<AdminUserRow[]> {
  const res = await request("/admin/users");
  if (!res.ok) throw await parseError(res, "Không tải được danh sách người dùng");
  const data = (await res.json()) as { users?: AdminUserRow[] };
  return Array.isArray(data.users) ? data.users : [];
}

export async function patchAdminUser(
  userId: string,
  body: { role?: string; locked?: boolean; display_name?: string; revoke_sessions?: boolean },
): Promise<AdminUserRow> {
  const res = await request(`/admin/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    headers: headers(undefined, true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseError(res, "Không cập nhật được người dùng");
  const data = (await res.json()) as { user: AdminUserRow };
  return data.user;
}

export async function listAdminJobs(statusFilter?: string): Promise<Job[]> {
  const q = statusFilter && statusFilter !== "all" ? `?status=${encodeURIComponent(statusFilter)}` : "";
  const res = await request(`/admin/jobs${q}`);
  if (!res.ok) throw await parseError(res, "Không tải được danh sách job toàn hệ thống");
  const data = (await res.json()) as { jobs?: Job[] };
  return Array.isArray(data.jobs) ? data.jobs : [];
}

export async function retryAdminJob(jobId: string): Promise<{ id: string; status: string }> {
  const res = await request(`/admin/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
  if (!res.ok) throw await parseError(res, "Không chạy lại được job");
  return (await res.json()) as { id: string; status: string };
}

export async function deleteAdminJob(jobId: string, keepDb = false): Promise<{ freed_bytes: number }> {
  const q = keepDb ? "?keep_db=true" : "";
  const res = await request(`/admin/jobs/${encodeURIComponent(jobId)}${q}`, { method: "DELETE" });
  if (!res.ok) throw await parseError(res, "Không xóa được job");
  return (await res.json()) as { freed_bytes: number };
}

export async function readAdminStorage(): Promise<{ summary: StorageSummary; videos: LocalVideoEntry[] }> {
  const res = await request("/admin/storage");
  if (!res.ok) throw await parseError(res, "Không đọc được thông tin lưu trữ local");
  return (await res.json()) as { summary: StorageSummary; videos: LocalVideoEntry[] };
}

export async function cleanupAdminStorage(body: {
  remove_orphans?: boolean;
  compact_done?: boolean;
}): Promise<{ freed_bytes: number; removed_orphans: string[]; compacted_jobs: string[]; summary: StorageSummary }> {
  const res = await request("/admin/storage/cleanup", {
    method: "POST",
    headers: headers(undefined, true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseError(res, "Không dọn dẹp được ổ đĩa local");
  return (await res.json()) as {
    freed_bytes: number;
    removed_orphans: string[];
    compacted_jobs: string[];
    summary: StorageSummary;
  };
}

export async function saveAdminSettings(body: {
  site_theme?: string;
  signup_enabled?: boolean;
}): Promise<AdminSettings> {
  const res = await request("/admin/settings", {
    method: "PUT",
    headers: headers(undefined, true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await parseError(res, "Không lưu được cài đặt hệ thống");
  return (await res.json()) as AdminSettings;
}
