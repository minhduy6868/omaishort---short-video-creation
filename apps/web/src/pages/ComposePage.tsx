import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  boostViralScript,
  createJob,
  deleteTemplate,
  draftScript,
  listAttachments,
  listTemplates,
  readProviders,
  readScriptPresets,
  readVoices,
  reverseEngineerVideo,
  rewriteScript,
  scoreViralScript,
  uploadAttachment,
  type AttachmentRow,
  type ProviderStatus,
  type VoiceOption,
} from "../api";
import { PageHeader, StatusPill } from "../components";
import { useNav } from "../nav";
import { useSession } from "../session";
import type {
  CaptionPreset,
  DramaShape,
  StoryStructureData,
  VideoBlueprint,
  VideoKind,
  ViralPreset,
  ViralScoreResult,
} from "../types";

const BEAT_META: {
  key: keyof Pick<StoryStructureData, "hook" | "conflict" | "rising_action" | "twist" | "ending">;
  label: string;
  hint: string;
}[] = [
  {
    key: "hook",
    label: "1. Mở đầu gây tò mò (Hook & Nghịch lý)",
    hint: "Con số gây sốc, câu hỏi đắt giá hoặc tình huống thực tế giữ chân người xem 3 giây đầu.",
  },
  {
    key: "conflict",
    label: "2. Vấn đề cốt lõi (Tác động & Hệ lụy)",
    hint: "Tại sao điều này quan trọng ngay lúc này? Nút thắt hoặc tác động thực tế tới người xem.",
  },
  {
    key: "rising_action",
    label: "3. Giải mã & Diễn biến (Câu chuyện & Cơ chế)",
    hint: "Dẫn dắt từng bước bằng câu chuyện cụ thể, mốc sự kiện hoặc ví dụ đời thường.",
  },
  {
    key: "twist",
    label: "4. Góc khuất bất ngờ (Phản trực giác)",
    hint: "Sự thật ít người biết hoặc cú bẻ lái lật ngược lầm tưởng của số đông.",
  },
  {
    key: "ending",
    label: "5. Đúc kết & Ứng dụng (Giá trị đọng lại)",
    hint: "Bài học cốt lõi hoặc kết luận sắc bén để người xem nhớ mãi sau khi xem xong.",
  },
];

const DRAMA_SAMPLE = `I found his phone on the counter at 2:17 a.m. He said he was sleeping. The lock screen was a photo of us. The messages were not.

Her name was Mara. She asked if I would be home this weekend. He typed, Don't worry. She never checks.`;

const DRAMA_VIRAL_SAMPLE = `A hotel cleaner in a faded uniform. The arrogant guest at the front desk. She asks for a room. He laughs at her in the lobby, in front of the other staff.`;

const NEWS_SAMPLE = `Tiêu đề: Trái đắng của người phụ nữ lấy chồng kém 37 tuổi.

Sharon, 61 tuổi ở Yorkshire, kết hôn với sinh viên Nigeria kém mình 37 tuổi sau khi quen trên ứng dụng hẹn hò.

Gia đình phản đối. Anh xin thị thực, hứa xây tương lai ở Anh.

Sau đăng ký kết hôn, mâu thuẫn về tiền bạc và chỗ ở bắt đầu.

Anh bỏ đi Nigeria. Cô mất nhà, phải ly hôn, và giữ lại rất ít tài sản.`;

const KNOWLEDGE_SAMPLE = `Thuyết minh về lạm phát và cách nó vận hành.`;

const DRAMA_GENRES = ["confession", "cheating", "revenge", "twist", "family", "drama"] as const;
const FALLBACK_VOICES: VoiceOption[] = [
  { id: "vi-female", language: "vi", label: "Nữ — Việt Nam" },
  { id: "vi-male", language: "vi", label: "Nam — Việt Nam" },
  { id: "en-female-us", language: "en", label: "Female — US" },
  { id: "en-male-us", language: "en", label: "Male — US" },
];

const COPY: Record<VideoKind, { title: string; lede: string; submit: string; sourceLabel: string; sourceHelp: string }> = {
  drama: {
    title: "Drama",
    lede: "Dán kịch bản hoặc ý tưởng. Studio sẽ phân tích nhân vật, chia cảnh, dựng still và motion theo scene.",
    submit: "Tạo drama",
    sourceLabel: "Chuyện",
    sourceHelp: "Giữ một câu chuyện rõ nhân vật, xung đột, cú xoay và kết. Không cần tách từng câu thành ảnh.",
  },
  news: {
    title: "News",
    lede: "Dán URL bài hoặc ghi chú. Output là editorial stills và Ken Burns, không diễn viên hóa câu chuyện.",
    submit: "Tạo tin",
    sourceLabel: "Bài hoặc ghi chú",
    sourceHelp: "Ưu tiên sự kiện, nhân vật thật, mốc thời gian và kết quả. Có thể thêm ảnh editorial ở panel References.",
  },
  knowledge: {
    title: "Kiến thức",
    lede: "Dán chủ đề. ChatGPT viết lời trước khi dựng stills. URL GitHub chỉ khi muốn thuyết minh một repo.",
    submit: "Tạo thuyết minh",
    sourceLabel: "Chủ đề",
    sourceHelp: "Viết vấn đề cần giải thích, đối tượng người xem và góc nhìn muốn nhấn mạnh.",
  },
};

