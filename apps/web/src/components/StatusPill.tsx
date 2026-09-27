type StatusTone = "idle" | "running" | "done" | "failed" | "accent";

type StatusPillProps = {
  label: string;
  tone?: StatusTone;
  title?: string;
};

export function toneForStatus(status?: string | null): StatusTone {
  if (!status) return "idle";
  if (status === "done") return "done";
  if (status === "failed") return "failed";
  if (status === "queued") return "idle";
  return "running";
}

export function StatusPill({ label, tone = "idle", title }: StatusPillProps) {
  return (
    <span className={`status-pill ${tone}`} title={title}>
      {label}
    </span>
  );
}
