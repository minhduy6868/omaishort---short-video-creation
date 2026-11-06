export type Stage =
  | "queued"
  | "analyze"
  | "plan"
  | "refs"
  | "stills"
  | "tts"
  | "captions"
  | "render"
  | "done"
  | "failed";

export const PIPELINE_STAGES: Stage[] = [
  "analyze",
  "plan",
  "refs",
  "stills",
  "tts",
  "captions",
  "render",
];

export type ShotPreview = {
  camera: string;
  motion: string;
};

export type ScenePreview = {
  index: number;
  duration_sec: number;
  location: string;
  location_id?: string | null;
  emotion: string;
  still_id: string;
  dialogue_or_vo: string;
  shots: ShotPreview[];
};

export type JobStorageInfo = {
  job_id?: string;
  local_exists?: boolean;
  mp4_ready?: boolean;
  mp4_path?: string | null;
  mp4_bytes?: number;
  stills_bytes?: number;
  sourced_bytes?: number;
  refs_bytes?: number;
  audio_bytes?: number;
  other_bytes?: number;
  total_bytes?: number;
  file_count?: number;
  compacted?: boolean;
  compacted_at?: string;
  freed_bytes?: number;
  duration_sec?: number;
  width?: number;
  height?: number;
};

export type Job = {
  id: string;
  status: string;
  stage: Stage | string;
  error?: string | null;
  progress?: string;
  user_id?: string | null;
  user_email?: string | null;
  created_at?: string;
  updated_at?: string;
  input?: Partial<StoryDraft> & Record<string, unknown>;
  structure?: {
    hook: string;
    conflict: string;
    rising_action: string;
    twist: string;
    ending: string;
  };
  storyboard?: {
    title: string;
    kind?: string;
    scenes: ScenePreview[];
  };
  artifacts?: Record<string, string>;
  storage?: JobStorageInfo;
};

export type VideoKind = "drama" | "news" | "knowledge";

export type DramaShape = "infer" | "default" | "custom";

export type StoryDraft = {
  mode: "script" | "idea";
  kind: VideoKind;
  text: string;
  target_seconds: number;
  genre: string;
  drama_shape?: DramaShape;
  language: string;
  voice_id?: string | null;
  source_url?: string | null;
  script_brief?: string | null;
  attachments?: { id: string; bind?: string | null }[];
  mix?: {
    bgm_enabled?: boolean;
    logo_enabled?: boolean;
  };
};
