import { FormEvent, useEffect, useMemo, useState } from "react";
import { createJob, dataFileUrl, readJob } from "./api";
import "./App.css";
import { PIPELINE_STAGES, type Job, type Stage } from "./types";

const SAMPLE = `I found his phone on the counter at 2:17 a.m. He said he was sleeping. The lock screen was a photo of us. The messages were not.

Her name was Mara. She asked if I would be home this weekend. He typed, Don't worry. She never checks.`;

export default function App() {
  const [text, setText] = useState(SAMPLE);
  const [mode, setMode] = useState<"script" | "idea">("script");
  const [genre, setGenre] = useState("confession");
  const [language, setLanguage] = useState("en");
  const [seconds, setSeconds] = useState(60);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

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

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    setJob(null);
    try {
      const data = await createJob({
        mode,
        text,
        target_seconds: seconds,
        genre,
        language,
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

  const mp4 = job?.status === "done" ? `/jobs/${jobId}/download` : null;

  return (
    <div className="shell">
      <header className="mast">
        <p className="kicker">Story Video Engine</p>
        <h1>omaishort</h1>
        <p className="lede">
          Paste a confession, not a prompt. One still per scene. Camera moves do the rest.
        </p>
      </header>

      <form className="panel" onSubmit={onSubmit}>
        <div className="row">
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
              <option>confession</option>
              <option>cheating</option>
              <option>revenge</option>
              <option>twist</option>
              <option>family</option>
              <option>drama</option>
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
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={10} />
        <div className="actions">
          <button type="submit" disabled={busy || text.trim().length < 8}>
            {busy ? "Rendering…" : "Make 60s short"}
          </button>
          {jobId && <span className="jobid">job {jobId}</span>}
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

      {mp4 && (
        <section className="panel">
          <video controls src={mp4} />
          <p>
            <a href={mp4} download>
              Download MP4 1080×1920
            </a>
          </p>
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
