type ProgressBarProps = {
  value: number;
  label?: string;
};

export function progressFromJob(progress?: string, status?: string): number {
  if (status === "done") return 100;
  if (status === "failed") return 100;
  if (!progress) return 0;
  const match = progress.match(/(\d+(?:\.\d+)?)/);
  if (!match) return 0;
  return Math.max(0, Math.min(100, Number(match[1])));
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