type PickedAttachment = { id: string; kind: string; filename: string; bind: string };

function defaultVoice(language: string): string {
  return language === "vi" ? "vi-female" : "en-female-us";
}

function providerChips(status: ProviderStatus | null, kind: VideoKind): { id: string; label: string; on: boolean }[] {
  if (!status) return [{ id: "api", label: "Đang đọc provider", on: false }];
  const imageReady = Object.values(status.image ?? {}).some(Boolean) || Boolean(status.grok_image);
  const ttsReady = Object.values(status.tts ?? {}).some(Boolean);
  const motion = status.drama_motion ?? "kenburns";
  const chips = [
    { id: "image", label: imageReady ? "Image ready" : "Image off", on: imageReady },
    { id: "tts", label: ttsReady ? "TTS ready" : "TTS off", on: ttsReady },
  ];
  if (kind === "drama") chips.push({ id: "motion", label: `motion ${motion}`, on: motion !== "kenburns" });
  if (kind === "knowledge") {
    chips.push({ id: "chatgpt", label: status.chatgpt_web_authed ? "ChatGPT ready" : "ChatGPT cần đăng nhập", on: Boolean(status.chatgpt_web_authed) });
  }
  return chips;
}

function attachmentLabel(row: AttachmentRow): string {
  return `${row.kind}:${row.filename}`;
}

