import { useCallback, useEffect, useState } from "react";
import {
  cleanupAdminStorage,
  compactJobStorage,
  deleteAdminJob,
  listAdminJobs,
  listAdminUsers,
  openChatgptContent,
  patchAdminUser,
  readAdminOverview,
  readAdminStorage,
  readProviders,
  retryAdminJob,
  saveAdminSettings,
  startChatgptLogin,
  startGrokLogin,
  type AdminOverview,
  type AdminUserRow,
  type LocalVideoEntry,
  type ProviderStatus,
  type StorageSummary,
} from "../api";
import {
  CounterCard,
  PageHeader,
  ProgressBar,
  StatusPill,
  progressCopy,
  progressFromJob,
  stageLabel,
  toneForStatus,
} from "../components";
import { useNav } from "../nav";
import { useSession } from "../session";
import { SiteThemePicker } from "../theme";
import type { Job } from "../types";

type AdminTab = "overview" | "users" | "jobs" | "storage";

const TABS: { id: AdminTab; label: string }[] = [
  { id: "overview", label: "Tổng quan & Cloudflare" },
  { id: "users", label: "Người dùng" },
  { id: "jobs", label: "Toàn bộ Job" },
  { id: "storage", label: "Lưu trữ Video Local" },
];

const JOB_FILTERS: { id: string; label: string }[] = [
  { id: "all", label: "Tất cả" },
  { id: "running", label: "Đang chạy" },
  { id: "done", label: "Đã xong" },
  { id: "failed", label: "Lỗi" },
];

