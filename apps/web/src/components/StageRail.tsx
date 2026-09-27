import { PIPELINE_STAGES, type Stage } from "../types";

type StageRailProps = {
  current?: string;
  status?: string;
};

const STAGE_LABELS: Record<Stage, string> = {
  queued: "Queued",
  analyze: "Analyze",
  plan: "Plan",
  refs: "Refs",
  stills: "Stills",
  tts: "TTS",
  captions: "Captions",
  render: "Render",
  done: "Done",
  failed: "Failed",
};

function stageClass(stage: Stage, current?: string, status?: string): string {
  const currentIndex = PIPELINE_STAGES.indexOf(current as Stage);
  const index = PIPELINE_STAGES.indexOf(stage);
  if (status === "done") return "done";
  if (status === "failed" && stage === current) return "fail";
  if (currentIndex === -1) return "";
  if (index < currentIndex) return "done";
  if (index === currentIndex) return "now";
  return "";
}

export function StageRail({ current, status }: StageRailProps) {
  return (
    <ol className="stage-rail" aria-label="Pipeline stages">
      {PIPELINE_STAGES.map((stage) => (
        <li key={stage} className={stageClass(stage, current, status)}>
          <span className="stage-dot" />
          <span>{STAGE_LABELS[stage]}</span>
        </li>
      ))}
    </ol>
  );
}
