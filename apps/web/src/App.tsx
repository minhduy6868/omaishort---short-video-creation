import { FormEvent, useEffect, useMemo, useState } from "react";
import { createJob, dataFileUrl, readJob } from "./api";
import "./App.css";
import { PIPELINE_STAGES, type Job, type Stage, type VideoKind } from "./types";

const DRAMA_SAMPLE = `I found his phone on the counter at 2:17 a.m. He said he was sleeping. The lock screen was a photo of us. The messages were not.

Her name was Mara. She asked if I would be home this weekend. He typed, Don't worry. She never checks.`;

const NEWS_SAMPLE = `Tiêu đề: Trái đắng của người phụ nữ lấy chồng kém 37 tuổi.

Sharon, 61 tuổi ở Yorkshire, kết hôn với sinh viên Nigeria kém mình 37 tuổi sau khi quen trên ứng dụng hẹn hò.

Gia đình phản đối. Anh xin thị thực, hứa xây tương lai ở Anh.

Sau đăng ký kết hôn, mâu thuẫn về tiền bạc và chỗ ở bắt đầu.

Anh bỏ đi Nigeria. Cô mất nhà, phải ly hôn, và giữ lại rất ít tài sản.`;

const KNOWLEDGE_SAMPLE = `Thuyết minh về lạm phát và cách nó vận hành.`;

const DRAMA_GENRES = ["confession", "cheating", "revenge", "twist", "family", "drama"] as const;
const EDITORIAL_GENRES = ["news", "knowledge"] as const;

function isEditorial(kind: VideoKind): boolean {
  return kind === "news" || kind === "knowledge";
}