export function ComposePage({ kind }: { kind: VideoKind }) {
  const { go } = useNav();
  const { user } = useSession();
  const editorial = kind !== "drama";
  const [text, setText] = useState(kind === "drama" ? DRAMA_SAMPLE : kind === "news" ? NEWS_SAMPLE : KNOWLEDGE_SAMPLE);
  const [mode, setMode] = useState<"script" | "idea">("script");
  const [genre, setGenre] = useState(kind === "drama" ? "confession" : kind);
  const [dramaShape, setDramaShape] = useState<DramaShape>("infer");
  const [language, setLanguage] = useState(kind === "drama" ? "en" : "vi");
  const [voiceId, setVoiceId] = useState(defaultVoice(kind === "drama" ? "en" : "vi"));
  const [seconds, setSeconds] = useState(kind === "drama" ? 60 : 90);
  const [sourceUrl, setSourceUrl] = useState("");
  const [scriptBrief, setScriptBrief] = useState("");
  const [bgmEnabled, setBgmEnabled] = useState(true);
  const [logoEnabled, setLogoEnabled] = useState(false);
  const [pauseBeforeRender, setPauseBeforeRender] = useState(true);
  const [voices, setVoices] = useState<VoiceOption[]>(FALLBACK_VOICES);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [attachKind, setAttachKind] = useState(editorial ? "editorial" : "face");
  const [attachBind, setAttachBind] = useState("");
  const [library, setLibrary] = useState<AttachmentRow[]>([]);
  const [picked, setPicked] = useState<PickedAttachment[]>([]);
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [structureDraft, setStructureDraft] = useState<StoryStructureData | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);
  const [rewriteBusy, setRewriteBusy] = useState<string | null>(null);
  const [aiInstruction, setAiInstruction] = useState("");
  const [templates, setTemplates] = useState<VideoBlueprint[]>([]);
  const [activeTemplate, setActiveTemplate] = useState<VideoBlueprint | null>(null);
  const [appliedTemplateId, setAppliedTemplateId] = useState<string | null>(null);
  const [reverseBusy, setReverseBusy] = useState(false);
  const [reverseTranscribe, setReverseTranscribe] = useState(false);
  const [showVideoMd, setShowVideoMd] = useState(false);
  const [viralPresetsByKind, setViralPresetsByKind] = useState<Record<string, ViralPreset[]>>({});
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [captionPresets, setCaptionPresets] = useState<CaptionPreset[]>([]);
  const [captionPresetId, setCaptionPresetId] = useState<string>("tiktok-gold");
  const [viralScore, setViralScore] = useState<ViralScoreResult | null>(null);
  const [viralBoostBusy, setViralBoostBusy] = useState(false);
  const [viralDeltaNote, setViralDeltaNote] = useState<string | null>(null);
  const copy = COPY[kind];
  const attachChoices = editorial ? ["editorial", "logo", "script"] : ["face", "location", "prop", "logo", "script"];

  useEffect(() => {
    setText(kind === "drama" ? DRAMA_SAMPLE : kind === "news" ? NEWS_SAMPLE : KNOWLEDGE_SAMPLE);
    setGenre(kind === "drama" ? "confession" : kind);
    const nextLang = kind === "drama" ? "en" : "vi";
    setLanguage(nextLang);
    setVoiceId(defaultVoice(nextLang));
    setSeconds(kind === "drama" ? 60 : 90);
    setAttachKind(kind !== "drama" ? "editorial" : "face");
    setStructureDraft(null);
    setActivePresetId(null);
    setViralDeltaNote(null);
    setCaptionPresetId(kind === "drama" ? "drama-amber" : kind === "news" ? "editorial-clean" : "tiktok-gold");
    setMessage(null);
    void readVoices().then((rows) => {
      if (rows.length) setVoices(rows);
    });
    void listAttachments().then(setLibrary);
    void listTemplates().then(setTemplates);
    void readProviders().then(setProviders);
    void readScriptPresets().then((res) => {
      setViralPresetsByKind(res.viral_presets);
      setCaptionPresets(res.caption_presets);
    });
  }, [kind]);

  // Debounced live viral retention evaluation (deterministic, zero API cost)
  useEffect(() => {
    const trimmed = text.trim();
    if (trimmed.length < 8) {
      setViralScore(null);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void scoreViralScript({
        kind,
        text: trimmed,
        language,
        target_seconds: seconds,
        structure: structureDraft,
      })
        .then((res) => {
          if (!cancelled) setViralScore(res);
        })
        .catch(() => undefined);
    }, 450);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [kind, language, seconds, structureDraft, text]);

  const activeViralPresets = useMemo(() => viralPresetsByKind[kind] ?? [], [kind, viralPresetsByKind]);
  const selectedCaption = useMemo(
    () => captionPresets.find((p) => p.id === captionPresetId) ?? captionPresets[0] ?? null,
    [captionPresetId, captionPresets],
  );
  const creditsLeft = user?.role === "operator" ? null : (user?.billing?.credits_remaining ?? 0);
  const outOfCredits = creditsLeft !== null && creditsLeft <= 0;

  const voiceChoices = useMemo(() => {
    const rows = voices.filter((voice) => voice.language === language);
    if (rows.length) return rows;
    return FALLBACK_VOICES.filter((voice) => voice.language === language);
  }, [language, voices]);

  const availableLibrary = useMemo(() => {
    return library.filter((row) => attachChoices.includes(row.kind) && !picked.some((item) => item.id === row.id)).slice(0, 8);
  }, [attachChoices, library, picked]);

  const canSubmit = !busy && !outOfCredits && (text.trim().length >= 8 || (editorial && sourceUrl.trim().length >= 12));
  const sourceCount = text.trim().length;

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const data = await createJob({
        mode: kind === "drama" ? mode : "script",
        kind,
        text: text.trim().length >= 8 ? text : `News from ${sourceUrl.trim()}`,
        target_seconds: seconds,
        genre,
        drama_shape: kind === "drama" ? dramaShape : undefined,
        language,
        voice_id: voiceId,
        source_url: editorial ? sourceUrl.trim() || null : null,
        script_brief: scriptBrief.trim() || null,
        reference_template_id: appliedTemplateId,
        subtitle: selectedCaption ? selectedCaption.subtitle : null,
        attachments: picked.map((item) => ({ id: item.id, bind: item.bind || null })),
        mix: { logo_enabled: logoEnabled, bgm_enabled: bgmEnabled, pause_before_render: pauseBeforeRender },
      });
      go(`/watch/${data.id}`);
    } catch (err) {
      setBusy(false);
      if (err instanceof ApiError && err.status === 402) {
        const left = err.billing?.credits_remaining ?? 0;
        setMessage(
          left <= 0
            ? "Hết lượt tạo video. Vào Tài khoản để đăng ký gói hoặc chờ admin cấp credit."
            : `${err.message}. Vào Tài khoản để xem gói và nâng cấp.`,
        );
      } else {
        setMessage(err instanceof Error ? err.message : "Could not create job");
      }
    }
  }

  function pickAttachment(row: AttachmentRow) {
    setPicked((prev) =>
      prev.some((item) => item.id === row.id)
        ? prev
        : [...prev, { id: row.id, kind: row.kind, filename: row.filename, bind: attachBind.trim() }],
    );
  }

  function syncTextFromStructure(next: StoryStructureData) {
    setStructureDraft(next);
    const joined = [next.hook, next.conflict, next.rising_action, next.twist, next.ending]
      .map((item) => (item || "").trim())
      .filter(Boolean)
      .join("\n\n");
    if (joined) setText(joined);
  }

  function splitTextIntoFiveBeats() {
    const paras = text
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .filter(Boolean);
    const next: StoryStructureData = {
      hook: paras[0] || text.trim(),
      conflict: paras[1] || "",
      rising_action: paras[2] || "",
      twist: paras[3] || "",
      ending: paras[4] || "",
    };
    setStructureDraft(next);
  }

  function applyBlueprintTemplate(bp: VideoBlueprint) {
    setActiveTemplate(bp);
    setAppliedTemplateId(bp.id);
    if (bp.script_brief) {
      setScriptBrief((prev) => {
        const clean = prev.trim();
        if (!clean) return bp.script_brief;
        if (clean.includes(bp.script_brief.slice(0, 48))) return clean;
        return `${clean}\n\n${bp.script_brief}`.slice(0, 2000);
      });
    }
    const clampedSec = Math.max(15, Math.min(180, Math.round(bp.duration_sec)));
    if (clampedSec >= 15) setSeconds(clampedSec);
  }

  async function handleReverseUpload(file: File) {
    setReverseBusy(true);
    setMessage(null);
    try {
      const bp = await reverseEngineerVideo(file, {
        language,
        useVlm: true,
        transcribe: reverseTranscribe,
      });
      setTemplates((prev) => [bp, ...prev.filter((item) => item.id !== bp.id)]);
      applyBlueprintTemplate(bp);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Không dịch ngược được video mẫu");
    } finally {
      setReverseBusy(false);
    }
  }

  async function handleDeleteTemplate(id: string) {
    try {
      await deleteTemplate(id);
      setTemplates((prev) => prev.filter((item) => item.id !== id));
      if (activeTemplate?.id === id) setActiveTemplate(null);
      if (appliedTemplateId === id) setAppliedTemplateId(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Không xoá được mẫu video");
    }
  }

  function applyViralPreset(preset: ViralPreset) {
    setActivePresetId(preset.id);
    setScriptBrief(preset.brief);
  }

  async function handleViralBoost() {
    if (!text.trim()) return;
    setViralBoostBusy(true);
    setMessage(null);
    setViralDeltaNote(null);
    try {
      const res = await boostViralScript({
        kind,
        text: text.trim(),
        language,
        target_seconds: seconds,
        instruction: aiInstruction.trim() || scriptBrief.trim(),
        structure: structureDraft,
      });
      setStructureDraft(res.structure);
      if (res.text) setText(res.text);
      setViralScore(res.after);
      const diff = res.after.score - res.before.score;
      setViralDeltaNote(
        `Đã tối ưu (${res.provider}): ${res.before.score} → ${res.after.score}/100 (${diff >= 0 ? `+${diff}` : diff} điểm, hạng ${res.after.grade}).`,
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Không tối ưu viral được kịch bản");
    } finally {
      setViralBoostBusy(false);
    }
  }

  async function handleDraftWithAi() {
    setDraftBusy(true);
    setMessage(null);
    try {
      const res = await draftScript({
        kind,
        text: text.trim() || sourceUrl.trim(),
        language,
        target_seconds: seconds,
        source_url: editorial ? sourceUrl.trim() || null : null,
        script_brief: scriptBrief.trim() || null,
      });
      setStructureDraft(res.structure);
      if (res.text) setText(res.text);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Không tạo được dàn ý 5 phần");
    } finally {
      setDraftBusy(false);
    }
  }

  async function handleRewriteBeat(beatKey: string) {
    if (!structureDraft) return;
    setRewriteBusy(beatKey);
    setMessage(null);
    try {
      const res = await rewriteScript({
        kind,
        language,
        target_seconds: seconds,
        beat: beatKey,
        instruction: aiInstruction.trim() || scriptBrief.trim(),
        structure: structureDraft,
      });
      syncTextFromStructure(res.structure);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Không viết lại được phần này");
    } finally {
      setRewriteBusy(null);
    }
  }

  return (
    <section className="page-stack compose-page">
      <PageHeader
        kicker="Tạo video"
        title={copy.title}
        lede={copy.lede}
        actions={
          <button type="button" className="ghost" onClick={() => go("/work")}>
            Về Work
          </button>
        }
        meta={
          <div className="provider-row">
            {providerChips(providers, kind).map((chip) => (
              <StatusPill key={chip.id} label={chip.label} tone={chip.on ? "done" : "idle"} />
            ))}
          </div>
        }
      />

      <form className="compose-form" onSubmit={(event) => void onSubmit(event)}>
        <div className="compose-grid">
          <section className="panel compose-panel source-panel">
            <div className="section-head compact">
              <div>
                <p className="kicker">Source</p>
                <h2>Nội dung gốc</h2>
              </div>
              <StatusPill label={`${sourceCount} ký tự`} tone={sourceCount >= 8 ? "done" : "idle"} />
            </div>

            {kind === "news" ? (
              <label>
                URL bài
                <input
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  placeholder="https://…"
                />
              </label>
            ) : null}

            {kind === "drama" ? (
              <div className="fields two">
                <label>
                  Shape
                  <select
                    value={dramaShape}
                    onChange={(e) => {
                      const next = e.target.value as DramaShape;
                      if (text === DRAMA_SAMPLE || text === DRAMA_VIRAL_SAMPLE) {
                        setText(next === "default" ? DRAMA_VIRAL_SAMPLE : DRAMA_SAMPLE);
                      }
                      setDramaShape(next);
                    }}
                  >
                    <option value="infer">Auto</option>
                    <option value="default">Viral</option>
                    <option value="custom">Custom</option>
                  </select>
                </label>
                <label>
                  Mode
                  <select value={mode} onChange={(e) => setMode(e.target.value as "script" | "idea")}>
                    <option value="script">Script</option>
                    <option value="idea">Idea</option>
                  </select>
                </label>
              </div>
            ) : null}

            <label>
              {copy.sourceLabel}
              <textarea value={text} onChange={(e) => setText(e.target.value)} rows={14} />
              <span className="field-hint">{copy.sourceHelp}</span>
            </label>

            {kind === "knowledge" ? (
              <label>
                GitHub URL, tuỳ chọn
                <input
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  placeholder="https://github.com/owner/repo"
                />
                <span className="field-hint">Bỏ trống nếu chỉ có chủ đề hoặc ghi chú.</span>
              </label>
            ) : null}

            {activeViralPresets.length > 0 ? (
              <div className="viral-preset-block">
                <div className="section-head compact">
                  <div>
                    <p className="kicker">Viral Formula</p>
                    <p className="card-title">Công thức giữ chân & tò mò (1 bấm)</p>
                  </div>
                </div>
                <div className="preset-grid">
                  {activeViralPresets.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      className={`preset-chip${activePresetId === preset.id ? " on" : ""}`}
                      onClick={() => applyViralPreset(preset)}
                    >
                      <div className="preset-chip-head">
                        <strong>{preset.name}</strong>
                        <span className="table-badge">{preset.tag}</span>
                      </div>
                      <small>{preset.summary}</small>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <label>
              Ghi chú lời
              <textarea value={scriptBrief} onChange={(e) => setScriptBrief(e.target.value)} rows={3} maxLength={2000} />
              <span className="field-hint">Dùng cho tone, ngôn ngữ, thông tin bắt buộc hoặc điều cần tránh.</span>
            </label>

            {viralScore ? (
              <div className="viral-card">
                <div className="viral-head">
                  <div>
                    <p className="kicker">Retention Audit</p>
                    <h3>Chỉ số giữ chân & khả năng viral</h3>
                  </div>
                  <div className="viral-score-badge">
                    <span className="viral-grade">{viralScore.grade}</span>
                    <div>
                      <strong>{viralScore.score}/100</strong>
                      <span>
                        {viralScore.word_count} từ · ~{viralScore.estimated_seconds}s
                      </span>
                    </div>
                  </div>
                </div>
                <div className="viral-metrics">
                  {Object.entries(viralScore.metrics).map(([key, m]) => {
                    const pct = Math.round((m.score / Math.max(1, m.max)) * 100);
                    return (
                      <div key={key} className="viral-metric-row">
                        <div className="viral-metric-label">
                          <span>{m.label}</span>
                          <strong>
                            {m.score}/{m.max}
                          </strong>
                        </div>
                        <div className="progress-track">
                          <div className="progress-fill" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
                {viralScore.tips.length > 0 ? (
                  <ul className="viral-tips">
                    {viralScore.tips.map((tip) => (
                      <li key={tip}>{tip}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="meta">Kịch bản đã đạt cấu trúc mở đầu tò mò, có điểm bẻ lái và nhịp đọc tốt.</p>
                )}
                {viralDeltaNote ? <p className="meta viral-delta">{viralDeltaNote}</p> : null}
              </div>
            ) : null}

            <div className="hub-actions compose-ai-actions">
              <button
                type="button"
                disabled={viralBoostBusy || text.trim().length < 8}
                onClick={() => void handleViralBoost()}
              >
                {viralBoostBusy ? "Đang tối ưu Viral…" : "Tối ưu Viral (AI)"}
              </button>
              <button
                type="button"
                className="ghost"
                disabled={draftBusy || (!text.trim() && !sourceUrl.trim())}
                onClick={() => void handleDraftWithAi()}
              >
                {draftBusy ? "Đang soạn dàn ý 5 phần…" : "Soạn cấu trúc 5 phần (ChatGPT / AI)"}
              </button>
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  if (structureDraft) setStructureDraft(null);
                  else splitTextIntoFiveBeats();
                }}
              >
                {structureDraft ? "Ẩn khung sửa 5 phần" : "Mở khung sửa từng phần (5 phần)"}
              </button>
            </div>

            {structureDraft ? (
              <div className="structure-builder" style={{ marginTop: "14px", display: "grid", gap: "12px" }}>
                <div className="section-head compact">
                  <div>
                    <p className="kicker">Storytelling Framework</p>
                    <h3>Chỉnh sửa chi tiết 5 phần nội dung</h3>
                  </div>
                  <button
                    type="button"
                    className="ghost"
                    disabled={rewriteBusy !== null}
                    onClick={() => void handleRewriteBeat("all")}
                  >
                    {rewriteBusy === "all" ? "Đang viết lại…" : "AI trau chuốt cả 5 phần"}
                  </button>
                </div>
                <label>
                  Yêu cầu chỉnh sửa thêm cho AI (tuỳ chọn)
                  <input
                    value={aiInstruction}
                    onChange={(e) => setAiInstruction(e.target.value)}
                    placeholder="VD: Thêm con số cụ thể ở mở đầu, giọng kể cuốn hút, câu ngắn gọn…"
                  />
                </label>
                {BEAT_META.map((item) => (
                  <div key={item.key} className="beat-card" style={{ display: "grid", gap: "6px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px" }}>
                      <strong>{item.label}</strong>
                      <button
                        type="button"
                        className="ghost"
                        disabled={rewriteBusy !== null}
                        onClick={() => void handleRewriteBeat(item.key)}
                      >
                        {rewriteBusy === item.key ? "Đang viết…" : "AI viết lại phần này"}
                      </button>
                    </div>
                    <textarea
                      rows={3}
                      value={structureDraft[item.key] || ""}
                      onChange={(e) =>
                        syncTextFromStructure({
                          ...structureDraft,
                          [item.key]: e.target.value,
                        })
                      }
                    />
                    <span className="field-hint">{item.hint}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </section>

          <section className="panel compose-panel settings-panel">
            <div className="section-head compact">
              <div>
                <p className="kicker">Production</p>
                <h2>Cài đặt dựng</h2>
              </div>
            </div>

            <div className="fields two">
              {kind === "drama" ? (
                <label>
                  Genre
                  <select value={genre} onChange={(e) => setGenre(e.target.value)}>
                    {DRAMA_GENRES.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <label>
                  Kind
                  <input value={kind} readOnly />
                </label>
              )}
              <label>
                Giây
                <input type="number" min={15} max={600} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} />
              </label>
              <label>
                Ngôn ngữ
                <select
                  value={language}
                  onChange={(e) => {
                    setLanguage(e.target.value);
                    setVoiceId(defaultVoice(e.target.value));
                  }}
                >
                  <option value="vi">vi</option>
                  <option value="en">en</option>
                </select>
              </label>
              <label>
                Giọng
                <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)}>
                  {voiceChoices.map((voice) => (
                    <option key={voice.id} value={voice.id}>
                      {voice.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mix-card">
              <p className="card-title">Mix & Chế độ duyệt</p>
              <label className="check">
                <input type="checkbox" checked={bgmEnabled} onChange={(e) => setBgmEnabled(e.target.checked)} />
                Nhạc nền
              </label>
              <label className="check">
                <input type="checkbox" checked={logoEnabled} onChange={(e) => setLogoEnabled(e.target.checked)} />
                Logo
              </label>
              <label className="check">
                <input
                  type="checkbox"
                  checked={pauseBeforeRender}
                  onChange={(e) => setPauseBeforeRender(e.target.checked)}
                />
                Tạm dừng sau Ảnh + Lời để duyệt/sửa trước khi xuất MP4
              </label>
            </div>

            {captionPresets.length > 0 ? (
              <div className="caption-card">
                <div className="section-head compact">
                  <div>
                    <p className="kicker">Karaoke Captions</p>
                    <p className="card-title">Phong cách phụ đề giữ mắt</p>
                  </div>
                  {selectedCaption ? <StatusPill label={selectedCaption.tag} tone="accent" /> : null}
                </div>
                <div className="caption-preset-grid">
                  {captionPresets.map((preset) => (
                    <button
                      key={preset.id}
                      type="button"
                      className={`caption-preset-btn${captionPresetId === preset.id ? " on" : ""}`}
                      onClick={() => setCaptionPresetId(preset.id)}
                    >
                      <strong>{preset.name}</strong>
                      <small>{preset.description}</small>
                    </button>
                  ))}
                </div>
                {selectedCaption ? (
                  <div className="caption-stage" aria-label="Xem trước phụ đề">
                    <span className="caption-stage-tag">9:16 Preview</span>
                    <p
                      className="caption-stage-line"
                      style={{
                        color: selectedCaption.subtitle.primary_hex || "#FFFFFF",
                        textShadow: `0 2px 0 ${selectedCaption.subtitle.outline_hex || "#101010"}, 0 -2px 0 ${selectedCaption.subtitle.outline_hex || "#101010"}, 2px 0 0 ${selectedCaption.subtitle.outline_hex || "#101010"}, -2px 0 0 ${selectedCaption.subtitle.outline_hex || "#101010"}`,
                      }}
                    >
                      SỰ THẬT{" "}
                      <span style={{ color: selectedCaption.subtitle.highlight_hex || "#FFE000" }}>
                        ÍT AI BIẾT
                      </span>{" "}
                      ĐẰNG SAU
                    </p>
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="provider-card">
              <p className="card-title">Provider readiness</p>
              <div className="provider-row">
                {providerChips(providers, kind).map((chip) => (
                  <StatusPill key={chip.id} label={chip.label} tone={chip.on ? "done" : "idle"} />
                ))}
              </div>
              {kind === "drama" ? (
                <p className="meta">Motion theo provider (kenburns / i2v / mixed). Đăng nhập Muse/Grok ở Account nếu cần hub.</p>
              ) : null}
              {kind === "knowledge" && providers && !providers.chatgpt_web_authed ? (
                <p className="meta">ChatGPT chưa sẵn sàng — đăng nhập ở Account để viết lời knowledge.</p>
              ) : null}
            </div>
          </section>

          <section className="panel compose-panel references-panel">
            <div className="section-head compact">
              <div>
                <p className="kicker">References</p>
                <h2>File gắn kèm</h2>
              </div>
              <StatusPill label={`${picked.length} chọn`} tone={picked.length ? "accent" : "idle"} />
            </div>

            <div className="fields two">
              <label>
                Loại file
                <select value={attachKind} onChange={(e) => setAttachKind(e.target.value)}>
                  {attachChoices.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Bind
                <input value={attachBind} onChange={(e) => setAttachBind(e.target.value)} placeholder="tuỳ chọn" />
              </label>
            </div>

            <label className="upload-box">
              Tải lên
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
              <span className="field-hint">Ảnh dùng PNG, JPEG, WebP. Script dùng TXT hoặc Markdown.</span>
            </label>

            {picked.length > 0 ? (
              <div className="picked-list">
                {picked.map((item) => (
                  <article key={item.id} className="picked-card">
                    <div>
                      <strong>{item.filename}</strong>
                      <span>
                        {item.kind}{item.bind ? ` · ${item.bind}` : ""}
                      </span>
                    </div>
                    <button type="button" className="ghost" onClick={() => setPicked((prev) => prev.filter((row) => row.id !== item.id))}>
                      Bỏ
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <p className="meta">Chưa chọn file. Drama nên có face/location/prop khi cần giữ nhân vật.</p>
            )}

            {availableLibrary.length > 0 ? (
              <div className="library-picks">
                <p className="card-title">Thư viện gần đây</p>
                {availableLibrary.map((row) => (
                  <button key={row.id} type="button" className="library-chip" onClick={() => pickAttachment(row)}>
                    {attachmentLabel(row)}
                  </button>
                ))}
              </div>
            ) : null}

            <div className="mix-card reverse-box">
              <div className="section-head compact">
                <div>
                  <p className="kicker">Reverse Video</p>
                  <p className="card-title">Dịch ngược video mẫu</p>
                </div>
                <StatusPill
                  label={appliedTemplateId ? "Đang áp dụng mẫu" : `${templates.length} mẫu`}
                  tone={appliedTemplateId ? "done" : "idle"}
                />
              </div>
              <span className="field-hint">
                Tải lên 1 video mẫu (MP4/MOV/WebM) để bóc từng shot, nhịp cắt, góc máy, bảng màu và tạo bản vẽ VIDEO.md (không sao chép mặt hay footage gốc).
              </span>
              <label className="check">
                <input
                  type="checkbox"
                  checked={reverseTranscribe}
                  onChange={(e) => setReverseTranscribe(e.target.checked)}
                />
                Tách lời thoại mẫu bằng Whisper (chậm hơn một chút)
              </label>
              <label className="upload-box">
                {reverseBusy ? "Đang dịch ngược từng shot…" : "Chọn video mẫu để dịch ngược"}
                <input
                  type="file"
                  accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm,.mkv"
                  disabled={reverseBusy}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    e.target.value = "";
                    if (!file) return;
                    void handleReverseUpload(file);
                  }}
                />
                <span className="field-hint">Tối đa 120MB. Tự nhận diện shot + màu bằng FFmpeg, tăng độ chi tiết nếu có VLM key.</span>
              </label>

              {templates.length > 0 ? (
                <div className="library-picks">
                  <p className="card-title">Mẫu đã dịch ngược</p>
                  {templates.slice(0, 6).map((tpl) => {
                    const isApplied = appliedTemplateId === tpl.id;
                    return (
                      <div key={tpl.id} className="tpl-row">
                        <button
                          type="button"
                          className={`library-chip${isApplied ? " on" : ""}`}
                          onClick={() => setActiveTemplate(tpl)}
                        >
                          {tpl.name} · {Math.round(tpl.duration_sec)}s · {tpl.shots.length} shot ({tpl.pacing})
                        </button>
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => void handleDeleteTemplate(tpl.id)}
                        >
                          Xoá
                        </button>
                      </div>
                    );
                  })}
                </div>
              ) : null}

              {activeTemplate ? (
                <div className="reverse-detail">
                  <div className="reverse-detail-head">
                    <strong>{activeTemplate.name}</strong>
                    <span className="meta">
                      {activeTemplate.width}×{activeTemplate.height} · {activeTemplate.duration_sec}s · avg {activeTemplate.avg_shot_sec}s/shot · {activeTemplate.analyzer_provider}
                    </span>
                  </div>
                  <p className="meta">
                    <strong>Hook:</strong> {activeTemplate.hook_style}
                  </p>
                  <p className="meta">
                    <strong>Style:</strong> {activeTemplate.visual_style}
                  </p>
                  {activeTemplate.color_palette.length > 0 ? (
                    <div className="palette-swatches">
                      {activeTemplate.color_palette.map((hex) => (
                        <span key={hex} title={hex} className="palette-pill">
                          <span className="palette-dot" style={{ background: hex }} />
                          {hex}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {activeTemplate.shots.length > 0 ? (
                    <div className="shot-strip">
                      {activeTemplate.shots.slice(0, 8).map((shot) => (
                        <div key={shot.index} className="shot-tile">
                          {shot.frame_rel ? (
                            <img src={`/files/${shot.frame_rel}`} alt={`Shot ${shot.index}`} />
                          ) : null}
                          <span>
                            #{shot.index} {shot.beat} ({shot.duration_sec}s)
                          </span>
                          <span className="meta">
                            {shot.camera}/{shot.motion}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  <div className="hub-actions">
                    <button type="button" onClick={() => applyBlueprintTemplate(activeTemplate)}>
                      {appliedTemplateId === activeTemplate.id ? "Đã áp dụng mẫu này" : "Áp dụng mẫu này"}
                    </button>
                    {appliedTemplateId === activeTemplate.id ? (
                      <button type="button" className="ghost" onClick={() => setAppliedTemplateId(null)}>
                        Bỏ áp dụng
                      </button>
                    ) : null}
                    <button type="button" className="ghost" onClick={() => setShowVideoMd((prev) => !prev)}>
                      {showVideoMd ? "Ẩn VIDEO.md" : "Xem VIDEO.md"}
                    </button>
                  </div>
                  {showVideoMd ? (
                    <textarea readOnly rows={10} value={activeTemplate.video_md} className="video-md-view" />
                  ) : null}
                </div>
              ) : null}
            </div>
          </section>
        </div>

        {message ? <p className="err">{message}</p> : null}
        <div className="mobile-action-bar">
          <div>
            <strong>
              {copy.title}
              {viralScore ? ` · Viral ${viralScore.score}/100 (${viralScore.grade})` : ""}
            </strong>
            <span>
              {outOfCredits
                ? "Hết credit tạo video — nâng cấp gói ở Tài khoản để tiếp tục"
                : creditsLeft !== null
                  ? `Còn ${creditsLeft} credit · Tạo video tốn 1 credit`
                  : "Operator · Không giới hạn lượt tạo"}
            </span>
          </div>
          <div className="hub-actions">
            {outOfCredits ? (
              <button type="button" onClick={() => go("/account")}>
                Nâng cấp gói
              </button>
            ) : (
              <button type="submit" disabled={!canSubmit}>
                {busy ? "Đang tạo…" : copy.submit}
              </button>
            )}
          </div>
        </div>
      </form>
    </section>
  );
}
