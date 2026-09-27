import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  createJob,
  listAttachments,
  readProviders,
  readVoices,
  startChatgptLogin,
  uploadAttachment,
  type AttachmentRow,
  type ProviderStatus,
  type VoiceOption,
} from "../api";
import { PageHeader, StatusPill } from "../components";
import { useNav } from "../nav";
import type { DramaShape, VideoKind } from "../types";

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
  const [voices, setVoices] = useState<VoiceOption[]>(FALLBACK_VOICES);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [attachKind, setAttachKind] = useState(editorial ? "editorial" : "face");
  const [attachBind, setAttachBind] = useState("");
  const [library, setLibrary] = useState<AttachmentRow[]>([]);
  const [picked, setPicked] = useState<PickedAttachment[]>([]);
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [chatgptOpening, setChatgptOpening] = useState(false);
  const copy = COPY[kind];
  const attachChoices = editorial ? ["editorial", "logo", "script"] : ["face", "location", "prop", "logo", "script"];

  useEffect(() => {
    void readVoices().then((rows) => {
      if (rows.length) setVoices(rows);
    });
    void listAttachments().then(setLibrary);
    void readProviders().then(setProviders);
  }, [kind]);

  useEffect(() => {
    if (!chatgptOpening) return;
    const timer = window.setInterval(() => {
      void readProviders().then((status) => {
        setProviders(status);
        if (status?.chatgpt_web_authed) {
          setChatgptOpening(false);
          setMessage("Đã lưu phiên ChatGPT.");
        }
      });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [chatgptOpening]);

  const voiceChoices = useMemo(() => {
    const rows = voices.filter((voice) => voice.language === language);
    if (rows.length) return rows;
    return FALLBACK_VOICES.filter((voice) => voice.language === language);
  }, [language, voices]);

  const availableLibrary = useMemo(() => {
    return library.filter((row) => attachChoices.includes(row.kind) && !picked.some((item) => item.id === row.id)).slice(0, 8);
  }, [attachChoices, library, picked]);

  const canSubmit = !busy && (text.trim().length >= 8 || (editorial && sourceUrl.trim().length >= 12));
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
        attachments: picked.map((item) => ({ id: item.id, bind: item.bind || null })),
        mix: { logo_enabled: logoEnabled, bgm_enabled: bgmEnabled },
      });
      go(`/watch/${data.id}`);
    } catch (err) {
      setBusy(false);
      setMessage(err instanceof Error ? err.message : "Could not create job");
    }
  }

  function pickAttachment(row: AttachmentRow) {
    setPicked((prev) =>
      prev.some((item) => item.id === row.id)
        ? prev
        : [...prev, { id: row.id, kind: row.kind, filename: row.filename, bind: attachBind.trim() }],
    );
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

            <label>
              Ghi chú lời
              <textarea value={scriptBrief} onChange={(e) => setScriptBrief(e.target.value)} rows={4} maxLength={2000} />
              <span className="field-hint">Dùng cho tone, ngôn ngữ, thông tin bắt buộc hoặc điều cần tránh.</span>
            </label>
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
                <input type="number" min={15} max={180} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} />
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
              <p className="card-title">Mix</p>
              <label className="check">
                <input type="checkbox" checked={bgmEnabled} onChange={(e) => setBgmEnabled(e.target.checked)} />
                Nhạc nền
              </label>
              <label className="check">
                <input type="checkbox" checked={logoEnabled} onChange={(e) => setLogoEnabled(e.target.checked)} />
                Logo
              </label>
            </div>

            <div className="provider-card">
              <p className="card-title">Provider readiness</p>
              <div className="provider-row">
                {providerChips(providers, kind).map((chip) => (
                  <StatusPill key={chip.id} label={chip.label} tone={chip.on ? "done" : "idle"} />
                ))}
              </div>
              {kind === "drama" ? (
                <p className="meta">Motion hiển thị đúng theo provider: kenburns, i2v hoặc mixed khi backend trả về.</p>
              ) : null}
              {kind === "knowledge" && providers && !providers.chatgpt_web_authed ? (
                <button
                  type="button"
                  className="ghost"
                  disabled={chatgptOpening}
                  onClick={() => {
                    setMessage(null);
                    void startChatgptLogin()
                      .then(() => {
                        setChatgptOpening(true);
                        setMessage("Chrome đang mở. Đăng nhập ChatGPT. Cửa sổ đóng khi phiên được lưu.");
                      })
                      .catch((err) => setMessage(err instanceof Error ? err.message : "Could not open ChatGPT"));
                  }}
                >
                  {chatgptOpening ? "Đang chờ ChatGPT…" : "Sign in to ChatGPT"}
                </button>
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
          </section>
        </div>

        {message ? <p className="err">{message}</p> : null}
        <div className="mobile-action-bar">
          <div>
            <strong>{copy.title}</strong>
            <span>{canSubmit ? "Sẵn sàng tạo job" : "Cần nội dung hoặc URL hợp lệ"}</span>
          </div>
          <button type="submit" disabled={!canSubmit}>
            {busy ? "Đang tạo…" : copy.submit}
          </button>
        </div>
      </form>
    </section>
  );
}
