import { useCallback, useEffect, useMemo, useState } from "react";
import { deleteJob, listJobs } from "../api";
import { CounterCard, PageHeader, ProgressBar, StatusPill, progressCopy, progressFromJob, stageLabel, toneForStatus } from "../components";
import { useNav } from "../nav";
import type { Job, VideoKind } from "../types";

type StatusFilter = "all" | "running" | "done" | "failed";

const FILTERS: { id: StatusFilter; label: string }[] = [
  { id: "all", label: "Tất cả" },
  { id: "running", label: "Đang chạy" },
  { id: "done", label: "Đã xong" },
  { id: "failed", label: "Lỗi" },
];

const CREATE_LINKS: { href: string; kind: VideoKind; title: string; copy: string; icon: string }[] = [
  {
    href: "/drama",
    kind: "drama",
    title: "Drama",
    copy: "Kịch bản 5 nhịp, khóa khuôn mặt Character Bible, dựng still và motion.",
    icon: "M15.91 11.672a.375.375 0 0 1 0 .656l-6.54 3.78a.375.375 0 0 1-.563-.328V8.22a.375.375 0 0 1 .563-.327l6.54 3.78Z",
  },
  {
    href: "/news",
    kind: "news",
    title: "News",
    copy: "Dán URL bài báo hoặc bản tin, dựng 5 nhịp biên tập với ảnh báo chí.",
    icon: "M12 7.5h1.5m-1.5 3h1.5m-7.5 3h7.5m-7.5 3h7.5m3-9h3.375c.621 0 1.125.504 1.125 1.125V18a2.25 2.25 0 0 1-2.25 2.25M16.5 7.5V18a2.25 2.25 0 0 0 2.25 2.25M16.5 7.5V4.875c0-.621-.504-1.125-1.125-1.125H4.125C3.504 3.75 3 4.254 3 4.875V18a2.25 2.25 0 0 0 2.25 2.25h13.5",
  },
  {
    href: "/knowledge",
    kind: "knowledge",
    title: "Kiến thức",
    copy: "Thuyết minh chủ đề hoặc GitHub repo bằng giọng đọc và tư liệu trực quan.",
    icon: "M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.62 48.62 0 0 1 12 20.904a48.62 48.62 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.636 50.636 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342",
  },
];

function isRunning(job: Job): boolean {
  return job.status !== "done" && job.status !== "failed";
}

