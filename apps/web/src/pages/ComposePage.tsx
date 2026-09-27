import { FormEvent, useEffect, useState } from "react";
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

function defaultVoice(language: string): string {
  return language === "vi" ? "vi-female" : "en-female-us";
}

const COPY: Record<VideoKind, { title: string; lede: string; submit: string }> = {
  drama: {
    title: "Drama",
    lede: "Dán kịch bản hoặc tên người. Shape auto, viral, hoặc custom. Ảnh mặt lấy từ sổ nhân vật.",
    submit: "Tạo drama",
  },
  news: {
    title: "News",
    lede: "Dán URL bài hoặc ghi chú. Năm nhịp phủ đến đoạn kết. Ảnh ghép, không diễn viên.",
    submit: "Tạo tin",
  },
  knowledge: {
    title: "Kiến thức",
    lede: "Dán một chủ đề hoặc URL GitHub. ChatGPT viết lời trước khi dựng ảnh.",
    submit: "Tạo thuyết minh",
  },
};

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
  const [picked, setPicked] = useState<{ id: string; kind: string; filename: string; bind: string }[]>([]);
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [chatgptOpening, setChatgptOpening] = useState(false);
  const copy = COPY[kind];
  const attachChoices = editorial ? ["editorial", "logo", "script"] : ["face", "location", "prop", "logo", "script"];

  useEffect(() => {
    void readVoices().then((rows) => {
      if (rows.length) setVoices(rows);
    });
    void listAttachments().then(setLibrary);
    if (kind === "knowledge") void readProviders().then(setProviders);
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

  return (
    <section>
      <p className="kicker">Tạo video</p>
      <h1>{copy.title}</h1>
      <p className="lede">{copy.lede}</p>
      {kind === "knowledge" && providers && !providers.chatgpt_web_authed ? (
        <div className="actions">
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
        </div>
      ) : null}
      {kind === "knowledge" && providers?.chatgpt_web_authed ? <p className="meta">ChatGPT đã đăng nhập.</p> : null}
      <form className="panel" onSubmit={(event) => void onSubmit(event)}>
        <div className="fields">
          {kind === "drama" ? (
            <>
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
            </>
          ) : (
            <label className="span-2">
              {kind === "knowledge" ? "GitHub URL" : "URL bài"}
              <input
                value={sourceUrl}
                onChange={(e) => setSourceUrl(e.target.value)}
                placeholder={kind === "knowledge" ? "https://github.com/owner/repo" : "https://…"}
              />
            </label>
          )}
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
              {voices
                .filter((voice) => voice.language === language)
                .map((voice) => (
                  <option key={voice.id} value={voice.id}>
                    {voice.label}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Giây
            <input type="number" min={15} max={180} value={seconds} onChange={(e) => setSeconds(Number(e.target.value))} />
          </label>
        </div>
        <label>
          {kind === "news" ? "Bài hoặc ghi chú" : kind === "knowledge" ? "Chủ đề" : "Chuyện"}
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={8} />
        </label>
        <label>
          Ghi chú lời
          <textarea value={scriptBrief} onChange={(e) => setScriptBrief(e.target.value)} rows={3} maxLength={2000} />
        </label>
        <div className="mix-opts">
          <label className="check">
            <input type="checkbox" checked={bgmEnabled} onChange={(e) => setBgmEnabled(e.target.checked)} />
            Nhạc nền
          </label>
          <label className="check">
            <input type="checkbox" checked={logoEnabled} onChange={(e) => setLogoEnabled(e.target.checked)} />
            Logo
          </label>
        </div>
        <div className="fields">
          <label>
            File
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
          <label>
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
          </label>
        </div>
        {picked.length > 0 ? (
          <ul className="chips">
            {picked.map((item) => (
              <li key={item.id}>
                {item.kind}:{item.filename}
                <button type="button" className="ghost" onClick={() => setPicked((prev) => prev.filter((row) => row.id !== item.id))}>
                  Bỏ
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {library.some((row) => attachChoices.includes(row.kind) && !picked.some((item) => item.id === row.id)) ? (
          <p className="meta">
            Thư viện:{" "}
            {library
              .filter((row) => attachChoices.includes(row.kind) && !picked.some((item) => item.id === row.id))
              .slice(0, 6)
              .map((row) => (
                <button
                  key={row.id}
                  type="button"
                  className="ghost"
                  onClick={() =>
                    setPicked((prev) => [...prev, { id: row.id, kind: row.kind, filename: row.filename, bind: attachBind.trim() }])
                  }
                >
                  {row.kind}:{row.filename}
                </button>
              ))}
          </p>
        ) : null}
        {message ? <p className="err">{message}</p> : null}
        <div className="actions">
          <button type="submit" disabled={busy || (text.trim().length < 8 && sourceUrl.trim().length < 12)}>
            {busy ? "Đang tạo…" : copy.submit}
          </button>
        </div>
      </form>
    </section>
  );
}
