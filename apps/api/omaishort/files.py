"""Resolve authenticated GETs under DATA_DIR. Never serve the DB or secrets."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, status

from omaishort import db
from omaishort.auth import can_read_job
from omaishort import config

_BLOCK_NAMES = {"omaishort.db", ".auth_secret"}
_BLOCK_PREFIXES = ("chatgpt-web",)


def resolve_public_file(rel: str, user: dict) -> Path:
    raw = (rel or "").replace("\\", "/").lstrip("/")
    if not raw or raw.endswith("/"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
    root = config.DATA_DIR.resolve()
    try:
        path = (root / raw).resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found") from None
    parts = path.relative_to(root).parts
    name = parts[-1]
    if name in _BLOCK_NAMES or name.startswith(".auth"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
    if parts and parts[0] in _BLOCK_PREFIXES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
    if not path.is_file() and len(parts) >= 3 and parts[0] == "attachments":
        from omaishort import cloud_client, uploads

        att_id = Path(name).stem
        att = db.get_attachment(att_id)
        if not att and cloud_client.cloud_mode_enabled():
            cloud_att = cloud_client.attachments_get(att_id)
            if cloud_att:
                att = db.upsert_attachment_from_cloud(cloud_att)
        if att:
            uploads.disk_path(att)
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
    if parts[0] == "jobs" and len(parts) >= 2:
        from omaishort import cloud_client

        row = db.get_job(parts[1])
        if not row and cloud_client.cloud_mode_enabled():
            remote = cloud_client.jobs_get(parts[1])
            if remote:
                cloud_client.bind_job_token(parts[1])
                row = db.upsert_job_from_cloud(remote)
        if not row or not can_read_job(row, user):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
        return path
    if parts[0] == "attachments" and len(parts) >= 2:
        owner = parts[1]
        if owner == user["id"] or user.get("role") == "operator":
            return path
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
    if parts[0] == "templates" and len(parts) >= 2:
        owner = parts[1]
        if owner == user["id"] or owner == "cli" or user.get("role") == "operator":
            return path
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
    raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found")
