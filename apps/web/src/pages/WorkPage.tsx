import { useCallback, useEffect, useMemo, useState } from "react";
import { listJobs } from "../api";
import { CounterCard, PageHeader, ProgressBar, StatusPill, progressFromJob, toneForStatus } from "../components";
import { useNav } from "../nav";
import type { Job, VideoKind } from "../types";

type StatusFilter = "all" | "running" | "done" | "failed";

const FILTERS: { id: StatusFilter; label: string }[] = [
  { id: "all", label: "Tất cả" },
  { id: "running", label: "Đang chạy" },
  { id: "done", label: "Đã xong" },
  { id: "failed", label: "Lỗi" },
];

const CREATE_LINKS: { href: string; kind: VideoKind; title: string; copy: string }[] = [
  { href: "/drama", kind: "drama", title: "Drama", copy: "Kịch bản nhân vật, scene, still và motion." },
  { href: "/news", kind: "news", title: "News", copy: "Tin ngắn dạng ảnh ghép biên tập." },
  { href: "/knowledge", kind: "knowledge", title: "Kiến thức", copy: "Giải thích chủ đề hoặc repo bằng thuyết minh." },
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

export function WorkPage() {
  const { go } = useNav();
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    const rows = await listJobs();
    setJobs(rows);
    setLastUpdated(new Date());
  }, []);

  useEffect(() => {
    let stop = false;
    void listJobs().then((rows) => {
      if (!stop) {
        setJobs(rows);
        setLastUpdated(new Date());
      }
    });
    return () => {
      stop = true;
    };
  }, []);

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
        kicker="Studio"
        title="Việc của tôi"
        lede="Theo dõi hàng đợi dựng video, mở lại job đang chạy, tải MP4 khi render xong."
        actions={
          <>
            <button type="button" className="ghost" onClick={() => void refresh()}>
              Làm mới
            </button>
            <button type="button" onClick={() => go("/drama")}>
              Tạo drama
            </button>
          </>
        }
        meta={lastUpdated ? <span>Cập nhật {formatDate(lastUpdated.toISOString())}</span> : null}
      />

      <div className="counter-grid">
        <CounterCard label="Tổng job" value={counts.total} hint="Trong workspace này" />
        <CounterCard label="Đang chạy" value={counts.running} hint="Chưa terminal" />
        <CounterCard label="Đã xong" value={counts.done} hint="Có thể tải MP4" />
        <CounterCard label="Lỗi" value={counts.failed} hint="Cần kiểm tra Watch" />
      </div>

      <div className="quick-create-grid">
        {CREATE_LINKS.map((link, index) => (
          <button key={link.href} type="button" className="quick-create-card" onClick={() => go(link.href)}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <strong>{link.title}</strong>
            <small>{link.copy}</small>
            <em>{link.kind}</em>
          </button>
        ))}
      </div>

      <section className="panel queue-panel">
        <div className="section-head">
          <div>
            <p className="kicker">Queue</p>
            <h2>Production queue</h2>
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

        {jobs === null ? <p className="meta">Đang tải job…</p> : null}
        {jobs && jobs.length === 0 ? (
          <div className="empty-panel">
            <strong>Chưa có job.</strong>
            <p>Tạo video đầu tiên từ Drama, News hoặc Kiến thức.</p>
            <button type="button" onClick={() => go("/drama")}>
              Tạo job đầu tiên
            </button>
          </div>
        ) : null}
        {jobs && jobs.length > 0 && filteredJobs.length === 0 ? (
          <p className="meta">Không có job trong bộ lọc này.</p>
        ) : null}
        {filteredJobs.length > 0 ? (
          <div className="job-table-wrap">
            <table className="job-table">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Kind</th>
                  <th>Stage</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Updated</th>
                  <th>Motion</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredJobs.map((job) => {
                  const motion = job.artifacts?.motion_mode || "pending";
                  const progress = progressFromJob(job.progress, job.status);
                  return (
                    <tr key={job.id}>
                      <td>
                        <button type="button" className="table-link" onClick={() => go(`/watch/${job.id}`)}>
                          <strong>{jobTitle(job)}</strong>
                          <span>{job.id}</span>
                        </button>
                      </td>
                      <td>{jobKind(job)}</td>
                      <td>{job.stage}</td>
                      <td>
                        <StatusPill label={job.status} tone={toneForStatus(job.status)} />
                      </td>
                      <td>
                        <ProgressBar value={progress} label={job.progress || `${Math.round(progress)}%`} />
                      </td>
                      <td>{formatDate(job.updated_at || job.created_at)}</td>
                      <td>{motion}</td>
                      <td>
                        {job.status === "done" ? (
                          <a className="button ghost" href={`/jobs/${encodeURIComponent(job.id)}/download`} download>
                            Tải
                          </a>
                        ) : (
                          <button type="button" className="ghost" onClick={() => go(`/watch/${job.id}`)}>
                            Mở
                          </button>
                        )}
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
