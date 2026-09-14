"""Upload sniff, quotas, and on-disk attachment storage."""

from __future__ import annotations

import hashlib
import re
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image

from omaishort import config
from omaishort import db
from omaishort_schema.models import AttachmentKind

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
MAX_IMAGE = 8 * 1024 * 1024
MAX_LOGO = 2 * 1024 * 1024
MAX_SCRIPT = 256 * 1024
MAX_COUNT = 80
MAX_BYTES = 200 * 1024 * 1024
IMAGE_KINDS = {
    AttachmentKind.face,
    AttachmentKind.location,
    AttachmentKind.prop,
    AttachmentKind.editorial,
    AttachmentKind.logo,
}


def sniff_bytes(data: bytes, kind: AttachmentKind, filename: str) -> tuple[str, str]:
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file")
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg", ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png", ".png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if kind == AttachmentKind.script:
        if b"\x00" in data[:1024]:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "file type not allowed")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "file type not allowed") from exc
        suffix = Path(filename).suffix.lower()
        if suffix not in {".txt", ".md", ""}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "file type not allowed")
        return "text/plain", suffix or ".txt"
    raise HTTPException(status.HTTP_400_BAD_REQUEST, "file type not allowed")


def max_bytes_for(kind: AttachmentKind) -> int:
    if kind == AttachmentKind.logo:
        return MAX_LOGO
    if kind == AttachmentKind.script:
        return MAX_SCRIPT
    return MAX_IMAGE


def sanitize_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    cleaned = _SAFE_NAME.sub("_", base).strip("._") or "upload"
    return cleaned[:120]


def _verify_image(data: bytes) -> None:
    from io import BytesIO

    try:
        with Image.open(BytesIO(data)) as img:
            img.verify()
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file type not allowed") from exc


async def save_upload(user_id: str, kind: AttachmentKind, upload: UploadFile) -> dict:
    data = await upload.read(max_bytes_for(kind) + 1)
    if len(data) > max_bytes_for(kind):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file too large")
    mime, ext = sniff_bytes(data, kind, upload.filename or "upload")
    if kind in IMAGE_KINDS:
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "file type not allowed")
        _verify_image(data)
    elif kind != AttachmentKind.script:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "file type not allowed")
    digest = hashlib.sha256(data).hexdigest()
    existing = db.find_attachment_by_hash(user_id, kind.value, digest)
    if existing:
        return existing
    count, used = db.attachment_quota(user_id)
    if count >= MAX_COUNT or used + len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "attachment quota exceeded")
    attachment_id = secrets.token_hex(6)
    rel = Path("attachments") / user_id / f"{attachment_id}{ext}"
    dest = config.DATA_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return db.insert_attachment(
        attachment_id,
        user_id,
        kind.value,
        sanitize_filename(upload.filename or f"upload{ext}"),
        mime,
        len(data),
        digest,
        rel.as_posix(),
    )


def disk_path(row: dict) -> Path:
    return (config.DATA_DIR / str(row["rel_path"])).resolve()


def attachment_abs(row: dict) -> Path:
    path = disk_path(row)
    root = config.DATA_DIR.resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found") from None
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    return path


def require_owned_attachment(attachment_id: str, user_id: str) -> dict:
    row = db.get_attachment(attachment_id)
    if not row or row["user_id"] != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    return row


def load_job_files(user_id: str, links: list) -> list[dict]:
    """Validate every linked attachment at POST /jobs time. 404 if any is missing/not owned."""
    rows: list[dict] = []
    for link in links:
        row = require_owned_attachment(link.id, user_id)
        if not disk_path(row).is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
        rows.append({**row, "bind": link.bind})
    return rows


def delete_owned(attachment_id: str, user_id: str) -> None:
    row = require_owned_attachment(attachment_id, user_id)
    path = config.DATA_DIR / str(row["rel_path"])
    db.delete_attachment(attachment_id)
    if path.is_file():
        path.unlink()
