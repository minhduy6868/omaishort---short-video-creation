import { useEffect, useMemo, useState } from "react";
import {
  aiRewriteJobStructure,
  dataFileUrl,
  fillJobStills,
  patchJobBible,
  patchJobMeta,
  patchJobScene,
  patchJobStructure,
  pauseJob,
  readJob,
  readVoices,
  regenerateSceneStill,
  rerenderJob,
  resumeJob,
  uploadSceneStill,
  type VoiceOption,
} from "../api";
import {
  PageHeader,
  PhonePreview,
  ProgressBar,
  SceneStrip,
  StageRail,
  StatusPill,
  progressCopy,
  progressFromJob,
  stageLabel,
  toneForStatus,
  type SceneWithSrc,
} from "../components";
import type { CharacterBibleData, Job, ScenePreview, StoryStructureData } from "../types";

const BEATS = ["hook", "conflict", "rising_action", "twist", "ending"] as const;
type BeatKey = (typeof BEATS)[number];

const BEAT_LABELS: Record<string, Record<BeatKey, { title: string; subtitle: string }>> = {
  drama: {
    hook: { title: "1. Mở màn kịch tính (Hook)", subtitle: "Khoảnh khắc gây sốc giữ chân người xem ngay 3 giây đầu" },
    conflict: { title: "2. Xung đột nổ ra", subtitle: "Mâu thuẫn trực diện giữa các nhân vật" },
    rising_action: { title: "3. Cao trào leo thang", subtitle: "Sự việc đẩy lên đỉnh điểm căng thẳng" },
    twist: { title: "4. Cú lật bất ngờ (Twist)", subtitle: "Sự thật phơi bày hoặc tình huống đảo chiều" },
    ending: { title: "5. Kết cục (Ending)", subtitle: "Hệ quả cuối cùng để lại dư âm" },
  },
  news: {
    hook: { title: "1. Tiêu điểm mở đầu", subtitle: "Sự kiện chính, nhân vật, địa điểm và con số nổi bật" },
    conflict: { title: "2. Nút thắt & Nguyên nhân", subtitle: "Vấn đề hoặc tranh cãi khởi phát sự việc" },
    rising_action: { title: "3. Toàn cảnh diễn biến", subtitle: "Chuỗi sự việc diễn ra theo trình tự thời gian" },
    twist: { title: "4. Chi tiết bước ngoặt", subtitle: "Tình tiết quyết định làm thay đổi cục diện" },
    ending: { title: "5. Kết cục & Hiện trạng", subtitle: "Kết quả thực tế hoặc diễn biến mới nhất hiện nay" },
  },
  knowledge: {
    hook: { title: "1. Mở đầu gây tò mò (Hook & Nghịch lý)", subtitle: "Câu hỏi đắt giá, con số bất ngờ hoặc tình huống đời thực" },
    conflict: { title: "2. Vấn đề cốt lõi (Tác động & Hệ lụy)", subtitle: "Tại sao điều này quan trọng và ảnh hưởng trực tiếp tới người xem?" },
    rising_action: { title: "3. Giải mã & Diễn biến (Câu chuyện & Cơ chế)", subtitle: "Dẫn dắt từng bước bằng câu chuyện cụ thể, ví dụ đời thường" },
    twist: { title: "4. Góc khuất bất ngờ (Phản trực giác)", subtitle: "Chi tiết đắt giá ít người biết hoặc lầm tưởng phổ biến của số đông" },
    ending: { title: "5. Đúc kết & Ứng dụng (Giá trị đọng lại)", subtitle: "Bài học cốt lõi sắc bén để người xem nhớ và áp dụng ngay" },
  },
};

const CAMERAS = ["wide", "medium", "close_up"] as const;
const MOTIONS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "hold"] as const;

function terminal(status?: string): boolean {
  return status === "done" || status === "failed" || status === "paused";
}

