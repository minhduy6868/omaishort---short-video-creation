import type { Job, StoryDraft } from "./types";

export type VoiceOption = { id: string; language: string; label: string };

export function dataFileUrl(abs: string | undefined): string | null {
  if (!abs) return null;
  const norm = abs.replace(/\\/g, "/");
  const idx = norm.toLowerCase().lastIndexOf("/data/");
  if (idx === -1) return null;
  return `/files/${norm.slice(idx + "/data/".length)}`;
}

export async function createJob(draft: StoryDraft): Promise<{ id: string }> {
  const res = await fetch("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(draft),
  });
  if (!res.ok) {
    throw new Error("Could not create job");
  }
  return (await res.json()) as { id: string };
}

export async function readJob(id: string): Promise<Job> {
  const res = await fetch(`/jobs/${id}`);
  if (!res.ok) {
    throw new Error("job not found");
  }
  return (await res.json()) as Job;
}

export async function readVoices(language?: string): Promise<VoiceOption[]> {
  const q = language ? `?language=${encodeURIComponent(language)}` : "";
  const res = await fetch(`/voices${q}`);
  if (!res.ok) {
    return [];
  }
  const data = (await res.json()) as { voices?: VoiceOption[] };
  return Array.isArray(data.voices) ? data.voices : [];
}
