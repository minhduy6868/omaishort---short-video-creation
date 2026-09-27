import { useEffect, useState } from "react";
import { listJobs } from "../api";
import { useNav } from "../nav";
import type { Job } from "../types";

export function WorkPage() {
  const { go } = useNav();
  const [jobs, setJobs] = useState<Job[] | null>(null);

  useEffect(() => {
    let stop = false;
    void listJobs().then((rows) => {
      if (!stop) setJobs(rows);
    });
    return () => {
      stop = true;
    };
  }, []);

  return (
    <section>
      <p className="kicker">Studio</p>
      <h1>Việc của tôi</h1>
      <p className="lede">Chọn một job đang chạy hoặc đã xong. Tạo video mới ở Drama, News, hoặc Kiến thức.</p>
      {jobs === null ? <p className="meta">Đang tải…</p> : null}
      {jobs && jobs.length === 0 ? <p className="meta">Chưa có job.</p> : null}
      {jobs && jobs.length > 0 ? (
        <ul className="job-list">
          {jobs.map((job) => (
            <li key={job.id}>
              <button type="button" onClick={() => go(`/watch/${job.id}`)}>
                <strong>{job.storyboard?.title || job.id}</strong>
                <span>
                  {job.storyboard?.kind || "short"} · {job.stage} · {job.status}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
