import { useEffect, useMemo, useState } from "react";
import { dataFileUrl, readJob } from "../api";
import { PIPELINE_STAGES, type Job, type Stage } from "../types";

function stageClass(stage: Stage, current: string, status: string): string {
  const now = PIPELINE_STAGES.indexOf(current as Stage);
  const index = PIPELINE_STAGES.indexOf(stage);
  if (status === "done") return "done";
  if (status === "failed" && stage === current) return "fail";
  if (index < now) return "done";
  if (index === now) return "now";
  return "";
}

export function JobPage({ id }: { id: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    let stop = false;
    const tick = async () => {
      try {
        const data = await readJob(id);
        if (!stop) {
          setJob(data);
          setMissing(false);
        }
      } catch {
        if (!stop) setMissing(true);
      }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), 1500);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [id]);

  const stills = useMemo(() => {
    return (job?.storyboard?.scenes ?? []).map((scene) => ({
      ...scene,
      src: dataFileUrl(job?.artifacts?.[scene.still_id]),
    }));
  }, [job]);

  const videoSrc =
    job?.status === "done" ? dataFileUrl(job.artifacts?.mp4) ?? `/jobs/${id}/download` : null;
  const poster = stills.find((scene) => scene.src)?.src ?? undefined;
  const motion = job?.artifacts?.motion_mode;

  return (
    <section className="job">
      <div>
        <p className="kicker">{job?.storyboard?.kind || "short"}</p>
        <h1>{job?.storyboard?.title || id}</h1>
        {job ? (
          <ol className="stages">
            {PIPELINE_STAGES.map((stage) => (
              <li key={stage} className={stageClass(stage, job.stage, job.status)}>
                {stage}
              </li>
            ))}
          </ol>
        ) : (
          <p className="meta">{missing ? "Không thấy job." : "Đang tải…"}</p>
        )}
        {job?.error ? <pre className="err">{job.error}</pre> : null}
        {job?.structure ? (
          <div className="beats">
            {(["hook", "conflict", "rising_action", "twist", "ending"] as const).map((key) => (
              <p key={key}>
                <strong>{key.replaceAll("_", " ")}</strong> {job.structure?.[key]}
              </p>
            ))}
          </div>
        ) : null}
      </div>
      <div className="screen-col">
        <div className="frame">
          {videoSrc ? (
            <video controls playsInline poster={poster} src={videoSrc} />
          ) : poster ? (
            <img src={poster} alt="" />
          ) : (
            <p className="empty">1080×1920</p>
          )}
        </div>
        {videoSrc ? (
          <p>
            <a href={videoSrc} download>
              Tải MP4
            </a>
            {motion ? <span className="meta"> · motion {motion}</span> : null}
          </p>
        ) : null}
        {stills.length > 0 ? (
          <ul className="thumbs">
            {stills.map((scene) => (
              <li key={scene.still_id}>
                {scene.src ? <img src={scene.src} alt="" /> : <span className="ph" />}
                <span>
                  {scene.still_id} · {scene.shots.map((shot) => `${shot.camera}/${shot.motion}`).join(" → ")}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </section>
  );
}
