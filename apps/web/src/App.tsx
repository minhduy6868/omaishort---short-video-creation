import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createJob,
  dataFileUrl,
  listAttachments,
  login,
  logout,
  readJob,
  readMe,
  readVoices,
  register,
  uploadAttachment,
  type AttachmentRow,
  type AuthUser,
  type VoiceOption,
} from "./api";
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
const FALLBACK_VOICES: VoiceOption[] = [
  { id: "vi-female", language: "vi", label: "Nữ — Việt Nam" },
  { id: "vi-male", language: "vi", label: "Nam — Việt Nam" },
  { id: "en-female-us", language: "en", label: "Female — US" },
  { id: "en-male-us", language: "en", label: "Male — US" },
  { id: "en-female-uk", language: "en", label: "Female — UK" },
  { id: "en-male-uk", language: "en", label: "Male — UK" },
  { id: "en-female-au", language: "en", label: "Female — Australia" },
  { id: "en-male-au", language: "en", label: "Male — Australia" },
];

function defaultVoice(language: string): string {
  return language === "vi" ? "vi-female" : "en-female-us";
}

function isEditorial(kind: VideoKind): boolean {
  return kind === "news" || kind === "knowledge";
}

export default function App() {
  const [kind, setKind] = useState<VideoKind>("drama");
  const [text, setText] = useState(DRAMA_SAMPLE);
  const [mode, setMode] = useState<"script" | "idea">("script");
  const [genre, setGenre] = useState("confession");
  const [language, setLanguage] = useState("en");
  const [voiceId, setVoiceId] = useState(defaultVoice("en"));
  const [seconds, setSeconds] = useState(60);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [logoEnabled, setLogoEnabled] = useState(false);
  const [scriptBrief, setScriptBrief] = useState("");
  const [voices, setVoices] = useState<VoiceOption[]>(FALLBACK_VOICES);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [attachKind, setAttachKind] = useState("face");
  const [attachBind, setAttachBind] = useState("");
  const [library, setLibrary] = useState<AttachmentRow[]>([]);
  const [picked, setPicked] = useState<{ id: string; kind: string; filename: string; bind: string }[]>([]);

  useEffect(() => {
    let stop = false;
    void readMe().then((me) => {
      if (!stop) {
        setUser(me);
        setAuthReady(true);
      }
    });
    return () => {
      stop = true;
    };
  }, []);

  useEffect(() => {
    if (!user) {
      setLibrary([]);
      return;
    }
    let stop = false;
    void listAttachments().then((rows) => {
      if (!stop) setLibrary(rows);
    });
    return () => {
      stop = true;
    };
  }, [user]);

  useEffect(() => {
    if (isEditorial(kind) && (attachKind === "face" || attachKind === "location" || attachKind === "prop")) {
      setAttachKind("editorial");
    }
    if (!isEditorial(kind) && attachKind === "editorial") {
      setAttachKind("face");
    }
  }, [kind, attachKind]);

  useEffect(() => {
    let stop = false;
    void readVoices().then((rows) => {
      if (!stop && rows.length) setVoices(rows);
    });
    return () => {
      stop = true;
    };
  }, []);

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
      setVoiceId(defaultVoice("en"));
      setSeconds(60);
    } else {
      setGenre(next === "knowledge" ? "knowledge" : "news");
      setLanguage("vi");
      setVoiceId(defaultVoice("vi"));
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
        voice_id: voiceId,
        source_url: isEditorial(kind) ? sourceUrl.trim() || null : null,
        script_brief: scriptBrief.trim() || null,
        attachments: picked.map((item) => ({ id: item.id, bind: item.bind || null })),
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
        ? "Paste a topic (thuyết minh về lạm phát…), one claim, or a GitHub URL. Optional script notes steer ChatGPT. The engine writes the explainer — it does not echo the request or dump a README."
        : "Paste a confession. One still per scene, bible-locked faces, beat cameras. I2V only when keyed — otherwise Ken Burns, never faked as video.";

  return (
    <div className="shell">
      <header className="mast">
        <p className="kicker">Story Video Engine</p>
        <h1>omaishort</h1>
        <p className="lede">
          {lede}
        </p>
        {authReady && user ? (
          <div className="auth-bar">
            <span className="meta">
              {user.email} · {user.role}
            </span>
            <button
              type="button"
              className="ghost"
              onClick={() => {
                void logout().then(() => {
                  setUser(null);
                  setPicked([]);
                });
              }}
            >
              Log out
            </button>
          </div>
        ) : null}
      </header>

      {authReady && !user ? (
        <form
          className="panel auth-panel"
          onSubmit={(event) => {
            event.preventDefault();
            setMessage(null);
            const run = authMode === "register" ? register : login;
            void run(authEmail, authPassword)
              .then((me) => {
                setUser(me);
                setAuthPassword("");
              })
              .catch((err) => setMessage(err instanceof Error ? err.message : "Auth failed"));
          }}
        >
          <h2>{authMode === "register" ? "Create account" : "Sign in"}</h2>
          <p className="meta">Studio jobs and files belong to your account. CLI dry-runs stay local.</p>
          <div className="row auth-row">
            <label>
              Email
              <input
                type="email"
                autoComplete="username"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete={authMode === "register" ? "new-password" : "current-password"}
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                minLength={8}
                required
              />
            </label>
          </div>
          <div className="actions">
            <button type="submit">{authMode === "register" ? "Register" : "Sign in"}</button>
            <button
              type="button"
              className="ghost"
              onClick={() => setAuthMode(authMode === "register" ? "login" : "register")}
            >
              {authMode === "register" ? "Have an account? Sign in" : "Need an account? Register"}
            </button>
          </div>
        </form>
      ) : null}

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
            <select
              value={language}
              onChange={(e) => {
                const next = e.target.value;
                setLanguage(next);
                setVoiceId(defaultVoice(next));
              }}
            >
              <option value="en">en</option>
              <option value="vi">vi</option>
            </select>
          </label>
          <label>
            Voice
            <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
              {voices.filter((voice) => voice.language === language).map((voice) => (
                <option key={voice.id} value={voice.id}>
                  {voice.label}
                </option>
              ))}
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
        <label className="script-brief">
          Extra script notes
          <textarea
            value={scriptBrief}
            onChange={(e) => setScriptBrief(e.target.value)}
            rows={3}
            maxLength={2000}
            placeholder={
              kind === "knowledge"
                ? "Optional. Example: giọng tài liệu, nhấn trận Khâm Ung Liêm, đừng kể gia phả"
                : kind === "news"
                  ? "Optional. Example: giọng lạnh, giữ số liệu, đừng đạo đức giảng"
                  : "Optional. Example: colder tone, stay on the kitchen, no flashback"
            }
          />
        </label>
        {user ? (
          <div className="attach">
            <p className="meta">Attachments — face / location / prop for drama; editorial photos for news; logo overlay; script is provenance only.</p>
            <div className="row auth-row">
              <label>
                Kind
                <select value={attachKind} onChange={(e) => setAttachKind(e.target.value)}>
                  {(isEditorial(kind)
                    ? ["editorial", "logo", "script"]
                    : ["face", "location", "prop", "logo", "script"]
                  ).map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Bind id
                <input
                  value={attachBind}
                  onChange={(e) => setAttachBind(e.target.value)}
                  placeholder={attachKind === "face" ? "wife" : "optional"}
                />
              </label>
              <label>
                File
                <input
                  type="file"
                  accept={attachKind === "script" ? ".txt,.md,text/plain" : "image/png,image/jpeg,image/webp"}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (!file) return;
                    void uploadAttachment(attachKind, file)
                      .then((row) => {
                        setLibrary((prev) => [row, ...prev.filter((item) => item.id !== row.id)]);
                        const bind = attachBind.trim() || file.name.replace(/\.[^.]+$/, "");
                        setPicked((prev) =>
                          prev.some((item) => item.id === row.id)
                            ? prev
                            : [...prev, { id: row.id, kind: row.kind, filename: row.filename, bind }],
                        );
                      })
                      .catch((err) => setMessage(err instanceof Error ? err.message : "Upload failed"));
                  }}
                />
              </label>
            </div>
            {picked.length > 0 ? (
              <ul className="chips">
                {picked.map((item) => (
                  <li key={item.id}>
                    {item.kind}:{item.filename}
                    {item.bind ? ` → ${item.bind}` : ""}
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => setPicked((prev) => prev.filter((row) => row.id !== item.id))}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            {library.length > 0 && picked.length < library.length ? (
              <p className="meta">
                Library:{" "}
                {library
                  .filter((row) => !picked.some((item) => item.id === row.id))
                  .slice(0, 6)
                  .map((row) => (
                    <button
                      key={row.id}
                      type="button"
                      className="ghost"
                      onClick={() =>
                        setPicked((prev) => [
                          ...prev,
                          { id: row.id, kind: row.kind, filename: row.filename, bind: attachBind.trim() },
                        ])
                      }
                    >
                      {row.kind}:{row.filename}
                    </button>
                  ))}
              </p>
            ) : null}
          </div>
        ) : (
          <p className="meta">Sign in to create a job and attach files.</p>
        )}
        <div className="actions">
          <button type="submit" disabled={!user || busy || (text.trim().length < 8 && sourceUrl.trim().length < 12)}>
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
