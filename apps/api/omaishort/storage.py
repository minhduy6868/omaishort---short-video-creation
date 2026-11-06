"""Local video storage manager: tracks MP4 and job disk footprint while keeping metadata in Cloudflare D1."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import shutil
from pathlib import Path
from typing import Any

from omaishort import config, db

_KEEP_RENDER_FILES = {"short.mp4", "captions.ass", "motion.json"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_job_dir(job_id: str) -> Path:
    clean = (job_id or "").strip()
    if not clean or "/" in clean or "\\" in clean or ".." in clean:
        raise ValueError("invalid job_id")
    root = (config.DATA_DIR / "jobs").resolve()
    target = (root / clean).resolve()
    target.relative_to(root)
    return target


def _dir_bytes(path: Path) -> tuple[int, int]:
    if not path.is_dir():
        return 0, 0
    total = 0
    count = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
                count += 1
            except OSError:
                continue
    return total, count


def inspect_job_storage(
    job_id: str,
    row: dict[str, Any] | None = None,
    *,
    sync_db: bool = False,
) -> dict[str, Any]:
    try:
        jdir = _safe_job_dir(job_id)
    except ValueError:
        return {
            "job_id": job_id,
            "local_exists": False,
            "mp4_ready": False,
            "mp4_bytes": 0,
            "stills_bytes": 0,
            "sourced_bytes": 0,
            "refs_bytes": 0,
            "audio_bytes": 0,
            "other_bytes": 0,
            "total_bytes": 0,
            "file_count": 0,
        }

    existing_meta = db.storage_of(row) if row else {}
    if not jdir.is_dir():
        info = {
            **existing_meta,
            "job_id": job_id,
            "local_exists": False,
            "mp4_ready": False,
            "mp4_bytes": 0,
            "stills_bytes": 0,
            "sourced_bytes": 0,
            "refs_bytes": 0,
            "audio_bytes": 0,
            "other_bytes": 0,
            "total_bytes": 0,
            "file_count": 0,
        }
        if sync_db and row is not None:
            db.update_job(job_id, storage_json=json.dumps(info))
        return info

    mp4_path = jdir / "render" / "short.mp4"
    mp4_bytes = mp4_path.stat().st_size if mp4_path.is_file() else 0
    sourced_dir = jdir / "stills" / "sourced"
    sourced_bytes, _ = _dir_bytes(sourced_dir)
    stills_total, _ = _dir_bytes(jdir / "stills")
    stills_bytes = max(0, stills_total - sourced_bytes)
    refs_bytes, _ = _dir_bytes(jdir / "refs")
    audio_bytes, _ = _dir_bytes(jdir / "audio")
    total_bytes, file_count = _dir_bytes(jdir)
    known = mp4_bytes + stills_total + refs_bytes + audio_bytes
    other_bytes = max(0, total_bytes - known)

    info = {
        **existing_meta,
        "job_id": job_id,
        "local_exists": True,
        "mp4_ready": bool(mp4_path.is_file() and mp4_bytes > 0),
        "mp4_path": mp4_path.as_posix() if mp4_path.is_file() else None,
        "mp4_bytes": mp4_bytes,
        "stills_bytes": stills_bytes,
        "sourced_bytes": sourced_bytes,
        "refs_bytes": refs_bytes,
        "audio_bytes": audio_bytes,
        "other_bytes": other_bytes,
        "total_bytes": total_bytes,
        "file_count": file_count,
        "inspected_at": _now(),
    }
    if sync_db:
        db.update_job(job_id, storage_json=json.dumps(info))
    return info


def compact_job_storage(job_id: str) -> dict[str, Any]:
    row = db.get_job(job_id)
    jdir = _safe_job_dir(job_id)
    before = inspect_job_storage(job_id, row)
    if not jdir.is_dir():
        return {**before, "freed_bytes": 0, "compacted": False}

    freed = 0
    sourced_dir = jdir / "stills" / "sourced"
    if sourced_dir.is_dir():
        bytes_removed, _ = _dir_bytes(sourced_dir)
        shutil.rmtree(sourced_dir, ignore_errors=True)
        freed += bytes_removed

    rdir = jdir / "render"
    if rdir.is_dir():
        for child in list(rdir.iterdir()):
            if child.name in _KEEP_RENDER_FILES:
                continue
            if child.is_file():
                try:
                    freed += child.stat().st_size
                    child.unlink()
                except OSError:
                    pass
            elif child.is_dir():
                b_rem, _ = _dir_bytes(child)
                shutil.rmtree(child, ignore_errors=True)
                freed += b_rem

    after = inspect_job_storage(job_id, row)
    after["compacted"] = True
    after["compacted_at"] = _now()
    after["freed_bytes"] = max(0, before["total_bytes"] - after["total_bytes"], freed)
    if row is not None:
        db.update_job(job_id, storage_json=json.dumps(after))
    return after


def delete_job_storage(job_id: str, *, delete_db_row: bool = False) -> dict[str, Any]:
    row = db.get_job(job_id)
    jdir = _safe_job_dir(job_id)
    before = inspect_job_storage(job_id, row)
    freed = before.get("total_bytes", 0)
    if jdir.is_dir():
        shutil.rmtree(jdir, ignore_errors=True)
    if delete_db_row:
        db.delete_job(job_id)
        return {"job_id": job_id, "deleted_db": True, "deleted_local": True, "freed_bytes": freed}
    updated = {
        **before,
        "local_exists": False,
        "mp4_ready": False,
        "mp4_path": None,
        "mp4_bytes": 0,
        "stills_bytes": 0,
        "sourced_bytes": 0,
        "refs_bytes": 0,
        "audio_bytes": 0,
        "other_bytes": 0,
        "total_bytes": 0,
        "file_count": 0,
        "deleted_at": _now(),
    }
    if row is not None:
        artifacts = db.artifacts_of(row)
        artifacts.pop("mp4", None)
        db.update_job(job_id, artifacts_json=json.dumps(artifacts), storage_json=json.dumps(updated))
    return {"job_id": job_id, "deleted_db": False, "deleted_local": True, "freed_bytes": freed}


def _job_video_entry(row: dict[str, Any], users_by_id: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    pub = db.public_job(row)
    job_id = str(row["id"])
    storage = inspect_job_storage(job_id, row)
    board = pub.get("storyboard") if isinstance(pub.get("storyboard"), dict) else {}
    inp = pub.get("input") if isinstance(pub.get("input"), dict) else {}
    kind = str(board.get("kind") or inp.get("kind") or "drama")
    title = str(board.get("title") or inp.get("genre") or job_id)
    uid = row.get("user_id")
    owner = (users_by_id or {}).get(str(uid)) if uid else None
    return {
        "id": job_id,
        "title": title,
        "kind": kind,
        "status": row.get("status"),
        "stage": row.get("stage"),
        "progress": row.get("progress"),
        "user_id": uid,
        "user_email": owner.get("email") if owner else ("cli" if not uid else None),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "download_url": f"/jobs/{job_id}/download" if storage.get("mp4_ready") else None,
        "watch_url": f"/watch/{job_id}",
        "storage": storage,
    }


def list_local_videos(user: dict[str, Any], *, all_users: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    is_op = user.get("role") == "operator"
    if all_users and is_op:
        rows = db.list_all_jobs(limit=limit)
        users_map = {str(u["id"]): u for u in db.list_users()}
    else:
        rows = db.list_jobs(str(user["id"]), limit=limit)
        users_map = {str(user["id"]): user}
    return [_job_video_entry(row, users_map) for row in rows]


def storage_summary() -> dict[str, Any]:
    jobs_root = config.DATA_DIR / "jobs"
    att_root = config.DATA_DIR / "attachments"
    jobs_bytes, jobs_files = _dir_bytes(jobs_root)
    att_bytes, att_files = _dir_bytes(att_root)
    mp4_count = 0
    mp4_bytes = 0
    job_dirs_count = 0
    orphan_job_ids: list[str] = []

    if jobs_root.is_dir():
        for child in sorted(jobs_root.iterdir()):
            if not child.is_dir():
                continue
            job_dirs_count += 1
            mp4 = child / "render" / "short.mp4"
            if mp4.is_file():
                try:
                    mp4_count += 1
                    mp4_bytes += mp4.stat().st_size
                except OSError:
                    pass
            if db.get_job(child.name) is None:
                orphan_job_ids.append(child.name)

    return {
        "data_dir": config.DATA_DIR.resolve().as_posix(),
        "jobs_bytes": jobs_bytes,
        "jobs_files": jobs_files,
        "job_dirs_count": job_dirs_count,
        "mp4_count": mp4_count,
        "mp4_bytes": mp4_bytes,
        "attachments_local_bytes": att_bytes,
        "attachments_local_files": att_files,
        "total_local_bytes": jobs_bytes + att_bytes,
        "orphan_job_ids": orphan_job_ids,
    }


def cleanup_storage(*, remove_orphans: bool = True, compact_done: bool = True) -> dict[str, Any]:
    freed_bytes = 0
    removed_orphans: list[str] = []
    compacted_jobs: list[str] = []

    summary = storage_summary()
    if remove_orphans:
        for orphan_id in summary["orphan_job_ids"]:
            try:
                jdir = _safe_job_dir(orphan_id)
            except ValueError:
                continue
            if jdir.is_dir():
                b_rem, _ = _dir_bytes(jdir)
                shutil.rmtree(jdir, ignore_errors=True)
                freed_bytes += b_rem
                removed_orphans.append(orphan_id)

    if compact_done:
        for row in db.list_all_jobs(limit=200, status="done"):
            res = compact_job_storage(str(row["id"]))
            if res.get("freed_bytes", 0) > 0:
                freed_bytes += int(res["freed_bytes"])
                compacted_jobs.append(str(row["id"]))

    return {
        "freed_bytes": freed_bytes,
        "removed_orphans": removed_orphans,
        "compacted_jobs": compacted_jobs,
        "summary": storage_summary(),
    }