function formatDate(value?: string): string {
  if (!value) return "Chưa có";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function jobKind(job: Job): string {
  return job.storyboard?.kind || (typeof job.input?.kind === "string" ? job.input.kind : "short");
}

function jobTitle(job: Job): string {
  return job.storyboard?.title || (typeof job.input?.genre === "string" ? `${jobKind(job)} · ${job.input.genre}` : job.id);
}

function formatBytes(bytes?: number): string {
  const val = bytes ?? 0;
  if (!val) return "—";
  if (val < 1024) return `${val} B`;
  if (val < 1024 * 1024) return `${Math.round(val / 1024)} KB`;
  return `${(val / (1024 * 1024)).toFixed(1)} MB`;
}

export function WorkPage() {
  const { go } = useNav();
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const rows = await listJobs();
      setJobs(rows);
      setLastUpdated(new Date());
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Không tải được danh sách job");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const running = (jobs ?? []).some(isRunning);

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => {
      if (!document.hidden) void refresh();
    }, 4000);
    const onVisible = () => {
      if (!document.hidden) void refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh, running]);

  const counts = useMemo(() => {
    const rows = jobs ?? [];
    return {
      total: rows.length,
      running: rows.filter(isRunning).length,
      done: rows.filter((job) => job.status === "done").length,
      failed: rows.filter((job) => job.status === "failed").length,
    };
  }, [jobs]);

  const filteredJobs = useMemo(() => {
    const rows = jobs ?? [];
    if (filter === "all") return rows;
    if (filter === "running") return rows.filter(isRunning);
    return rows.filter((job) => job.status === filter);
  }, [filter, jobs]);

  return (
    <section className="page-stack">
      <PageHeader
        kicker="Workspace Overview"
        title="Việc của tôi"
        lede="Quản lý hàng đợi dựng video, giám sát tiến trình pipeline 7 bước và tải file MP4."
        actions={
          <>
            <button type="button" className="ghost" onClick={() => void refresh()}>
              Làm mới
            </button>
            <button type="button" onClick={() => go("/drama")}>
              + Tạo video mới
            </button>
          </>
        }
        meta={lastUpdated ? <span className="sync-meta">Đồng bộ lúc {formatDate(lastUpdated.toISOString())}</span> : null}
      />

      <div className="counter-grid">
        <CounterCard label="Tổng số job" value={counts.total} hint="Trong workspace" />
        <CounterCard label="Đang xử lý" value={counts.running} hint="Pipeline đang chạy" />
        <CounterCard label="Hoàn tất" value={counts.done} hint="Sẵn sàng tải MP4" />
        <CounterCard label="Cần kiểm tra" value={counts.failed} hint="Xem log tại Watch" />
      </div>

      <div className="quick-create-grid">
        {CREATE_LINKS.map((link) => (
          <button key={link.href} type="button" className="quick-create-card" onClick={() => go(link.href)}>
            <div className="quick-card-head">
              <div className="quick-card-icon" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d={link.icon} />
                </svg>
              </div>
              <span className="quick-card-action">Tạo mới →</span>
            </div>
            <div className="quick-card-body">
              <strong>{link.title}</strong>
              <small>{link.copy}</small>
            </div>
          </button>
        ))}
      </div>

      <section className="panel queue-panel">
        <div className="section-head">
          <div>
            <h2>Danh sách công việc</h2>
            <p className="panel-subtitle">Bấm vào tên job để mở màn hình giám sát chi tiết.</p>
          </div>
          <div className="segmented" aria-label="Lọc trạng thái">
            {FILTERS.map((item) => (
              <button
                key={item.id}
                type="button"
                className={filter === item.id ? "on" : ""}
                onClick={() => setFilter(item.id)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>

        {jobs === null && !loadError ? <p className="meta">Đang tải danh sách job…</p> : null}
        {loadError ? <p className="err">{loadError}</p> : null}
        {jobs && jobs.length === 0 ? (
          <div className="empty-panel">
            <div className="empty-icon" aria-hidden="true">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="16" rx="2" />
                <path d="m10 9 5 3-5 3V9Z" />
              </svg>
            </div>
            <div className="empty-text">
              <strong>Chưa có video nào trong danh sách</strong>
              <p>Chọn một trong ba định dạng (Drama, News, hoặc Kiến thức) ở trên để bắt đầu dựng video đầu tiên.</p>
            </div>
            <div className="empty-actions">
              <button type="button" onClick={() => go("/drama")}>
                Tạo Drama
              </button>
              <button type="button" className="ghost" onClick={() => go("/news")}>
                Tạo News
              </button>
              <button type="button" className="ghost" onClick={() => go("/knowledge")}>
                Tạo Kiến thức
              </button>
            </div>
          </div>
        ) : null}
        {jobs && jobs.length > 0 && filteredJobs.length === 0 ? (
          <p className="meta">Không có job nào khớp với bộ lọc hiện tại.</p>
        ) : null}
        {filteredJobs.length > 0 ? (
          <div className="job-table-wrap">
            <table className="job-table">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Định dạng</th>
                  <th>Bước hiện tại</th>
                  <th>Trạng thái</th>
                  <th>Tiến độ</th>
                  <th>Cập nhật</th>
                  <th>Chuyển động / MP4</th>
                  <th>Thao tác</th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.map((job) => {
                  const motion = job.artifacts?.motion_mode || "pending";
                  const progress = progressFromJob(job.progress, job.status, job.stage);
                  const mp4Bytes = job.storage?.mp4_bytes;
                  return (
                    <tr key={job.id}>
                      <td>
                        <button type="button" className="table-link" onClick={() => go(`/watch/${job.id}`)}>
                          <strong>{jobTitle(job)}</strong>
                          <span>{job.id}</span>
                        </button>
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
                      <td>{formatDate(job.updated_at || job.created_at)}</td>
                      <td>
                        <span className="table-mono">
                          {motion}
                          {mp4Bytes ? ` · ${formatBytes(mp4Bytes)}` : ""}
                        </span>
                      </td>
                      <td>
                        <div className="hub-actions">
                          {job.status === "done" ? (
                            <a className="button ghost" href={`/jobs/${encodeURIComponent(job.id)}/download`} download>
                              Tải MP4
                            </a>
                          ) : (
                            <button type="button" className="ghost" onClick={() => go(`/watch/${job.id}`)}>
                              Xem
                            </button>
                          )}
                          <button
                            type="button"
                            className="ghost"
                            onClick={() => {
                              void deleteJob(job.id, false)
                                .then(() => refresh())
                                .catch((err) => setLoadError(err instanceof Error ? err.message : "Không xóa được job"));
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
        ) : null}
      </section>
    </section>
  );
}