export function JobPage({ id }: { id: string }) {
  const [job, setJob] = useState<Job | null>(null);
  const [missing, setMissing] = useState(false);
  const [lastPoll, setLastPoll] = useState<Date | null>(null);
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [stillVersion, setStillVersion] = useState<number>(Date.now());

  // Editor states
  const [editingBeats, setEditingBeats] = useState(false);
  const [beatsForm, setBeatsForm] = useState<StoryStructureData>({
    hook: "",
    conflict: "",
    rising_action: "",
    twist: "",
    ending: "",
  });
  const [aiInstruction, setAiInstruction] = useState("");
  const [beatBusy, setBeatBusy] = useState<string | null>(null);

  const [editingMeta, setEditingMeta] = useState(false);
  const [metaTitle, setMetaTitle] = useState("");
  const [metaVoice, setMetaVoice] = useState("");
  const [metaSeconds, setMetaSeconds] = useState(90);
  const [metaBgm, setMetaBgm] = useState(true);
  const [metaLogo, setMetaLogo] = useState(false);

  const [selectedSceneIdx, setSelectedSceneIdx] = useState<number | null>(null);
  const [sceneForm, setSceneForm] = useState<{
    dialogue_or_vo: string;
    action: string;
    image_prompt: string;
    location: string;
    duration_sec: number;
    camera: string;
    motion: string;
  } | null>(null);
  const [sceneBusy, setSceneBusy] = useState(false);

  const [editingBible, setEditingBible] = useState(false);
  const [bibleForm, setBibleForm] = useState<CharacterBibleData | null>(null);

  const [editorMessage, setEditorMessage] = useState<string | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [rerenderBusy, setRerenderBusy] = useState(false);

  useEffect(() => {
    void readVoices().then(setVoices);
  }, []);

  useEffect(() => {
    let stop = false;
    let seen = false;
    let timer = 0;
    const tick = async () => {
      if (document.hidden) return;
      try {
        const data = await readJob(id);
        if (stop) return;
        seen = true;
        setJob(data);
        setMissing(false);
        setLastPoll(new Date());
        if (data.status === "done") {
          setStillVersion(Date.now());
        }
        if (terminal(data.status) && timer) {
          window.clearInterval(timer);
          timer = 0;
        } else if (!terminal(data.status) && !timer) {
          timer = window.setInterval(() => void tick(), 2000);
        }
      } catch {
        if (stop || seen) return;
        setMissing(true);
        if (timer) window.clearInterval(timer);
      }
    };
    void tick();
    timer = window.setInterval(() => void tick(), 2000);
    const onVisible = () => {
      if (!document.hidden) void tick();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      stop = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [id, job?.status]);

  // Sync forms when job first arrives or when not actively editing
  useEffect(() => {
    if (!job) return;
    if (!editingBeats && job.structure) {
      setBeatsForm({
        hook: job.structure.hook || "",
        conflict: job.structure.conflict || "",
        rising_action: job.structure.rising_action || "",
        twist: job.structure.twist || "",
        ending: job.structure.ending || "",
        hook_sec: job.structure.hook_sec,
        conflict_sec: job.structure.conflict_sec,
        rising_sec: job.structure.rising_sec,
        twist_sec: job.structure.twist_sec,
        ending_sec: job.structure.ending_sec,
      });
    }
    if (!editingMeta) {
      setMetaTitle(job.storyboard?.title || "");
      setMetaVoice(typeof job.input?.voice_id === "string" ? job.input.voice_id : "vi-female");
      setMetaSeconds(typeof job.input?.target_seconds === "number" ? job.input.target_seconds : 90);
      const mix = job.input?.mix as { bgm_enabled?: boolean; logo_enabled?: boolean } | undefined;
      setMetaBgm(mix?.bgm_enabled ?? true);
      setMetaLogo(mix?.logo_enabled ?? false);
    }
    if (!editingBible && job.bible) {
      setBibleForm(job.bible);
    }
  }, [job, editingBeats, editingMeta, editingBible]);

  const stills: SceneWithSrc[] = useMemo(() => {
    return (job?.storyboard?.scenes ?? []).map((scene) => {
      const base = dataFileUrl(job?.artifacts?.[scene.still_id]);
      return {
        ...scene,
        src: base ? `${base}?v=${stillVersion}` : null,
      };
    });
  }, [job, stillVersion]);

  function openSceneEditor(scene: ScenePreview) {
    setSelectedSceneIdx(scene.index);
    setSceneForm({
      dialogue_or_vo: scene.dialogue_or_vo || "",
      action: scene.action || "",
      image_prompt: scene.image_prompt || "",
      location: scene.location || "",
      duration_sec: scene.duration_sec || 6,
      camera: scene.shots?.[0]?.camera || "medium",
      motion: scene.shots?.[0]?.motion || "zoom_in",
    });
  }

  async function handleSaveMeta() {
    setEditorError(null);
    setEditorMessage(null);
    try {
      const updated = await patchJobMeta(id, {
        title: metaTitle,
        voice_id: metaVoice,
        target_seconds: metaSeconds,
        bgm_enabled: metaBgm,
        logo_enabled: metaLogo,
      });
      setJob(updated);
      setEditingMeta(false);
      setEditorMessage("Đã lưu cài đặt dự án. Bấm Render lại MP4 nếu muốn cập nhật giọng đọc hoặc nhạc nền.");
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không lưu được cài đặt");
    }
  }

  async function handleSaveBeats(syncScenes = true): Promise<boolean> {
    setBeatBusy("save");
    setEditorError(null);
    setEditorMessage(null);
    try {
      const updated = await patchJobStructure(id, {
        ...beatsForm,
        sync_scenes: syncScenes,
      });
      setJob(updated);
      setEditingBeats(false);
      if (syncScenes) {
        setSelectedSceneIdx(null);
        setSceneForm(null);
      }
      setEditorMessage("Đã lưu cấu trúc 5 phần và đồng bộ sang lời thoại các cảnh.");
      return true;
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không lưu được cấu trúc");
      return false;
    } finally {
      setBeatBusy(null);
    }
  }

  async function handleAiRewrite(beatKey: string) {
    setBeatBusy(beatKey);
    setEditorError(null);
    setEditorMessage(null);
    try {
      const updated = await aiRewriteJobStructure(id, {
        beat: beatKey,
        instruction: aiInstruction,
        sync_scenes: true,
      });
      setJob(updated);
      if (updated.structure) {
        setBeatsForm(updated.structure);
      }
      setSelectedSceneIdx(null);
      setSceneForm(null);
      setEditorMessage(
        beatKey === "all"
          ? `Đã viết lại toàn bộ 5 phần (${updated.rewrite_provider || "AI"}).`
          : `Đã viết lại phần ${beatKey} (${updated.rewrite_provider || "AI"}).`,
      );
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không viết lại được bằng AI");
    } finally {
      setBeatBusy(null);
    }
  }

  async function handleSaveScene() {
    if (selectedSceneIdx === null || !sceneForm) return;
    setSceneBusy(true);
    setEditorError(null);
    setEditorMessage(null);
    try {
      const updated = await patchJobScene(id, selectedSceneIdx, sceneForm);
      setJob(updated);
      setEditorMessage(`Đã lưu chỉnh sửa Cảnh #${selectedSceneIdx}.`);
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không lưu được cảnh");
    } finally {
      setSceneBusy(false);
    }
  }

  async function handleRegenerateStill(
    sceneIndex: number,
    customPrompt?: string,
    source: "auto" | "grok" | "chatgpt" | "search" = "auto",
  ) {
    setSceneBusy(true);
    setEditorError(null);
    const sourceLabel =
      source === "grok"
        ? "Grok Search / Imagine"
        : source === "chatgpt"
          ? "ChatGPT Search / Image"
          : source === "search"
            ? "Web / Wikipedia"
            : "AI";
    setEditorMessage(`Đang lấy ảnh từ ${sourceLabel} cho Cảnh #${sceneIndex}…`);
    try {
      const updated = await regenerateSceneStill(id, sceneIndex, customPrompt, source);
      setJob(updated);
      setStillVersion(Date.now());
      setEditorMessage(
        `Đã cập nhật ảnh mới cho Cảnh #${sceneIndex} (${updated.still_provider || sourceLabel}).`,
      );
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không tạo lại được ảnh cảnh");
    } finally {
      setSceneBusy(false);
    }
  }

  async function handleFillStills(source: "grok" | "chatgpt" | "search" | "auto", forceAll = false) {
    setSceneBusy(true);
    setEditorError(null);
    const label = source === "grok" ? "Grok" : source === "chatgpt" ? "ChatGPT" : "Web/AI";
    setEditorMessage(
      forceAll
        ? `Đang tìm & cập nhật lại toàn bộ ảnh các cảnh từ ${label}…`
        : `Đang bù các ảnh còn thiếu / ảnh tạm từ ${label}…`,
    );
    try {
      const updated = await fillJobStills(id, source, forceAll);
      setJob(updated);
      setStillVersion(Date.now());
      const count = updated.updated_scenes?.length ?? 0;
      setEditorMessage(
        count > 0
          ? `Đã cập nhật ${count} cảnh từ nguồn ${label}.`
          : `Tất cả các cảnh đã có ảnh đầy đủ (0 cảnh thiếu). Bấm 'Đổi tất cả ảnh' nếu muốn thay mới toàn bộ.`,
      );
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không bù được ảnh các cảnh");
    } finally {
      setSceneBusy(false);
    }
  }

  async function handlePause() {
    setRerenderBusy(true);
    setEditorError(null);
    try {
      const updated = await pauseJob(id);
      setJob(updated);
      setEditorMessage(
        "Đã tạm dừng tiến trình. Bạn có thể sửa cấu trúc 5 phần, lời thoại, hoặc đổi ảnh từng cảnh (từ Grok / ChatGPT / máy tính), sau đó bấm 'Tiếp tục xuất MP4'.",
      );
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không tạm dừng được job");
    } finally {
      setRerenderBusy(false);
    }
  }

  async function handleUploadStill(sceneIndex: number, file: File) {
    setSceneBusy(true);
    setEditorError(null);
    setEditorMessage(`Đang tải ảnh lên cho Cảnh #${sceneIndex}…`);
    try {
      const updated = await uploadSceneStill(id, sceneIndex, file);
      setJob(updated);
      setStillVersion(Date.now());
      setEditorMessage(`Đã thay ảnh mới cho Cảnh #${sceneIndex}.`);
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không tải được ảnh lên");
    } finally {
      setSceneBusy(false);
    }
  }

  async function handleSaveBible() {
    if (!bibleForm) return;
    setEditorError(null);
    setEditorMessage(null);
    try {
      const updated = await patchJobBible(id, bibleForm);
      setJob(updated);
      setEditingBible(false);
      setEditorMessage("Đã lưu Hồ sơ Nhân vật & Bối cảnh (Character Bible).");
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không lưu được Character Bible");
    }
  }

  async function handleRerender(regenerateStills = false) {
    setRerenderBusy(true);
    setEditorError(null);
    setEditorMessage(
      regenerateStills
        ? "Đang tạo lại toàn bộ ảnh Stills, giọng đọc TTS, phụ đề và render lại MP4…"
        : "Đang tổng hợp lại giọng đọc TTS, căn lại phụ đề và render lại MP4…",
    );
    try {
      const updated =
        job?.status === "paused"
          ? await resumeJob(id, regenerateStills)
          : await rerenderJob(id, regenerateStills);
      setJob(updated);
    } catch (err) {
      setEditorError(err instanceof Error ? err.message : "Không chạy lại được render");
    } finally {
      setRerenderBusy(false);
    }
  }

  const videoSrc =
    job?.status === "done"
      ? `${dataFileUrl(job.artifacts?.mp4) ?? `/jobs/${id}/download`}?v=${stillVersion}`
      : null;
  const poster = stills.find((scene) => scene.src)?.src ?? undefined;
  const rawKind = job?.storyboard?.kind || (typeof job?.input?.kind === "string" ? job.input.kind : "drama");
  const kind = rawKind === "brief" ? "news" : rawKind;
  const beatLabels = BEAT_LABELS[kind] || BEAT_LABELS.knowledge;
  const motion = job?.artifacts?.motion_mode || "pending";
  const progress = progressFromJob(job?.progress, job?.status, job?.stage);
  const progressText = progressCopy(job?.progress, job?.stage);

  return (
    <section className="page-stack watch-page">
      <PageHeader
        kicker={job?.storyboard?.kind || "short"}
        title={job?.storyboard?.title || id}
        lede="Theo dõi tiến trình, chỉnh sửa trực tiếp từng phần kịch bản, lời thoại, góc máy, ảnh từng cảnh và render lại MP4."
        actions={
          <div className="hub-actions">
            {job?.status === "running" || job?.status === "queued" ? (
              <button
                type="button"
                disabled={rerenderBusy}
                onClick={() => void handlePause()}
              >
                ⏸ Tạm dừng để chỉnh sửa (Lời / Ảnh / Cảnh)
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className={job?.status === "paused" ? "" : "ghost"}
                  disabled={rerenderBusy}
                  onClick={() => void handleRerender(false)}
                >
                  {job?.status === "paused"
                    ? "▶ Tiếp tục xuất MP4 (Giữ ảnh)"
                    : "Render lại MP4 (Giữ ảnh)"}
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={rerenderBusy}
                  onClick={() => void handleRerender(true)}
                >
                  Tạo lại Ảnh & MP4
                </button>
              </>
            )}
            {videoSrc ? (
              <a className="button" href={videoSrc} download>
                Tải MP4
              </a>
            ) : null}
          </div>
        }
        meta={
          job ? (
            <div className="provider-row">
              <StatusPill label={job.status} tone={toneForStatus(job.status)} />
              <StatusPill label={stageLabel(job.stage)} tone={job.status === "failed" ? "failed" : "accent"} />
              <StatusPill label={`motion ${motion}`} tone={motion === "pending" ? "idle" : "done"} />
              {lastPoll ? (
                <span>
                  Cập nhật{" "}
                  {lastPoll.toLocaleTimeString("vi-VN", {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  })}
                </span>
              ) : null}
            </div>
          ) : null
        }
      />

      {editorMessage ? <p className="meta">{editorMessage}</p> : null}
      {editorError ? <p className="err">{editorError}</p> : null}

      <div className="watch-layout">
        <aside className="panel watch-inspector">
          <div className="section-head compact">
            <div>
              <p className="kicker">Stages</p>
              <h2>Pipeline</h2>
            </div>
            <button type="button" className="ghost" onClick={() => setEditingMeta((v) => !v)}>
              {editingMeta ? "Đóng cài đặt" : "Sửa cài đặt"}
            </button>
          </div>
          {job ? (
            <StageRail current={job.stage} status={job.status} />
          ) : (
            <p className="meta">{missing ? "Không thấy job." : "Đang tải…"}</p>
          )}
          {job ? <ProgressBar value={progress} label={progressText} /> : null}
          {job?.error ? (
            <div className="error-panel">
              <strong>Lỗi render</strong>
              <pre className="err">{job.error}</pre>
            </div>
          ) : null}

          {editingMeta ? (
            <div className="meta-editor" style={{ marginTop: "12px", display: "grid", gap: "10px" }}>
              <label>
                Tiêu đề video
                <input value={metaTitle} onChange={(e) => setMetaTitle(e.target.value)} />
              </label>
              <label>
                Giọng đọc
                <select value={metaVoice} onChange={(e) => setMetaVoice(e.target.value)}>
                  {voices.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label} ({v.language})
                    </option>
                  ))}
                  {!voices.some((v) => v.id === metaVoice) ? (
                    <option value={metaVoice}>{metaVoice}</option>
                  ) : null}
                </select>
              </label>
              <label>
                Thời lượng mục tiêu (giây)
                <input
                  type="number"
                  min={15}
                  max={600}
                  value={metaSeconds}
                  onChange={(e) => setMetaSeconds(Number(e.target.value))}
                />
              </label>
              <label className="check">
                <input type="checkbox" checked={metaBgm} onChange={(e) => setMetaBgm(e.target.checked)} />
                Bật nhạc nền
              </label>
              <label className="check">
                <input type="checkbox" checked={metaLogo} onChange={(e) => setMetaLogo(e.target.checked)} />
                Hiển thị Logo
              </label>
              <button type="button" onClick={() => void handleSaveMeta()}>
                Lưu cài đặt dự án
              </button>
            </div>
          ) : null}

          <div className="artifact-list">
            <p className="card-title">Artifacts</p>
            <span>MP4: {videoSrc ? "ready" : "pending"}</span>
            <span>
              Stills: {stills.filter((scene) => scene.src).length}/{stills.length}
            </span>
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
                  <p className="kicker">Storytelling Arc</p>
                  <h2>Cấu trúc 5 phần</h2>
                </div>
                <div className="hub-actions">
                  <button
                    type="button"
                    className="ghost"
                    disabled={beatBusy !== null}
                    onClick={() => void handleAiRewrite("all")}
                  >
                    {beatBusy === "all" ? "AI đang viết…" : "AI / ChatGPT viết lại"}
                  </button>
                  <button type="button" className="ghost" onClick={() => setEditingBeats((v) => !v)}>
                    {editingBeats ? "Đóng sửa" : "Sửa từng phần"}
                  </button>
                </div>
              </div>

              {editingBeats ? (
                <div style={{ display: "grid", gap: "10px", marginBottom: "10px" }}>
                  <label>
                    Hướng dẫn cho AI / ChatGPT khi viết lại
                    <input
                      value={aiInstruction}
                      onChange={(e) => setAiInstruction(e.target.value)}
                      placeholder="VD: Mở đầu kịch tính hơn, thêm ví dụ thực tế, câu ngắn gọn…"
                    />
                  </label>
                </div>
              ) : null}

              {BEATS.map((key) => {
                const info = beatLabels[key];
                return (
                  <article key={key} className="beat-card" style={{ display: "grid", gap: "6px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                      <div>
                        <strong>{info.title}</strong>
                        <span className="field-hint" style={{ display: "block", fontSize: "12px" }}>
                          {info.subtitle}
                        </span>
                      </div>
                      {editingBeats ? (
                        <button
                          type="button"
                          className="ghost"
                          disabled={beatBusy !== null}
                          onClick={() => void handleAiRewrite(key)}
                        >
                          {beatBusy === key ? "Đang viết…" : "AI viết lại"}
                        </button>
                      ) : null}
                    </div>
                    {editingBeats ? (
                      <textarea
                        rows={3}
                        value={beatsForm[key] || ""}
                        onChange={(e) =>
                          setBeatsForm((prev) => ({
                            ...prev,
                            [key]: e.target.value,
                          }))
                        }
                      />
                    ) : (
                      <p>{job.structure?.[key]}</p>
                    )}
                  </article>
                );
              })}

              {editingBeats ? (
                <div className="hub-actions" style={{ marginTop: "10px" }}>
                  <button
                    type="button"
                    disabled={beatBusy !== null}
                    onClick={() => void handleSaveBeats(true)}
                  >
                    {beatBusy === "save" ? "Đang lưu…" : "Lưu & Đồng bộ sang Cảnh"}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={beatBusy !== null}
                    onClick={() => {
                      void handleSaveBeats(true).then((ok) => {
                        if (ok) void handleRerender(false);
                      });
                    }}
                  >
                    Lưu & Render lại MP4
                  </button>
                </div>
              ) : null}
            </section>
          ) : null}

          {job?.bible && kind === "drama" ? (
            <section className="panel">
              <div className="section-head compact">
                <div>
                  <p className="kicker">Identity Lock</p>
                  <h2>Nhân vật & Bối cảnh</h2>
                </div>
                <button type="button" className="ghost" onClick={() => setEditingBible((v) => !v)}>
                  {editingBible ? "Đóng" : "Sửa nhân vật"}
                </button>
              </div>
              {editingBible && bibleForm ? (
                <div style={{ display: "grid", gap: "10px" }}>
                  {bibleForm.characters.map((char, idx) => (
                    <div key={char.id} className="beat-card" style={{ display: "grid", gap: "6px" }}>
                      <strong>Nhân vật: {char.id}</strong>
                      <label>
                        Ngoại hình (Appearance)
                        <input
                          value={char.appearance}
                          onChange={(e) => {
                            const next = [...bibleForm.characters];
                            next[idx] = { ...char, appearance: e.target.value };
                            setBibleForm({ ...bibleForm, characters: next });
                          }}
                        />
                      </label>
                      <label>
                        Trang phục (Clothing)
                        <input
                          value={char.clothing}
                          onChange={(e) => {
                            const next = [...bibleForm.characters];
                            next[idx] = { ...char, clothing: e.target.value };
                            setBibleForm({ ...bibleForm, characters: next });
                          }}
                        />
                      </label>
                    </div>
                  ))}
                  <button type="button" onClick={() => void handleSaveBible()}>
                    Lưu hồ sơ nhân vật
                  </button>
                </div>
              ) : (
                <p className="meta">
                  {job.bible.characters.length} nhân vật · {job.bible.locations.length} bối cảnh
                </p>
              )}
            </section>
          ) : null}

          <section className="panel scenes-panel">
            <div className="section-head compact">
              <div>
                <p className="kicker">Scenes</p>
                <h2>Chỉnh sửa từng cảnh ({stills.length})</h2>
              </div>
              <StatusPill label={`${stills.length} scenes`} tone={stills.length ? "accent" : "idle"} />
            </div>
            {stills.length > 0 && job?.status !== "running" && job?.status !== "queued" ? (
              <div className="hub-actions" style={{ marginBottom: "10px", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="ghost"
                  disabled={sceneBusy}
                  onClick={() => void handleFillStills("grok", false)}
                >
                  Bù ảnh thiếu từ Grok
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={sceneBusy}
                  onClick={() => void handleFillStills("chatgpt", false)}
                >
                  Bù ảnh thiếu từ ChatGPT
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={sceneBusy}
                  onClick={() => void handleFillStills("grok", true)}
                >
                  Đổi tất cả ảnh bằng Grok
                </button>
                <button
                  type="button"
                  className="ghost"
                  disabled={sceneBusy}
                  onClick={() => void handleFillStills("chatgpt", true)}
                >
                  Đổi tất cả ảnh bằng ChatGPT
                </button>
              </div>
            ) : null}
            <SceneStrip scenes={stills} />
            {stills.length === 0 ? <p className="meta">Storyboard chưa sẵn sàng.</p> : null}

            {stills.length > 0 ? (
              <div style={{ marginTop: "14px", display: "grid", gap: "10px" }}>
                {stills.map((scene) => {
                  const isEditingThis = selectedSceneIdx === scene.index && sceneForm !== null;
                  const primaryShot = scene.shots?.[0];
                  return (
                    <article key={scene.still_id} className="beat-card" style={{ display: "grid", gap: "8px" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                        <div>
                          <strong>
                            Cảnh #{scene.index} · {scene.duration_sec}s
                          </strong>
                          <span className="meta" style={{ marginLeft: "8px" }}>
                            {primaryShot ? `${primaryShot.camera} · ${primaryShot.motion}` : "medium · zoom_in"}
                          </span>
                        </div>
                        <div className="hub-actions">
                          <button
                            type="button"
                            className="ghost"
                            onClick={() => {
                              if (isEditingThis) {
                                setSelectedSceneIdx(null);
                                setSceneForm(null);
                              } else {
                                openSceneEditor(scene);
                              }
                            }}
                          >
                            {isEditingThis ? "Đóng" : "Sửa cảnh này"}
                          </button>
                          <button
                            type="button"
                            className="ghost"
                            disabled={sceneBusy}
                            onClick={() => void handleRegenerateStill(scene.index, undefined, "grok")}
                          >
                            Ảnh Grok
                          </button>
                          <button
                            type="button"
                            className="ghost"
                            disabled={sceneBusy}
                            onClick={() => void handleRegenerateStill(scene.index, undefined, "chatgpt")}
                          >
                            Ảnh ChatGPT
                          </button>
                          <button
                            type="button"
                            className="ghost"
                            disabled={sceneBusy}
                            onClick={() => void handleRegenerateStill(scene.index, undefined, "auto")}
                          >
                            Đổi ảnh AI
                          </button>
                        </div>
                      </div>

                      {!isEditingThis ? (
                        <p style={{ margin: 0 }}>{scene.dialogue_or_vo}</p>
                      ) : (
                        <div style={{ display: "grid", gap: "8px", marginTop: "4px" }}>
                          <label>
                            Lời thoại / Thuyết minh cảnh #{scene.index}
                            <textarea
                              rows={3}
                              value={sceneForm.dialogue_or_vo}
                              onChange={(e) => setSceneForm({ ...sceneForm, dialogue_or_vo: e.target.value })}
                            />
                          </label>
                          <label>
                            Mô tả hành động / Hình ảnh (Action)
                            <input
                              value={sceneForm.action}
                              onChange={(e) => setSceneForm({ ...sceneForm, action: e.target.value })}
                            />
                          </label>
                          <label>
                            Prompt / Từ khóa tìm ảnh chi tiết (Image Prompt)
                            <textarea
                              rows={2}
                              value={sceneForm.image_prompt}
                              onChange={(e) => setSceneForm({ ...sceneForm, image_prompt: e.target.value })}
                            />
                          </label>
                          <div className="fields two">
                            <label>
                              Bối cảnh (Location)
                              <input
                                value={sceneForm.location}
                                onChange={(e) => setSceneForm({ ...sceneForm, location: e.target.value })}
                              />
                            </label>
                            <label>
                              Thời lượng (giây)
                              <input
                                type="number"
                                step="0.5"
                                min={1}
                                max={120}
                                value={sceneForm.duration_sec}
                                onChange={(e) => setSceneForm({ ...sceneForm, duration_sec: Number(e.target.value) })}
                              />
                            </label>
                            <label>
                              Góc máy (Camera)
                              <select
                                value={sceneForm.camera}
                                onChange={(e) => setSceneForm({ ...sceneForm, camera: e.target.value })}
                              >
                                {CAMERAS.map((c) => (
                                  <option key={c} value={c}>
                                    {c}
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              Chuyển động (Motion)
                              <select
                                value={sceneForm.motion}
                                onChange={(e) => setSceneForm({ ...sceneForm, motion: e.target.value })}
                              >
                                {MOTIONS.map((m) => (
                                  <option key={m} value={m}>
                                    {m}
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>
                          <label className="upload-box">
                            Tải ảnh riêng từ máy cho Cảnh #{scene.index}
                            <input
                              type="file"
                              accept="image/png,image/jpeg,image/webp"
                              disabled={sceneBusy}
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                e.target.value = "";
                                if (file) void handleUploadStill(scene.index, file);
                              }}
                            />
                          </label>
                          <div className="hub-actions" style={{ flexWrap: "wrap" }}>
                            <button type="button" disabled={sceneBusy} onClick={() => void handleSaveScene()}>
                              {sceneBusy ? "Đang lưu…" : "Lưu cảnh này"}
                            </button>
                            <button
                              type="button"
                              className="ghost"
                              disabled={sceneBusy}
                              onClick={() =>
                                void handleRegenerateStill(scene.index, sceneForm.image_prompt || sceneForm.action, "grok")
                              }
                            >
                              Lấy ảnh Grok theo Prompt
                            </button>
                            <button
                              type="button"
                              className="ghost"
                              disabled={sceneBusy}
                              onClick={() =>
                                void handleRegenerateStill(scene.index, sceneForm.image_prompt || sceneForm.action, "chatgpt")
                              }
                            >
                              Lấy ảnh ChatGPT theo Prompt
                            </button>
                            <button
                              type="button"
                              className="ghost"
                              disabled={sceneBusy}
                              onClick={() =>
                                void handleRegenerateStill(scene.index, sceneForm.image_prompt || sceneForm.action, "search")
                              }
                            >
                              Tìm ảnh Web/Wiki
                            </button>
                            <button
                              type="button"
                              className="ghost"
                              disabled={sceneBusy}
                              onClick={() =>
                                void handleRegenerateStill(scene.index, sceneForm.image_prompt || sceneForm.action, "auto")
                              }
                            >
                              Tạo ảnh AI
                            </button>
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : null}
          </section>
        </aside>
      </div>
    </section>
  );
}
