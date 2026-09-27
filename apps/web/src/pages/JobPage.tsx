import { useEffect, useMemo, useState } from "react";
import { dataFileUrl, readJob } from "../api";
import {
  PageHeader,
  PhonePreview,
  ProgressBar,
  SceneStrip,
  StageRail,
  StatusPill,
  progressFromJob,
  toneForStatus,
  type SceneWithSrc,
} from "../components";
import type { Job } from "../types";

const BEATS = [
  ["hook", "Hook"],
  ["conflict", "Conflict"],
  ["rising_action", "Rising"],
  ["twist", "Twist"],
  ["ending", "Ending"],
] as const;

function terminal(status?: string): boolean {
  return status === "done" || status === "failed";
}

export function JobPage({ id }: { id: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [missing, setMissing] = useState(false);
  const [lastPoll, setLastPoll] = useState<Date | null>(null);

  useEffect(() => {
    let stop = false;
    let timer = 0;
    const tick = async () => {
      try {
        const data = await readJob(id);
        if (stop) return;
        setJob(data);
        setMissing(false);
        setLastPoll(new Date());
        if (terminal(data.status) && timer) window.clearInterval(timer);
      } catch {
        if (!stop) setMissing(true);
      }
    };
    void tick();
    timer = window.setInterval(() => void tick(), 1500);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [id]);

  const stills: SceneWithSrc[] = useMemo(() => {
    return (job?.storyboard?.scenes ?? []).map((scene) => ({
      ...scene,
      src: dataFileUrl(job?.artifacts?.[scene.still_id]),
    }));
  }, [job]);

  const videoSrc = job?.status === "done" ? dataFileUrl(job.artifacts?.mp4) ?? `/jobs/${id}/download` : null;
  const poster = stills.find((scene) => scene.src)?.src ?? undefined;
  const motion = job?.artifacts?.motion_mode || "pending";
  const progress = progressFromJob(job?.progress, job?.status);

  return (
    <section className="page-stack watch-page">
      <PageHeader
        kicker={job?.storyboard?.kind || "short"}
        title={job?.storyboard?.title || id}
        lede="Màn hình theo dõi production: stage, preview dọc, scene stills, beats và artifact tải xuống."
        actions={
          videoSrc ? (
            <a className="button" href={videoSrc} download>
              Tải MP4
            </a>
          ) : null
        }
        meta={
          job ? (
            <div className="provider-row">
              <StatusPill label={job.status} tone={toneForStatus(job.status)} />
              <StatusPill label={`stage ${job.stage}`} tone={job.status === "failed" ? "failed" : "accent"} />
              <StatusPill label={`motion ${motion}`} tone={motion === "pending" ? "idle" : "done"} />
              {lastPoll ? <span>Cập nhật {lastPoll.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span> : null}
            </div>
          ) : null
        }
      />

      <div className="watch-layout">
        <aside className="panel watch-inspector">
          <div className="section-head compact">
            <div>
              <p className="kicker">Stages</p>
              <h2>Pipeline</h2>
            </div>
          </div>
          {job ? <StageRail current={job.stage} status={job.status} /> : <p className="meta">{missing ? "Không thấy job." : "Đang tải…"}</p>}
          {job ? <ProgressBar value={progress} label={job.progress || `${Math.round(progress)}%`} /> : null}
          {job?.error ? (
            <div className="error-panel">
              <strong>Lỗi render</strong>
              <pre className="err">{job.error}</pre>
            </div>
          ) : null}
          <div className="artifact-list">
            <p className="card-title">Artifacts</p>
            <span>MP4: {videoSrc ? "ready" : "pending"}</span>
            <span>Stills: {stills.filter((scene) => scene.src).length}/{stills.length}</span>
            <span>Motion: {motion}</span>
          </div>
        </aside>

        <main className="watch-main">
          <PhonePreview videoSrc={videoSrc} poster={poster} />
          {videoSrc ? (
            <div className="download-row">
              <a className="button" href={videoSrc} download>
                Tải MP4
              </a>
              <span className="meta">Motion mode: {motion}</span>
            </div>
          ) : (
            <p className="meta">Preview sẽ chuyển từ still sang MP4 khi render hoàn tất.</p>
          )}
        </main>

        <aside className="watch-side">
          {job?.structure ? (
            <section className="panel beats-panel">
              <div className="section-head compact">
                <div>
                  <p className="kicker">Beats</p>
                  <h2>Cấu trúc</h2>
                </div>
              </div>
              {BEATS.map(([key, label]) => (
                <article key={key} className="beat-card">
                  <strong>{label}</strong>
                  <p>{job.structure?.[key]}</p>
                </article>
              ))}
            </section>
          ) : null}

          <section className="panel scenes-panel">
            <div className="section-head compact">
              <div>
                <p className="kicker">Scenes</p>
                <h2>Contact sheet</h2>
              </div>
              <StatusPill label={`${stills.length} scenes`} tone={stills.length ? "accent" : "idle"} />
            </div>
            <SceneStrip scenes={stills} />
            {stills.length === 0 ? <p className="meta">Storyboard chưa sẵn sàng.</p> : null}
          </section>
        </aside>
      </div>
    </section>
  );
}
