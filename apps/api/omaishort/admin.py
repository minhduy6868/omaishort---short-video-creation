"""Admin (operator) and local video storage HTTP routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from omaishort import db, storage
from omaishort.auth import CurrentUser, OperatorUser, _parse_iso, require_job
from omaishort.pipeline import run_job
from omaishort.providers.llm import llm_status

router = APIRouter()

SITE_THEMES = ("brutal", "soft")


def site_theme_value() -> str:
    value = db.get_setting("site_theme")
    return value if value in SITE_THEMES else SITE_THEMES[0]


def _admin_user_view(
    row: dict[str, Any],
    job_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    locked_dt = _parse_iso(row.get("locked_until"))
    is_locked = bool(locked_dt and locked_dt > now)
    uid = str(row["id"])
    att_count, att_bytes = db.attachment_quota(uid)
    return {
        "id": uid,
        "email": row["email"],
        "display_name": row.get("display_name"),
        "role": row["role"],
        "locked": is_locked,
        "locked_until": row.get("locked_until") if is_locked else None,
        "failed_logins": int(row.get("failed_logins") or 0),
        "jobs_count": (job_counts or {}).get(uid, 0),
        "attachments_count": att_count,
        "attachments_bytes": att_bytes,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


class AdminUserPatch(BaseModel):
    role: str | None = None
    locked: bool | None = None
    display_name: str | None = Field(default=None, max_length=80)
    revoke_sessions: bool = False


class AdminSettingsBody(BaseModel):
    site_theme: str | None = None
    signup_enabled: bool | None = None


class StorageCleanupBody(BaseModel):
    remove_orphans: bool = True
    compact_done: bool = True


@router.get("/admin/overview")
def admin_overview(_admin: OperatorUser) -> dict[str, Any]:
    return {
        "stats": db.admin_stats(),
        "storage": storage.storage_summary(),
        "settings": {
            "site_theme": site_theme_value(),
            "themes": list(SITE_THEMES),
            "signup_enabled": db.signup_enabled(),
        },
        "providers": llm_status(),
    }


@router.get("/admin/users")
def admin_list_users(_admin: OperatorUser) -> dict[str, Any]:
    users = db.list_users()
    all_jobs = db.list_all_jobs(limit=200)
    counts: dict[str, int] = {}
    for j in all_jobs:
        uid = j.get("user_id")
        if uid:
            counts[str(uid)] = counts.get(str(uid), 0) + 1
    return {"users": [_admin_user_view(u, counts) for u in users]}


@router.patch("/admin/users/{user_id}")
def admin_patch_user(user_id: str, body: AdminUserPatch, caller: OperatorUser) -> dict[str, Any]:
    target = db.get_user_by_id(user_id)
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    updates: dict[str, Any] = {}
    if body.role is not None:
        if body.role not in ("operator", "creator"):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "role must be operator or creator")
        if target["role"] == "operator" and body.role == "creator" and db.count_operators() <= 1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Không thể hạ quyền admin (operator) cuối cùng.")
        updates["role"] = body.role

    if body.display_name is not None:
        updates["display_name"] = body.display_name.strip() or target["email"].split("@", 1)[0]

    if body.locked is not None:
        if body.locked:
            if user_id == caller["id"]:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Không thể tự khóa tài khoản của chính mình.")
            until = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
            updates["locked_until"] = until
            updates["failed_logins"] = 8
            db.revoke_user_refresh(user_id)
        else:
            updates["locked_until"] = None
            updates["failed_logins"] = 0

    if updates:
        db.update_user(user_id, **updates)
    if body.revoke_sessions:
        db.revoke_user_refresh(user_id)

    fresh = db.get_user_by_id(user_id)
    assert fresh
    return {"user": _admin_user_view(fresh)}


@router.get("/admin/jobs")
def admin_list_jobs(
    _admin: OperatorUser,
    limit: int = Query(50, ge=1, le=200),
    job_status: str | None = Query(None, alias="status"),
    user_id: str | None = Query(None),
) -> dict[str, Any]:
    rows = db.list_all_jobs(limit=limit, status=job_status, user_id=user_id)
    users_map = {str(u["id"]): u for u in db.list_users()}
    out: list[dict[str, Any]] = []
    for row in rows:
        pub = db.public_job(row)
        uid = row.get("user_id")
        owner = users_map.get(str(uid)) if uid else None
        pub["user_email"] = owner.get("email") if owner else ("cli" if not uid else None)
        pub["storage"] = storage.inspect_job_storage(str(row["id"]), row)
        out.append(pub)
    return {"jobs": out}


@router.post("/admin/jobs/{job_id}/retry")
async def admin_retry_job(
    job_id: str,
    background: BackgroundTasks,
    _admin: OperatorUser,
) -> dict[str, str]:
    row = db.get_job(job_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    db.update_job(job_id, status="queued", stage="queued", progress="queued", error=None)
    background.add_task(run_job, job_id)
    return {"id": job_id, "status": "queued"}


@router.delete("/admin/jobs/{job_id}")
def admin_delete_job(
    job_id: str,
    _admin: OperatorUser,
    keep_db: bool = Query(False),
) -> dict[str, Any]:
    row = db.get_job(job_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return storage.delete_job_storage(job_id, delete_db_row=not keep_db)


@router.get("/admin/storage")
def admin_read_storage(caller: OperatorUser) -> dict[str, Any]:
    return {
        "summary": storage.storage_summary(),
        "videos": storage.list_local_videos(caller, all_users=True, limit=100),
    }


@router.post("/admin/storage/cleanup")
def admin_cleanup_storage(body: StorageCleanupBody, _admin: OperatorUser) -> dict[str, Any]:
    return storage.cleanup_storage(
        remove_orphans=body.remove_orphans,
        compact_done=body.compact_done,
    )


@router.put("/admin/settings")
def admin_save_settings(body: AdminSettingsBody, _admin: OperatorUser) -> dict[str, Any]:
    if body.site_theme is not None:
        if body.site_theme not in SITE_THEMES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"theme must be one of {', '.join(SITE_THEMES)}")
        db.set_setting("site_theme", body.site_theme)
    if body.signup_enabled is not None:
        db.set_setting("signup_enabled", "1" if body.signup_enabled else "0")
    return {
        "site_theme": site_theme_value(),
        "themes": list(SITE_THEMES),
        "signup_enabled": db.signup_enabled(),
    }


@router.get("/storage/videos")
def list_user_videos(
    user: CurrentUser,
    all_users: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    return {
        "videos": storage.list_local_videos(user, all_users=all_users, limit=limit),
        "summary": storage.storage_summary() if user.get("role") == "operator" else None,
    }


@router.get("/jobs/{job_id}/storage")
def read_job_storage(job_id: str, user: CurrentUser) -> dict[str, Any]:
    row = require_job(job_id, user)
    return storage.inspect_job_storage(job_id, row, sync_db=True)


@router.post("/jobs/{job_id}/compact")
def compact_job(job_id: str, user: CurrentUser) -> dict[str, Any]:
    require_job(job_id, user)
    return storage.compact_job_storage(job_id)


@router.delete("/jobs/{job_id}")
def remove_job(
    job_id: str,
    user: CurrentUser,
    keep_db: bool = Query(False),
) -> dict[str, Any]:
    require_job(job_id, user)
    return storage.delete_job_storage(job_id, delete_db_row=not keep_db)

