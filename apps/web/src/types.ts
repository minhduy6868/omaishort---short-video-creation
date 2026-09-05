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

export type Job = {
  id: string;
  status: string;
  stage: Stage | string;
  error?: string | null;
  progress?: string;
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
};

export type VideoKind = "drama" | "news" | "knowledge";

export type StoryDraft = {
  mode: "script" | "idea";
  kind: VideoKind;
  text: string;
  target_seconds: number;
  genre: string;
  language: string;
  source_url?: string | null;
  mix?: {
    bgm_enabled?: boolean;
    logo_enabled?: boolean;
  };
};