function formatBytes(bytes?: number): string {
  const val = bytes ?? 0;
  if (val < 1024) return `${val} B`;
  if (val < 1024 * 1024) return `${(val / 1024).toFixed(1)} KB`;
  return `${(val / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(value?: string | null): string {
  if (!value) return "Chưa có";
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

function jobKind(job: Job): string {
  return job.storyboard?.kind || (typeof job.input?.kind === "string" ? job.input.kind : "drama");
}

function jobTitle(job: Job): string {
  return job.storyboard?.title || (typeof job.input?.genre === "string" ? `${jobKind(job)} · ${job.input.genre}` : job.id);
}

export function AdminPage() {
  const { user } = useSession();
  const { go } = useNav();
  const [tab, setTab] = useState<AdminTab>("overview");
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [users, setUsers] = useState<AdminUserRow[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [jobFilter, setJobFilter] = useState<string>("all");
  const [storageData, setStorageData] = useState<{ summary: StorageSummary; videos: LocalVideoEntry[] } | null>(null);
  const [providers, setProviders] = useState<ProviderStatus | null>(null);
  const [chatgptOpening, setChatgptOpening] = useState(false);
  const [grokOpening, setGrokOpening] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isOperator = user?.role === "operator";

  const refreshAll = useCallback(async () => {
    if (!isOperator) return;
    setError(null);
    try {
      const [ov, usr, jb, st, prov] = await Promise.all([
        readAdminOverview(),
        listAdminUsers(),
        listAdminJobs(),
        readAdminStorage(),
        readProviders(),
      ]);
      setOverview(ov);
      setUsers(usr);
      setJobs(jb);
      setStorageData(st);
      setProviders(prov);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu quản trị");
    }
  }, [isOperator]);

  useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  useEffect(() => {
    if (!chatgptOpening && !grokOpening) return;
    const timer = window.setInterval(() => {
      void readProviders().then((status) => {
        setProviders(status);
        if (chatgptOpening && !status?.chatgpt_opening) {
          setChatgptOpening(false);
          setMessage(
            status?.chatgpt_web_authed
              ? "Đã lưu phiên ChatGPT."
              : "Đã đóng cửa sổ ChatGPT. Bấm Đăng nhập ChatGPT nếu chưa hoàn tất.",
          );
        }
        if (grokOpening && !status?.grok_opening) {
          setGrokOpening(false);
          setMessage(
            status?.grok_hub_authed
              ? "Đã lưu phiên Grok."
              : "Đã đóng cửa sổ Grok. Bấm Đăng nhập Grok nếu chưa hoàn tất.",
          );
        }
      });
    }, 2000);
    return () => window.clearInterval(timer);
  }, [chatgptOpening, grokOpening]);

  if (!isOperator) {
    return (
      <section className="page-stack">
        <PageHeader
          kicker="Admin Console"
          title="Khu vực Quản trị"
          lede="Chỉ tài khoản Admin (operator) mới có quyền truy cập trang quản trị hệ thống."
        />
        <section className="panel">
          <p className="err">Tài khoản hiện tại ({user?.email}) có quyền creator, không có quyền truy cập Admin Console.</p>
        </section>
      </section>
    );
  }

  const stats = overview?.stats;
  const storageSummary = storageData?.summary ?? overview?.storage;
  const filteredJobs = jobs.filter((job) => {
    if (jobFilter === "all") return true;
    if (jobFilter === "running") return job.status !== "done" && job.status !== "failed";
    return job.status === jobFilter;
  });

  return (
    <section className="page-stack admin-page">
      <PageHeader
        kicker="System Administration"
        title="Quản trị Hệ thống"
        lede="Quản lý tài khoản trên Cloudflare D1, giám sát hàng đợi toàn hệ thống và quản lý kho lưu trữ video MP4 local."
        actions={
          <button type="button" className="ghost" disabled={busy} onClick={() => void refreshAll()}>
            Làm mới dữ liệu
          </button>
        }
      />

      <div className="counter-grid">
        <CounterCard
          label="Người dùng (D1)"
          value={stats?.users_total ?? 0}
          hint={`${stats?.operators_total ?? 1} operator · Cloudflare ${stats?.db_backend ?? "d1"}`}
        />
        <CounterCard
          label="Tổng số Job"
          value={stats?.jobs_total ?? 0}
          hint={`${stats?.jobs_by_status?.done ?? 0} xong · ${stats?.jobs_by_status?.failed ?? 0} lỗi`}
        />
        <CounterCard
          label="Video MP4 Local"
          value={storageSummary?.mp4_count ?? 0}
          hint={`${formatBytes(storageSummary?.mp4_bytes)} MP4 trên đĩa`}
        />
        <CounterCard
          label="Thư mục Job Local"
          value={storageSummary?.job_dirs_count ?? 0}
          hint={`${formatBytes(storageSummary?.total_local_bytes)} · ${stats?.attachments_total ?? 0} attachments`}
        />
      </div>

      <section className="panel">
        <div className="section-head">
          <div>
            <p className="kicker">Console</p>
            <h2>Phân hệ quản trị</h2>
          </div>
          <div className="segmented" role="tablist" aria-label="Phân hệ quản trị">
            {TABS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                aria-selected={tab === item.id}
                className={tab === item.id ? "on" : ""}
                onClick={() => {
                  setTab(item.id);
                  setMessage(null);
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
        {message ? <p className="meta">{message}</p> : null}
        {error ? <p className="err">{error}</p> : null}
      </section>

      {tab === "overview" ? (
        <div className="account-grid">
          <section className="panel">
            <div className="section-head compact">
              <div>
                <p className="kicker">Cloudflare Settings</p>
                <h2>Cấu hình toàn hệ thống</h2>
                <p className="panel-subtitle">Lưu trữ đồng bộ trong bảng settings trên Cloudflare D1.</p>
              </div>
            </div>
            <SiteThemePicker editable />
            <div className="hub-actions" style={{ marginTop: "16px" }}>
              <label className="check">
                <input
                  type="checkbox"
                  checked={overview?.settings?.signup_enabled ?? true}
                  disabled={busy}
                  onChange={(event) => {
                    const next = event.target.checked;
                    setBusy(true);
                    void saveAdminSettings({ signup_enabled: next })
                      .then((saved) => {
                        setOverview((prev) => (prev ? { ...prev, settings: saved } : prev));
                        setMessage(next ? "Đã mở đăng ký tài khoản mới." : "Đã khóa đăng ký tài khoản mới.");
                      })
                      .catch((err) => setError(err instanceof Error ? err.message : "Lỗi cập nhật cài đặt"))
                      .finally(() => setBusy(false));
                  }}
                />
                Cho phép người dùng mới tự đăng ký tài khoản (`/register`)
              </label>
            </div>
          </section>

          <section className="panel">
            <div className="section-head compact">
              <div>
                <p className="kicker">Architecture</p>
                <h2>Cloudflare D1 & Local Storage</h2>
                <p className="panel-subtitle">
                  Database, tài khoản, lịch sử job và attachment lưu trên Cloudflare; file video MP4 lưu tại ổ đĩa máy chủ render.
                </p>
              </div>
            </div>
            <div className="provider-card-grid">
              <article className="provider-tile">
                <StatusPill label="active" tone="done" />
                <strong>DB: {stats?.db_backend || "cloudflare-d1"}</strong>
              </article>
              <article className="provider-tile">
                <StatusPill label={overview?.settings?.signup_enabled ? "open" : "closed"} tone={overview?.settings?.signup_enabled ? "done" : "idle"} />
                <strong>Signup: {overview?.settings?.signup_enabled ? "Mở" : "Đóng"}</strong>
              </article>
              <article className="provider-tile">
                <StatusPill label={`${storageSummary?.mp4_count ?? 0} MP4`} tone="accent" />
                <strong>Local MP4: {formatBytes(storageSummary?.mp4_bytes)}</strong>
              </article>
              <article className="provider-tile">
                <StatusPill label={`${stats?.attachments_total ?? 0} files`} tone="done" />
                <strong>Attachments: {formatBytes(stats?.attachments_bytes)}</strong>
              </article>
            </div>
            <p className="meta" style={{ marginTop: "12px" }}>
              Thư mục lưu trữ video local: <code>{storageSummary?.data_dir || "data/"}</code>
            </p>
            <div className="hub-actions" style={{ marginTop: "16px" }}>
              <button
                type="button"
                className={providers?.chatgpt_web_authed ? "ghost" : undefined}
                disabled={chatgptOpening}
                onClick={() => {
                  setError(null);
                  setChatgptOpening(true);
                  void startChatgptLogin()
                    .then(() => setMessage("Chrome đang mở ChatGPT. Đăng nhập trên cửa sổ đó."))
                    .catch((err) => {
                      setChatgptOpening(false);
                      setError(err instanceof Error ? err.message : "Không mở được ChatGPT");
                    });
                }}
              >
                {chatgptOpening ? "Đang chờ ChatGPT…" : providers?.chatgpt_web_authed ? "ChatGPT: Đăng nhập lại" : "Đăng nhập ChatGPT"}
              </button>
              {providers?.chatgpt_web_authed ? (
                <button
                  type="button"
                  className="ghost"
                  disabled={chatgptOpening}
                  onClick={() => {
                    void openChatgptContent()
                      .then(() => setMessage("Đã mở cửa sổ hội thoại ChatGPT hôm nay."))
                      .catch((err) => setError(err instanceof Error ? err.message : "Không mở được ChatGPT"));
                  }}
                >
                  Mở ChatGPT hôm nay
                </button>
              ) : null}
              <button
                type="button"
                className={providers?.grok_hub_authed ? "ghost" : undefined}
                disabled={grokOpening}
                onClick={() => {
                  setError(null);
                  setGrokOpening(true);
                  void startGrokLogin()
                    .then(() => setMessage("Chrome đang mở grok.com/imagine. Đăng nhập trên cửa sổ đó."))
                    .catch((err) => {
                      setGrokOpening(false);
                      setError(err instanceof Error ? err.message : "Không mở được Grok");
                    });
                }}
              >
                {grokOpening ? "Đang chờ Grok…" : providers?.grok_hub_authed ? "Grok: Đăng nhập lại" : "Đăng nhập Grok"}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {tab === "users" ? (
        <section className="panel">
          <div className="section-head">
            <div>
              <p className="kicker">Cloudflare D1 Users</p>
              <h2>Quản lý Người dùng ({users.length})</h2>
              <p className="panel-subtitle">Phân quyền operator/creator, mở khóa hoặc khóa tài khoản và thu hồi phiên đăng nhập.</p>
            </div>
          </div>
          <div className="job-table-wrap">
            <table className="job-table">
              <thead>
                <tr>
                  <th>Người dùng</th>
                  <th>Vai trò</th>
                  <th>Trạng thái</th>
                  <th>Số Job</th>
                  <th>Attachments</th>
                  <th>Ngày tạo</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {users.map((row) => {
                  const isSelf = row.id === user?.id;
                  return (
                    <tr key={row.id}>
                      <td>
                        <strong>{row.display_name || row.email}</strong>
                        <div>
                          <span>{row.email}</span>
                        </div>
                      </td>
                      <td>
                        <span className="table-badge">{row.role}</span>
                      </td>
                      <td>
                        <StatusPill label={row.locked ? "locked" : "active"} tone={row.locked ? "failed" : "done"} />
                      </td>
                      <td>{row.jobs_count}</td>
                      <td>
                        {row.attachments_count} ({formatBytes(row.attachments_bytes)})
                      </td>
                      <td>{formatDate(row.created_at)}</td>
                      <td>
                        <div className="hub-actions">
                          <button
                            type="button"
                            className="ghost"
                            disabled={busy || (isSelf && row.role === "operator" && (stats?.operators_total ?? 1) <= 1)}
                            onClick={() => {
                              const nextRole = row.role === "operator" ? "creator" : "operator";
                              setBusy(true);
                              void patchAdminUser(row.id, { role: nextRole })
                                .then(() => {
                                  setMessage(`Đã đổi quyền ${row.email} sang ${nextRole}.`);
                                  return refreshAll();
                                })
                                .catch((err) => setError(err instanceof Error ? err.message : "Lỗi đổi quyền"))
                                .finally(() => setBusy(false));
                            }}
                          >
                            {row.role === "operator" ? "Hạ xuống Creator" : "Nâng lên Admin"}
                          </button>
                          {!isSelf ? (
                            <button
                              type="button"
                              className="ghost"
                              disabled={busy}
                              onClick={() => {
                                setBusy(true);
                                void patchAdminUser(row.id, { locked: !row.locked })
                                  .then(() => {
                                    setMessage(row.locked ? `Đã mở khóa ${row.email}.` : `Đã khóa ${row.email}.`);
                                    return refreshAll();
                                  })
                                  .catch((err) => setError(err instanceof Error ? err.message : "Lỗi khóa/mở khóa"))
                                  .finally(() => setBusy(false));
                              }}
                            >
                              {row.locked ? "Mở khóa" : "Khóa"}
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {tab === "jobs" ? (
        <section className="panel">
          <div className="section-head">
            <div>
              <p className="kicker">Global Job Queue</p>
              <h2>Toàn bộ Công việc ({filteredJobs.length})</h2>
              <p className="panel-subtitle">Giám sát mọi job của người dùng và CLI, chạy lại job lỗi hoặc xóa job.</p>
            </div>
            <div className="segmented" aria-label="Lọc trạng thái job">
              {JOB_FILTERS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={jobFilter === item.id ? "on" : ""}
                  onClick={() => setJobFilter(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {filteredJobs.length === 0 ? (
            <p className="meta">Không có job nào trong bộ lọc này.</p>
          ) : (
            <div className="job-table-wrap">
              <table className="job-table">
                <thead>
                  <tr>
                    <th>Job</th>
                    <th>Người tạo</th>
                    <th>Định dạng</th>
                    <th>Bước</th>
                    <th>Trạng thái</th>
                    <th>Tiến độ</th>
                    <th>Dung lượng Local</th>
                    <th>Thao tác</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredJobs.map((job) => {
                    const progress = progressFromJob(job.progress, job.status, job.stage);
                    const mp4Bytes = job.storage?.mp4_bytes ?? 0;
                    const totalBytes = job.storage?.total_bytes ?? 0;
                    return (
                      <tr key={job.id}>
                        <td>
                          <button type="button" className="table-link" onClick={() => go(`/watch/${job.id}`)}>
                            <strong>{jobTitle(job)}</strong>
                            <span>{job.id}</span>
                          </button>
                        </td>
                        <td>
                          <span className="table-mono">{job.user_email || job.user_id || "cli"}</span>
                        </td>
                        <td>
                          <span className="table-badge">{jobKind(job)}</span>
                        </td>
                        <td>{stageLabel(job.stage)}</td>
                        <td>
                          <StatusPill label={job.status} tone={toneForStatus(job.status)} />
                        </td>
                        <td>
                          <ProgressBar value={progress} label={progressCopy(job.progress, job.stage)} />
                        </td>
                        <td>
                          <span className="table-mono">
                            {mp4Bytes > 0 ? `MP4 ${formatBytes(mp4Bytes)}` : formatBytes(totalBytes)}
                          </span>
                        </td>
                        <td>
                          <div className="hub-actions">
                            <button type="button" className="ghost" onClick={() => go(`/watch/${job.id}`)}>
                              Xem
                            </button>
                            {job.status === "done" && job.storage?.mp4_ready ? (
                              <a className="button ghost" href={`/jobs/${encodeURIComponent(job.id)}/download`} download>
                                Tải MP4
                              </a>
                            ) : null}
                            {job.status === "failed" ? (
                              <button
                                type="button"
                                className="ghost"
                                disabled={busy}
                                onClick={() => {
                                  setBusy(true);
                                  void retryAdminJob(job.id)
                                    .then(() => {
                                      setMessage(`Đã đưa job ${job.id} vào hàng đợi chạy lại.`);
                                      return refreshAll();
                                    })
                                    .catch((err) => setError(err instanceof Error ? err.message : "Không chạy lại được job"))
                                    .finally(() => setBusy(false));
                                }}
                              >
                                Chạy lại
                              </button>
                            ) : null}
                            <button
                              type="button"
                              className="ghost"
                              disabled={busy}
                              onClick={() => {
                                setBusy(true);
                                void deleteAdminJob(job.id, false)
                                  .then((res) => {
                                    setMessage(`Đã xóa job ${job.id} (giải phóng ${formatBytes(res.freed_bytes)}).`);
                                    return refreshAll();
                                  })
                                  .catch((err) => setError(err instanceof Error ? err.message : "Không xóa được job"))
                                  .finally(() => setBusy(false));
                              }}
                            >
                              Xóa
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}

      {tab === "storage" ? (
        <section className="panel">
          <div className="section-head">
            <div>
              <p className="kicker">Local Video Storage Skill</p>
              <h2>Quản lý Lưu trữ Video Local ({storageData?.videos?.length ?? 0})</h2>
              <p className="panel-subtitle">
                Quản lý file MP4 và dữ liệu render trên ổ cứng máy chủ ({storageSummary?.data_dir}).
                {storageSummary?.orphan_job_ids?.length
                  ? ` Phát hiện ${storageSummary.orphan_job_ids.length} thư mục orphan chưa đồng bộ.`
                  : " Không có thư mục orphan."}
              </p>
            </div>
            <div className="hub-actions">
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  setBusy(true);
                  void cleanupAdminStorage({ remove_orphans: true, compact_done: true })
                    .then((res) => {
                      setMessage(
                        `Đã dọn dẹp ổ đĩa: giải phóng ${formatBytes(res.freed_bytes)} (${res.compacted_jobs.length} job gọn nhẹ, ${res.removed_orphans.length} orphan).`,
                      );
                      return refreshAll();
                    })
                    .catch((err) => setError(err instanceof Error ? err.message : "Lỗi dọn ổ đĩa"))
                    .finally(() => setBusy(false));
                }}
              >
                Dọn file tạm & Orphan
              </button>
            </div>
          </div>

          <div className="job-table-wrap">
            <table className="job-table">
              <thead>
                <tr>
                  <th>Video / Job</th>
                  <th>Người tạo</th>
                  <th>Trạng thái</th>
                  <th>MP4 Local</th>
                  <th>Stills / Refs</th>
                  <th>Tổng dung lượng</th>
                  <th>Thao tác lưu trữ</th>
                </tr>
              </thead>
              <tbody>
                {(storageData?.videos ?? []).map((item) => {
                  const st = item.storage;
                  return (
                    <tr key={item.id}>
                      <td>
                        <button type="button" className="table-link" onClick={() => go(item.watch_url)}>
                          <strong>{item.title}</strong>
                          <span>
                            {item.id} · {item.kind}
                          </span>
                        </button>
                      </td>
                      <td>
                        <span className="table-mono">{item.user_email || item.user_id || "cli"}</span>
                      </td>
                      <td>
                        <StatusPill
                          label={st.mp4_ready ? "MP4 ready" : st.local_exists ? item.status : "cloud-only"}
                          tone={st.mp4_ready ? "done" : "idle"}
                        />
                      </td>
                      <td>
                        <span className="table-mono">{st.mp4_ready ? formatBytes(st.mp4_bytes) : "0 B"}</span>
                      </td>
                      <td>
                        <span className="table-mono">{formatBytes((st.stills_bytes ?? 0) + (st.refs_bytes ?? 0))}</span>
                      </td>
                      <td>
                        <span className="table-mono">{formatBytes(st.total_bytes)}</span>
                      </td>
                      <td>
                        <div className="hub-actions">
                          {item.download_url ? (
                            <a className="button ghost" href={item.download_url} download>
                              Tải MP4
                            </a>
                          ) : null}
                          {st.local_exists ? (
                            <button
                              type="button"
                              className="ghost"
                              disabled={busy}
                              onClick={() => {
                                setBusy(true);
                                void compactJobStorage(item.id)
                                  .then((res) => {
                                    setMessage(`Đã thu gọn job ${item.id} (giải phóng ${formatBytes(res.freed_bytes)}).`);
                                    return refreshAll();
                                  })
                                  .catch((err) => setError(err instanceof Error ? err.message : "Lỗi thu gọn job"))
                                  .finally(() => setBusy(false));
                              }}
                            >
                              Thu gọn
                            </button>
                          ) : null}
                          {st.local_exists ? (
                            <button
                              type="button"
                              className="ghost"
                              disabled={busy}
                              onClick={() => {
                                setBusy(true);
                                void deleteAdminJob(item.id, true)
                                  .then((res) => {
                                    setMessage(
                                      `Đã xóa file local của job ${item.id} (${formatBytes(res.freed_bytes)}), giữ lại lịch sử trên Cloudflare D1.`,
                                    );
                                    return refreshAll();
                                  })
                                  .catch((err) => setError(err instanceof Error ? err.message : "Lỗi xóa file local"))
                                  .finally(() => setBusy(false));
                              }}
                            >
                              Xóa file đĩa
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </section>
  );
}
