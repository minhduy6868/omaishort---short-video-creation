type ProgressBarProps = {
  value: number;
  label?: string;
};

const STAGE_PERCENT: Record<string, number> = {
  queued: 4,
  analyze: 18,
  plan: 32,
  refs: 44,
  stills: 52,
  tts: 76,
  captions: 86,
  render: 94,
  done: 100,
};

const PROGRESS_COPY: Record<string, string> = {
  resume: "Tiếp tục job",
  script: "Đang viết lời",
  analyze: "Đang phân tích",
  plan: "Đang chia cảnh",
  refs: "Đang dựng ảnh mẫu",
  stills: "Đang dựng still",
  "stills:search": "Đang tìm ảnh theo từng nhịp",
  tts: "Đang đọc lời",
  captions: "Đang ghép phụ đề",
  render: "Đang render",
  done: "Xong",
  failed: "Dừng vì lỗi",
};

export function progressFromJob(progress?: string, status?: string, stage?: string): number {
  if (status === "done") return 100;
  const fraction = progress?.match(/^stills:(\d+)\/(\d+)$/);
  if (fraction) {
    const done = Number(fraction[1]);
    const total = Math.max(1, Number(fraction[2]));
    return Math.min(74, 52 + Math.round((done / total) * 22));
  }
  if (progress === "stills:search" || progress === "script") return progress === "script" ? 10 : 58;
  const base = STAGE_PERCENT[stage || ""] ?? STAGE_PERCENT[progress || ""] ?? 0;
  if (status === "failed") return base;
  return base;
}

export function progressCopy(progress?: string, stage?: string): string {
  if (!progress) return PROGRESS_COPY[stage || ""] || "";
  const fraction = progress.match(/^stills:(\d+)\/(\d+)$/);
  if (fraction) return `Still ${fraction[1]}/${fraction[2]}`;
  return PROGRESS_COPY[progress] || PROGRESS_COPY[stage || ""] || progress;
}

export function ProgressBar({ value, label }: ProgressBarProps) {
  const safeValue = Math.max(0, Math.min(100, value));
  return (
    <div className="progress-wrap" aria-label={label || `Tiến độ ${Math.round(safeValue)}%`}>
      <div className="progress-track">
        <span className="progress-fill" style={{ width: `${safeValue}%` }} />
      </div>
      {label ? <span className="progress-label">{label}</span> : null}
    </div>
  );
}
