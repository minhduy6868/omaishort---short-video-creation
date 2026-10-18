import { useEffect, useMemo, useState } from "react";
import {
  listAttachments,
  openChatgptContent,
  readElevenLabs,
  readProviders,
  saveElevenLabs,
  startChatgptLogin,
  startGrokLogin,
  type AttachmentRow,
  type ElevenLabsHub,
  type ProviderStatus,
} from "../api";
import { CounterCard, PageHeader, StatusPill } from "../components";
import { useSession } from "../session";

function chips(status: ProviderStatus): { id: string; on: boolean; label: string }[] {
  const image = status.image ?? {};
  const video = status.video ?? {};
  const motion = status.drama_motion ?? "kenburns";
  return [
    { id: "chatgpt", on: Boolean(status.chatgpt_web_authed), label: status.chatgpt_web_authed ? "ChatGPT ready" : "ChatGPT off" },
    { id: "grok", on: Boolean(status.grok_hub_authed), label: status.grok_hub_authed ? "Grok hub" : "Grok hub off" },
    { id: "gemini", on: Boolean(image.gemini), label: image.gemini ? "Gemini API" : "Gemini cần key" },
    { id: "motion", on: motion !== "kenburns", label: `motion ${motion}` },
    { id: "tts", on: Object.values(status.tts ?? {}).some(Boolean), label: "TTS" },
    { id: "image", on: Object.values(image).some(Boolean) || Boolean(status.grok_image), label: "Image" },
    { id: "video", on: Object.values(video).some(Boolean) || Boolean(status.grok_video), label: "Video" },
  ];
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function AccountPage() {
  const { user } = useSession();
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [attachments, setAttachments] = useState<AttachmentRow[]>([]);
  const [chatgptOpening, setChatgptOpening] = useState(false);
  const [chatgptMessage, setChatgptMessage] = useState<string | null>(null);
  const [grokOpening, setGrokOpening] = useState(false);
  const [grokMessage, setGrokMessage] = useState<string | null>(null);
  const [eleven, setEleven] = useState<ElevenLabsHub | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [voiceId, setVoiceId] = useState("aN7cv9yXNrfIR87bDmyD");
  const [modelId, setModelId] = useState("eleven_v3");
  const [elevenEnabled, setElevenEnabled] = useState(false);
  const [elevenMode, setElevenMode] = useState<"anonymous" | "api">("anonymous");
  const [hubBusy, setHubBusy] = useState(false);
  const [hubMessage, setHubMessage] = useState<string | null>(null);

  useEffect(() => {
    void readProviders().then(setProviders);
    void listAttachments().then(setAttachments);
    void readElevenLabs()
      .then((hub) => {
        setEleven(hub);
        setVoiceId(hub.voice_id || "");
        setModelId(hub.model_id || "eleven_v3");
        setElevenEnabled(hub.enabled);
        setElevenMode(hub.mode === "api" ? "api" : "anonymous");
      })
      .catch((err) => setHubMessage(err instanceof Error ? err.message : "Không đọc được ElevenLabs"));
  }, []);

  useEffect(() => {
    const refresh = () => {
      if (!document.hidden) void readProviders().then(setProviders);
    };
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.removeEventListener("focus", refresh);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, []);

  useEffect(() => {
    if (!chatgptOpening && !grokOpening) return;
    const started = Date.now();
    const timer = window.setInterval(() => {
      void readProviders().then((status) => {
        setProviders(status);
        if (chatgptOpening && status?.chatgpt_web_authed) {
          setChatgptOpening(false);
          setChatgptMessage("Đã lưu phiên ChatGPT. Mở cửa sổ để chỉnh nội dung trên hội thoại hôm nay.");
        }
        if (grokOpening && status?.grok_hub_authed) {
          setGrokOpening(false);
          setGrokMessage("Đã lưu phiên Grok.");
        }
        if (Date.now() - started > 10 * 60 * 1000) {
          setChatgptOpening(false);
          setGrokOpening(false);
        }
      });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [chatgptOpening, grokOpening]);

  const attachmentCounts = useMemo(() => {
    const kinds = new Map<string, number>();
    for (const row of attachments) kinds.set(row.kind, (kinds.get(row.kind) ?? 0) + 1);
    return Array.from(kinds.entries()).sort(([left], [right]) => left.localeCompare(right));
  }, [attachments]);

  return (
    <section className="page-stack account-page">
      <PageHeader
        kicker="Tài khoản"
        title={user?.display_name || user?.email || "Account"}
        lede={user ? `${user.email} · ${user.role}` : "Phiên đăng nhập hiện tại"}
      />

      <div className="hub-grid">
        <section className="panel hub-card">
          <div className="section-head compact">
            <div>
              <p className="kicker">Content</p>
              <h2>ChatGPT</h2>
            </div>
            <StatusPill
              label={providers?.chatgpt_web_authed ? "ready" : chatgptOpening ? "opening" : "off"}
              tone={providers?.chatgpt_web_authed ? "done" : "idle"}
            />
          </div>
          <p className="meta">
            Phiên này viết lời Knowledge. Đăng nhập một lần, rồi mở hội thoại trong ngày để chỉnh nội dung trước khi dựng video.
          </p>
          <div className="hub-actions">
            <button
              type="button"
              className={providers?.chatgpt_web_authed ? "ghost" : undefined}
              disabled={chatgptOpening}
              onClick={() => {
                setChatgptMessage(null);
                setChatgptOpening(true);
                void startChatgptLogin()
                  .then(() => {
                    setChatgptMessage("Chrome đang mở trang đăng nhập ChatGPT. Đăng nhập ở cửa sổ đó. Cửa sổ đóng khi tài khoản đã lưu.");
                  })
                  .catch((err) => {
                    setChatgptOpening(false);
                    setChatgptMessage(err instanceof Error ? err.message : "Không mở được ChatGPT");
                  });
              }}
            >
              {chatgptOpening ? "Đang chờ ChatGPT…" : providers?.chatgpt_web_authed ? "Đăng nhập lại" : "Đăng nhập ChatGPT"}
            </button>
            {providers?.chatgpt_web_authed ? (
              <button
                type="button"
                disabled={chatgptOpening}
                onClick={() => {
                  setChatgptMessage(null);
                  void openChatgptContent()
                    .then(() => setChatgptMessage("Chrome đang mở hội thoại hôm nay. Chỉnh nội dung, rồi đóng cửa sổ."))
                    .catch((err) => setChatgptMessage(err instanceof Error ? err.message : "Không mở được ChatGPT"));
                }}
              >
                Mở để chỉnh nội dung
              </button>
            ) : null}
          </div>
          {providers?.chatgpt_web_chat ? <p className="meta">Hội thoại hôm nay đã có. Cửa sổ hub mở đúng phiên đó.</p> : null}
          {chatgptMessage ? <p className="meta">{chatgptMessage}</p> : null}
        </section>

        <section className="panel hub-card">
          <div className="section-head compact">
            <div>
              <p className="kicker">Motion</p>
              <h2>Grok</h2>
            </div>
            <StatusPill
              label={providers?.grok_hub_authed ? "ready" : grokOpening ? "opening" : "off"}
              tone={providers?.grok_hub_authed ? "done" : "idle"}
            />
          </div>
          <p className="meta">
            Phiên này chỉ cho drama chuyển động. Ảnh vẫn đi qua API key của Gemini hoặc xAI, không đăng nhập gemini.google.com.
          </p>
          <div className="hub-actions">
            <button
              type="button"
              className={providers?.grok_hub_authed ? "ghost" : undefined}
              disabled={grokOpening}
              onClick={() => {
                setGrokMessage(null);
                setGrokOpening(true);
                void startGrokLogin()
                  .then(() => setGrokMessage("Chrome đang mở grok.com/imagine. Đăng nhập ở cửa sổ đó. Phiên lưu khi cookie SSO xuất hiện."))
                  .catch((err) => {
                    setGrokOpening(false);
                    setGrokMessage(err instanceof Error ? err.message : "Không mở được Grok");
                  });
              }}
            >
              {grokOpening ? "Đang chờ Grok…" : providers?.grok_hub_authed ? "Đăng nhập lại" : "Đăng nhập Grok"}
            </button>
          </div>
          {providers?.grok_hub_authed ? <p className="meta">Đã đăng nhập. Drama sẽ dựng chuyển động qua Grok.</p> : null}
          {providers?.image?.gemini ? <p className="meta">Gemini API đã có key.</p> : <p className="meta">Gemini: đặt GEMINI_API_KEY. Không có cửa sổ đăng nhập.</p>}
          {grokMessage ? <p className="meta">{grokMessage}</p> : null}
        </section>

        <section className="panel hub-card">
          <div className="section-head compact">
            <div>
              <p className="kicker">Voice</p>
              <h2>ElevenLabs</h2>
            </div>
            <StatusPill label={eleven?.enabled ? "on" : eleven?.configured ? "saved" : "off"} tone={eleven?.enabled ? "done" : "idle"} />
          </div>
          <p className="meta">
            Giọng công khai giống videoai: không cần API key. Lúc dựng video, Chrome mở một lần để xác minh. Có khóa thì chuyển sang API.
          </p>
          <label>
            Cách đọc
            <select
              value={elevenMode}
              onChange={(event) => {
                const next = event.target.value === "api" ? "api" : "anonymous";
                setElevenMode(next);
                if (next === "anonymous" && !voiceId) setVoiceId("aN7cv9yXNrfIR87bDmyD");
              }}
            >
              <option value="anonymous">Giọng công khai</option>
              <option value="api">API key</option>
            </select>
          </label>
          {elevenMode === "api" ? (
            <label>
              API key
              <input
                type="password"
                autoComplete="off"
                value={apiKey}
                placeholder={eleven?.key_hint ? `Đã lưu ${eleven.key_hint}` : "xi-api-key"}
                onChange={(event) => setApiKey(event.target.value)}
              />
            </label>
          ) : (
            <p className="meta">Chọn một giọng trong danh sách, hoặc dán Voice ID bất kỳ. Lúc dựng video Chrome hỏi xác minh một lần.</p>
          )}
          <label>
            Giọng
            <select
              value={(eleven?.voices ?? []).some((voice) => voice.id === voiceId) ? voiceId : ""}
              onChange={(event) => {
                if (event.target.value) setVoiceId(event.target.value);
              }}
            >
              <option value="">Giọng khác (dán ID bên dưới)</option>
              {(eleven?.voices ?? []).map((voice) => (
                <option key={voice.id} value={voice.id}>
                  {voice.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Voice ID
            <input value={voiceId} autoComplete="off" spellCheck={false} onChange={(event) => setVoiceId(event.target.value.trim())} />
          </label>
          <label>
            Model
            <select value={modelId} onChange={(event) => setModelId(event.target.value)}>
              <option value="eleven_v3">eleven_v3</option>
              <option value="eleven_multilingual_v2">eleven_multilingual_v2</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={elevenEnabled} onChange={(event) => setElevenEnabled(event.target.checked)} />
            Dùng ElevenLabs cho lời thoại
          </label>
          <div className="hub-actions">
            <button
              type="button"
              disabled={hubBusy || (elevenMode === "api" && elevenEnabled && !apiKey.trim() && !eleven?.configured) || (elevenEnabled && !voiceId)}
              onClick={() => {
                setHubBusy(true);
                setHubMessage(null);
                const body: {
                  api_key?: string;
                  voice_id?: string;
                  enabled?: boolean;
                  mode?: "anonymous" | "api";
                  model_id?: string;
                } = {
                  mode: elevenMode,
                  voice_id: voiceId || (elevenMode === "anonymous" ? "aN7cv9yXNrfIR87bDmyD" : ""),
                  model_id: modelId,
                  enabled: elevenEnabled,
                };
                if (elevenMode === "api" && apiKey.trim()) body.api_key = apiKey.trim();
                void saveElevenLabs(body)
                  .then((hub) => {
                    setEleven(hub);
                    setVoiceId(hub.voice_id || voiceId);
                    setModelId(hub.model_id || modelId);
                    setElevenEnabled(hub.enabled);
                    setElevenMode(hub.mode === "api" ? "api" : "anonymous");
                    setApiKey("");
                    setHubMessage(
                      hub.enabled && hub.mode !== "api"
                        ? "Đã bật giọng công khai. Lần đọc tới Chrome sẽ hỏi xác minh."
                        : hub.enabled
                          ? "Đã bật ElevenLabs."
                          : "Đã lưu hub ElevenLabs.",
                    );
                  })
                  .catch((err) => setHubMessage(err instanceof Error ? err.message : "Không lưu được ElevenLabs"))
                  .finally(() => setHubBusy(false));
              }}
            >
              {hubBusy ? "Đang lưu…" : "Lưu hub"}
            </button>
            {eleven?.configured ? (
              <button
                type="button"
                className="ghost"
                disabled={hubBusy}
                onClick={() => {
                  setHubBusy(true);
                  setHubMessage(null);
                  void saveElevenLabs({ api_key: "", enabled: false })
                    .then((hub) => {
                      setEleven(hub);
                      setVoiceId("");
                      setElevenEnabled(false);
                      setApiKey("");
                      setHubMessage("Đã gỡ khóa ElevenLabs trên máy này.");
                    })
                    .catch((err) => setHubMessage(err instanceof Error ? err.message : "Không gỡ được khóa"))
                    .finally(() => setHubBusy(false));
                }}
              >
                Gỡ khóa
              </button>
            ) : null}
          </div>
          {hubMessage ? <p className="meta">{hubMessage}</p> : null}
          {eleven?.error ? <p className="err">{eleven.error}</p> : null}
        </section>
      </div>

      <div className="counter-grid">
        <CounterCard label="Attachments" value={attachments.length} hint="File trong thư viện" />
        <CounterCard label="Loại file" value={attachmentCounts.length} hint="face, logo, script, editorial" />
        <CounterCard label="Providers" value={providers ? chips(providers).filter((chip) => chip.on).length : 0} hint="Đang sẵn sàng" />
        <CounterCard label="Motion" value={providers?.drama_motion && providers.drama_motion !== "kenburns" ? 1 : 0} hint={providers?.drama_motion || "kenburns"} />
      </div>

      <div className="account-grid">
        <section className="panel">
          <div className="section-head compact">
            <div>
              <p className="kicker">Providers</p>
              <h2>Readiness</h2>
            </div>
          </div>
          {providers ? (
            <div className="provider-card-grid">
              {chips(providers).map((chip) => (
                <article key={chip.id} className="provider-tile">
                  <StatusPill label={chip.on ? "ready" : "off"} tone={chip.on ? "done" : "idle"} />
                  <strong>{chip.label}</strong>
                </article>
              ))}
            </div>
          ) : (
            <p className="meta">Đang đọc provider…</p>
          )}
          <p className="meta">ChatGPT viết lời Knowledge. Grok hub chỉ chuyển động drama. Gemini là API key.</p>
        </section>

        <section className="panel">
          <div className="section-head compact">
            <div>
              <p className="kicker">Library</p>
              <h2>Attachment library</h2>
            </div>
          </div>
          {attachmentCounts.length ? (
            <div className="provider-row">
              {attachmentCounts.map(([kind, count]) => (
                <StatusPill key={kind} label={`${kind} ${count}`} tone="accent" />
              ))}
            </div>
          ) : null}
          {attachments.length ? (
            <div className="attachment-table-wrap">
              <table className="job-table attachment-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Kind</th>
                    <th>Size</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {attachments.map((row) => (
                    <tr key={row.id}>
                      <td>
                        <strong>{row.filename}</strong>
                        <span>{row.mime}</span>
                      </td>
                      <td>{row.kind}</td>
                      <td>{formatBytes(row.byte_size)}</td>
                      <td>{formatDate(row.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="meta">Chưa có attachment. Tải file từ trang Drama, News hoặc Knowledge.</p>
          )}
        </section>
      </div>
    </section>
  );
}
