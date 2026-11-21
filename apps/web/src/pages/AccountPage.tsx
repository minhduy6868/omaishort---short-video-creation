import { useEffect, useMemo, useState } from "react";
import {
  checkChatgptSession,
  checkoutPlan,
  deleteAttachment,
  listAttachments,
  listBillingPlans,
  openChatgptContent,
  readBillingMe,
  readElevenLabs,
  readMe,
  readProviders,
  saveElevenLabs,
  startChatgptLogin,
  startGrokLogin,
  startMuseLogin,
  type AttachmentRow,
  type BillingMe,
  type BillingPlan,
  type ElevenLabsHub,
  type ProviderStatus,
} from "../api";
import { CounterCard, PageHeader, StatusPill } from "../components";
import { useNav } from "../nav";
import { useSession } from "../session";

function formatVnd(amount: number): string {
  return new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND", maximumFractionDigits: 0 }).format(amount);
}

function chips(status: ProviderStatus): { id: string; on: boolean; label: string }[] {
  const image = status.image ?? {};
  const video = status.video ?? {};
  const motion = status.drama_motion ?? "kenburns";
  return [
    { id: "chatgpt", on: Boolean(status.chatgpt_web_authed), label: status.chatgpt_web_authed ? "ChatGPT ready" : "ChatGPT off" },
    { id: "muse", on: Boolean(status.muse_hub_authed), label: status.muse_hub_authed ? "Muse hub" : "Muse hub off" },
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

function ledgerReasonLabel(reason: string): string {
  switch (reason) {
    case "trial_grant":
      return "Tặng dùng thử";
    case "job_hold":
      return "Tạo video";
    case "job_refund":
      return "Hoàn credit";
    case "plan_activate":
      return "Kích hoạt gói";
    case "admin_grant":
      return "Admin cộng thêm";
    default:
      return reason;
  }
}

export function AccountPage() {
  const { go } = useNav();
  const { user, setUser } = useSession();
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [attachments, setAttachments] = useState<AttachmentRow[]>([]);
  const [billingMe, setBillingMe] = useState<BillingMe | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [billingBusy, setBillingBusy] = useState(false);
  const [billingMessage, setBillingMessage] = useState<string | null>(null);
  const [chatgptOpening, setChatgptOpening] = useState(false);
  const [chatgptChecking, setChatgptChecking] = useState(false);
  const [chatgptMessage, setChatgptMessage] = useState<string | null>(null);
  const [grokOpening, setGrokOpening] = useState(false);
  const [grokMessage, setGrokMessage] = useState<string | null>(null);
  const [museOpening, setMuseOpening] = useState(false);
  const [museMessage, setMuseMessage] = useState<string | null>(null);
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
    void readBillingMe()
      .then(setBillingMe)
      .catch((err) => setBillingMessage(err instanceof Error ? err.message : "Không đọc được gói"));
    void listBillingPlans()
      .then((data) => setPlans(data.plans.filter((p) => p.code !== "trial" || p.price_vnd === 0)))
      .catch(() => undefined);
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
    if (!chatgptOpening && !grokOpening && !museOpening) return;
    const started = Date.now();
    const timer = window.setInterval(() => {
      void readProviders().then((status) => {
        setProviders(status);
        if (chatgptOpening && !status?.chatgpt_opening) {
          setChatgptOpening(false);
          setChatgptMessage(
            status?.chatgpt_web_authed
              ? "Đã lưu phiên ChatGPT. Mở cửa sổ để chỉnh nội dung trên hội thoại hôm nay."
              : "Đã đóng cửa sổ ChatGPT. Bấm Đăng nhập ChatGPT nếu chưa hoàn tất.",
          );
        }
        if (museOpening && !status?.muse_opening) {
          setMuseOpening(false);
          setMuseMessage(
            status?.muse_hub_authed
              ? "Đã lưu phiên Muse."
              : "Đã đóng cửa sổ Muse. Bấm Đăng nhập Muse nếu chưa hoàn tất.",
          );
        }
        if (grokOpening && !status?.grok_opening) {
          setGrokOpening(false);
          setGrokMessage(
            status?.grok_hub_authed
              ? "Đã lưu phiên Grok."
              : "Đã đóng cửa sổ Grok. Bấm Đăng nhập Grok nếu chưa hoàn tất.",
          );
        }
        if (Date.now() - started > 10 * 60 * 1000) {
          setChatgptOpening(false);
          setGrokOpening(false);
          setMuseOpening(false);
        }
      });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [chatgptOpening, grokOpening, museOpening]);

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
        actions={
          user?.role === "operator" ? (
            <button type="button" onClick={() => go("/admin")}>
              Mở trang Quản trị
            </button>
          ) : undefined
        }
      />

      <section className="panel">
        <div className="section-head compact">
          <div>
            <p className="kicker">Gói & credit</p>
            <h2>Dùng thử và nâng cấp</h2>
          </div>
          <StatusPill
            label={billingMe?.billing?.status || (user?.role === "operator" ? "operator" : "none")}
            tone={billingMe?.billing && billingMe.billing.credits_remaining > 0 ? "done" : "idle"}
          />
        </div>
        {user?.role === "operator" ? (
          <p className="meta">Tài khoản operator không bị trừ credit khi tạo job.</p>
        ) : (
          <>
            <div className="hub-grid">
              <CounterCard
                label="Credit còn"
                value={billingMe?.billing?.credits_remaining ?? user?.billing?.credits_remaining ?? 0}
                hint={billingMe?.billing?.plan_code || user?.billing?.plan_code || "chưa có gói"}
              />
              <CounterCard
                label="Tổng credit gói"
                value={billingMe?.billing?.credits_total ?? user?.billing?.credits_total ?? 0}
                hint={
                  billingMe?.billing?.ends_at
                    ? `Hết hạn ${formatDate(billingMe.billing.ends_at)}`
                    : user?.billing?.ends_at
                      ? `Hết hạn ${formatDate(user.billing.ends_at)}`
                      : "—"
                }
              />
            </div>
            {billingMe?.pending_order ? (
              <p className="meta">
                Đơn <code>{billingMe.pending_order.id}</code> · {billingMe.pending_order.plan_code} ·{" "}
                {formatVnd(billingMe.pending_order.amount_vnd)} đang chờ admin duyệt.{" "}
                {billingMe.transfer_note}
              </p>
            ) : (
              <p className="meta">{billingMe?.transfer_note}</p>
            )}
            <div className="job-table-wrap">
              <table className="job-table">
                <thead>
                  <tr>
                    <th>Gói</th>
                    <th>Credit</th>
                    <th>Thời hạn</th>
                    <th>Giá</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {plans
                    .filter((p) => p.active && p.code !== "trial")
                    .map((plan) => (
                      <tr key={plan.code}>
                        <td>
                          <strong>{plan.name}</strong>
                        </td>
                        <td>{plan.credits}</td>
                        <td>{plan.period_days} ngày</td>
                        <td>{formatVnd(plan.price_vnd)}</td>
                        <td>
                          <button
                            type="button"
                            className="ghost"
                            disabled={billingBusy || Boolean(billingMe?.pending_order)}
                            onClick={() => {
                              setBillingBusy(true);
                              setBillingMessage(null);
                              void checkoutPlan(plan.code)
                                .then(async (result) => {
                                  setBillingMessage(
                                    `Đã tạo đơn ${result.order.id}. ${result.transfer_note}`,
                                  );
                                  const me = await readBillingMe();
                                  setBillingMe(me);
                                  const fresh = await readMe();
                                  if (fresh) setUser(fresh);
                                })
                                .catch((err) =>
                                  setBillingMessage(err instanceof Error ? err.message : "Không tạo được đơn"),
                                )
                                .finally(() => setBillingBusy(false));
                            }}
                          >
                            Đăng ký gói
                          </button>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
            {billingMessage ? <p className="meta">{billingMessage}</p> : null}
            {billingMe?.ledger && billingMe.ledger.length > 0 ? (
              <div className="ledger-block">
                <p className="card-title">Lịch sử biến động credit</p>
                <div className="attachment-table-wrap">
                  <table className="job-table attachment-table">
                    <thead>
                      <tr>
                        <th>Lý do</th>
                        <th>Thay đổi</th>
                        <th>Ghi chú / Job</th>
                        <th>Thời gian</th>
                      </tr>
                    </thead>
                    <tbody>
                      {billingMe.ledger.slice(0, 10).map((row) => (
                        <tr key={row.id}>
                          <td><span className="table-badge">{ledgerReasonLabel(row.reason)}</span></td>
                          <td>
                            <strong className={row.delta >= 0 ? "delta-pos" : "delta-neg"}>
                              {row.delta >= 0 ? `+${row.delta}` : row.delta}
                            </strong>
                          </td>
                          <td>{row.job_id || row.note || "—"}</td>
                          <td>{formatDate(row.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </>
        )}
      </section>

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
              disabled={chatgptOpening || chatgptChecking}
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
            <button
              type="button"
              className="ghost"
              disabled={chatgptOpening || chatgptChecking}
              onClick={() => {
                setChatgptChecking(true);
                setChatgptMessage("Đang kiểm tra kết nối trực tiếp tới ChatGPT…");
                void checkChatgptSession()
                  .then((res) => {
                    setChatgptMessage(res.message);
                    void readProviders().then(setProviders);
                  })
                  .catch((err) => setChatgptMessage(err instanceof Error ? err.message : "Không kiểm tra được ChatGPT"))
                  .finally(() => setChatgptChecking(false));
              }}
            >
              {chatgptChecking ? "Đang kiểm tra…" : "Kiểm tra ChatGPT thật"}
            </button>
            {providers?.chatgpt_web_authed ? (
              <button
                type="button"
                disabled={chatgptOpening || chatgptChecking}
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
              <h2>Muse</h2>
            </div>
            <StatusPill
              label={
                providers?.muse_hub_authed
                  ? "ready"
                  : providers?.muse_hub_challenge
                    ? "challenge"
                    : museOpening
                      ? "opening"
                      : "off"
              }
              tone={providers?.muse_hub_authed ? "done" : providers?.muse_hub_challenge ? "running" : "idle"}
            />
          </div>
          <p className="meta">
            Browser Hub Muse (giống videoai): Chrome persistent profile → đăng nhập / Meta checkpoint → Hatch session.
            Drama I2V ưu tiên Muse khi hub ready.
          </p>
          <div className="hub-actions">
            <button
              type="button"
              className={providers?.muse_hub_authed ? "ghost" : undefined}
              disabled={museOpening}
              onClick={() => {
                setMuseMessage(null);
                setMuseOpening(true);
                void startMuseLogin()
                  .then(() =>
                    setMuseMessage(
                      "Chrome hub Muse đang mở. Đăng nhập Meta và vượt checkpoint nếu có. Phiên lưu khi Hatch gateway sẵn sàng.",
                    ),
                  )
                  .catch((err) => {
                    setMuseOpening(false);
                    setMuseMessage(err instanceof Error ? err.message : "Không mở được Muse");
                  });
              }}
            >
              {museOpening
                ? "Đang chờ Muse…"
                : providers?.muse_hub_challenge
                  ? "Mở hub (checkpoint)"
                  : providers?.muse_hub_authed
                    ? "Đăng nhập lại"
                    : "Đăng nhập Muse"}
            </button>
          </div>
          {providers?.muse_hub_authed ? <p className="meta">Hub ready. Drama sẽ dựng chuyển động qua Muse trước.</p> : null}
          {providers?.muse_hub_challenge ? (
            <p className="meta">
              Meta đang yêu cầu checkpoint
              {providers.muse_hub_checkpoint ? ` — ${providers.muse_hub_checkpoint}` : ""}. Bấm nút để mở hub và hoàn tất.
            </p>
          ) : null}
          {museMessage ? <p className="meta">{museMessage}</p> : null}
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
                    <th></th>
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
                      <td>
                        <button
                          type="button"
                          className="ghost"
                          onClick={() => {
                            void deleteAttachment(row.id)
                              .then(() => setAttachments((prev) => prev.filter((item) => item.id !== row.id)))
                              .catch((err) =>
                                setBillingMessage(err instanceof Error ? err.message : "Không xóa được file"),
                              );
                          }}
                        >
                          Xóa
                        </button>
                      </td>
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