export default function App() {
  const [kind, setKind] = useState<VideoKind>("drama");
  const [text, setText] = useState(DRAMA_SAMPLE);
  const [mode, setMode] = useState<"script" | "idea">("script");
  const [genre, setGenre] = useState("confession");
  const [language, setLanguage] = useState("en");
  const [seconds, setSeconds] = useState(60);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [logoEnabled, setLogoEnabled] = useState(false);

  useEffect(() => {
    if (!jobId) return;
    let stop = false;
    const tick = async () => {
      try {
        const data = await readJob(jobId);
        if (!stop) setJob(data);
        if (data.status === "done" || data.status === "failed") setBusy(false);
      } catch {
        /* poll continues */
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 1500);
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [jobId]);

  function onKindChange(next: VideoKind) {
    const samples: Record<VideoKind, string> = {
      drama: DRAMA_SAMPLE,
      news: NEWS_SAMPLE,
      knowledge: KNOWLEDGE_SAMPLE,
    };
    if (Object.values(samples).includes(text)) setText(samples[next]);
    setKind(next);
    if (next === "drama") {
      setGenre("confession");
      setLanguage("en");
      setSeconds(60);
    } else {
      setGenre(next === "knowledge" ? "knowledge" : "news");
      setLanguage("vi");
      setSeconds(90);
    }
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setJob(null);
    try {
      const data = await createJob({
        mode,
        kind,
        text: text.trim().length >= 8 ? text : `News from ${sourceUrl.trim()}`,
        target_seconds: seconds,
        genre,
        language,
        source_url: isEditorial(kind) ? sourceUrl.trim() || null : null,
        mix: { logo_enabled: logoEnabled },
      });
      setJobId(data.id);
    } catch (err) {
      setBusy(false);
      setMessage(err instanceof Error ? err.message : "Could not create job");
    }
  }

  const stills = useMemo(() => {
    const board = job?.storyboard?.scenes ?? [];
    return board.map((scene) => ({
      ...scene,
      src: dataFileUrl(job?.artifacts?.[scene.still_id]),
    }));
  }, [job]);

  const videoSrc =
    job?.status === "done"
      ? dataFileUrl(job.artifacts?.mp4) ?? (jobId ? `/jobs/${jobId}/download` : null)
      : null;
  const poster = stills.find((scene) => scene.src)?.src ?? undefined;
  const genres = isEditorial(kind) ? EDITORIAL_GENRES : DRAMA_GENRES;
  const submitLabel =
    kind === "news" ? "Make news short" : kind === "knowledge" ? "Make knowledge short" : "Make drama short";
  const lede =
    kind === "news"
      ? "Paste a news URL or notes. Five beats cover the full article, including the ending. Stills match each beat — article photos first, then CC search, never Pexels."
      : kind === "knowledge"
        ? "Paste a topic (thuyết minh về lạm phát…), one claim, or a GitHub URL. The engine writes the explainer — it does not echo the request or dump a README."
        : "Paste a confession. One still per scene, bible-locked faces, beat cameras. I2V only when keyed — otherwise Ken Burns, never faked as video.";

  return (
    <div className="shell">
      <header className="mast">
        <p className="kicker">Story Video Engine</p>
        <h1>omaishort</h1>
        <p className="lede">
          {lede}
        </p>
      </header>

      <form className="panel" onSubmit={onSubmit}>
        <div className="row">
          <label>
            Kind
            <select value={kind} onChange={(e) => onKindChange(e.target.value as VideoKind)}>
              <option value="drama">Drama story</option>
              <option value="news">News</option>
              <option value="knowledge">Kiến thức</option>
            </select>
          </label>
          <label>
            Mode
            <select value={mode} onChange={(e) => setMode(e.target.value as "script" | "idea")}>
              <option value="script">Script</option>
              <option value="idea">Idea</option>
            </select>
          </label>
          <label>
            Genre
            <select value={genre} onChange={(e) => setGenre(e.target.value)}>
              {genres.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            Language
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="en">en</option>
              <option value="vi">vi</option>
            </select>
          </label>
          <label>
            Seconds
            <input
              type="number"
              min={15}
              max={180}
              value={seconds}
              onChange={(e) => setSeconds(Number(e.target.value))}
            />
          </label>
        </div>
        {isEditorial(kind) ? (
          <label className="source-url">
            {kind === "knowledge" ? "GitHub URL (optional)" : "Article URL"}
            <input
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder={kind === "knowledge" ? "https://github.com/owner/repo — or leave empty" : "https://vnexpress.net/…"}
            />
          </label>
        ) : null}
        <label className="logo-opt">
          <input type="checkbox" checked={logoEnabled} onChange={(e) => setLogoEnabled(e.target.checked)} />
          Overlay logo (assets/logo)
        </label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          placeholder={kind === "knowledge" ? "Thuyết minh về lạm phát và cách nó vận hành" : undefined}
        />
        <div className="actions">
          <button type="submit" disabled={busy || (text.trim().length < 8 && sourceUrl.trim().length < 12)}>
            {busy ? "Rendering…" : submitLabel}
          </button>
          {jobId && <span className="jobid">job {jobId}</span>}
          <label className="load-job">
            Load job
            <input
              value={jobId ?? ""}
              onChange={(e) => {
                const id = e.target.value.trim();
                setJobId(id || null);
                setJob(null);
                setBusy(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") e.preventDefault();
              }}
              placeholder="dryrun-…"
            />
          </label>
        </div>
      </form>

      {job && (
        <section className="panel">
          <ol className="stages">
            {PIPELINE_STAGES.map((stage) => (
              <li key={stage} className={stageClass(stage, job.stage, job.status)}>
                {stage}
              </li>
            ))}
          </ol>
          {job.error && <pre className="err">{job.error}</pre>}
        </section>
      )}

      {videoSrc && (
        <section className="panel player">
          <video controls playsInline poster={poster} src={videoSrc} />
          <p>
            <a href={videoSrc} download>
              Download MP4 1080×1920
            </a>
            {job?.artifacts?.motion_mode ? (
              <span className="meta"> · motion {job.artifacts.motion_mode}</span>
            ) : null}
          </p>
        </section>
      )}

      {job?.structure && (
        <section className="panel beats">
          <h2>Beats</h2>
          {(["hook", "conflict", "rising_action", "twist", "ending"] as const).map((key) => (
            <p key={key}>
              <strong>{key.replaceAll("_", " ")}</strong> {job.structure?.[key]}
            </p>
          ))}
        </section>
      )}

      {stills.length > 0 && (
        <section className="board">
          {stills.map((scene) => (
            <article key={scene.still_id} className="card">
              {scene.src ? <img src={scene.src} alt={scene.still_id} /> : <div className="ph" />}
              <div>
                <p className="meta">
                  {scene.still_id} · {scene.duration_sec}s · {scene.location}
                  {scene.location_id ? ` · ${scene.location_id}` : ""}
                </p>
                <p>{scene.dialogue_or_vo}</p>
                <p className="meta">
                  {scene.shots.map((s) => `${s.camera}/${s.motion}`).join(" → ")}
                </p>
              </div>
            </article>
          ))}
        </section>
      )}

      {message && <p className="err">{message}</p>}
    </div>
  );
}

function stageClass(stage: Stage, current: string, status: string): string {
  const now = PIPELINE_STAGES.indexOf(current as Stage);
  const i = PIPELINE_STAGES.indexOf(stage);
  if (status === "done") return "done";
  if (status === "failed" && stage === current) return "fail";
  if (i < now) return "done";
  if (i === now) return "now";
  return "";
}
