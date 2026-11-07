from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omaishort import config

_lock = threading.Lock()
_DEFAULT_PG = "postgresql://omaishort:omaishort@127.0.0.1:5432/omaishort"

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def database_url() -> str:
    env = os.environ.get("DATABASE_URL", "").strip()
    if env.startswith("sqlite"):
        return env
    if config.D1_WORKER_URL and config.D1_WORKER_KEY:
        return "d1://worker"
    if env:
        return env
    configured = (getattr(config, "DATABASE_URL", "") or "").strip()
    if configured.startswith("sqlite"):
        return configured
    if config.D1_WORKER_URL and config.D1_WORKER_KEY:
        return "d1://worker"
    return configured or _DEFAULT_PG


def is_d1(url: str | None = None) -> bool:
    raw = (url or database_url()).lower()
    return raw.startswith("d1:")


def is_postgres(url: str | None = None) -> bool:
    raw = (url or database_url()).lower()
    return raw.startswith("postgres")


def sqlite_path(url: str | None = None) -> Path:
    raw = url or database_url()
    if raw.startswith("sqlite:///"):
        return Path(raw[len("sqlite:///") :])
    if raw.startswith("sqlite://"):
        return Path(raw[len("sqlite://") :])
    return config.DATA_DIR / "omaishort.db"


def db_path() -> Path:
    return sqlite_path()


def _sql(sql: str) -> str:
    if is_postgres():
        return sql.replace("?", "%s")
    return sql


def _row(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return dict(row)


def _unique_violation(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {"IntegrityError", "UniqueViolation"}:
        return True
    text = str(exc).lower()
    return "unique" in text or "duplicate key" in text


def connect():
    url = database_url()
    if is_d1(url):
        from omaishort.d1 import D1Connection

        if not config.D1_WORKER_URL or not config.D1_WORKER_KEY:
            raise RuntimeError("Set D1_WORKER_URL and D1_WORKER_KEY for the Cloudflare database.")
        return D1Connection(config.D1_WORKER_URL, config.D1_WORKER_KEY)
    if is_postgres(url):
        if psycopg is None:
            raise RuntimeError("install psycopg (see apps/api/requirements.txt) for PostgreSQL")
        try:
            conn = psycopg.connect(url, row_factory=dict_row)
        except Exception as exc:
            raise RuntimeError(
                "PostgreSQL connection failed. Create the database/user then set DATABASE_URL "
                "(see .env.example and scripts/init_postgres.sql)."
            ) from exc
        return conn
    path = sqlite_path(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn, table: str, name: str, ddl: str) -> None:
    if is_d1():
        rows = conn.execute(f"SELECT name FROM pragma_table_info('{table}')").fetchall()
        names = {(_row(row) or {}).get("name") for row in rows}
        if name not in names:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
        return
    if is_postgres():
        found = conn.execute(
            _sql(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = ? AND column_name = ?"
            ),
            (table, name),
        ).fetchone()
        if not found:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
        return
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if name not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    bible_json TEXT,
                    structure_json TEXT,
                    storyboard_json TEXT,
                    timeline_json TEXT,
                    artifacts_json TEXT,
                    storage_json TEXT,
                    progress TEXT,
                    user_id TEXT
                )
                """
            )
            _ensure_column(conn, "jobs", "user_id", "TEXT")
            _ensure_column(conn, "jobs", "storage_json", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT,
                    role TEXT NOT NULL,
                    failed_logins INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    created_at TEXT NOT NULL,
                    user_agent TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    mime TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    rel_path TEXT NOT NULL,
                    content_b64 TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            _ensure_column(conn, "attachments", "content_b64", "TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_attachments_user ON attachments(user_id, created_at)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role, created_at)")
            conn.commit()
        finally:
            conn.close()


def create_job(job_id: str, input_json: str, user_id: str | None = None) -> None:
    now = _now()
    with _lock:
        conn = connect()
        try:
            conn.execute(
                _sql(
                    """
                    INSERT INTO jobs (id, status, stage, error, created_at, updated_at, input_json, progress, user_id)
                    VALUES (?, 'queued', 'queued', NULL, ?, ?, ?, 'queued', ?)
                    """
                ),
                (job_id, now, now, input_json, user_id),
            )
            conn.commit()
        finally:
            conn.close()


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    assignments = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [job_id]
    with _lock:
        conn = connect()
        try:
            conn.execute(_sql(f"UPDATE jobs SET {assignments} WHERE id = ?"), values)
            conn.commit()
        finally:
            conn.close()


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(_sql("SELECT * FROM jobs WHERE id = ?"), (job_id,)).fetchone()
            return _row(row)
        finally:
            conn.close()


def list_jobs(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    cap = min(50, max(1, limit))
    with _lock:
        conn = connect()
        try:
            rows = conn.execute(
                _sql(
                    """
                    SELECT * FROM jobs WHERE user_id = ?
                    ORDER BY created_at DESC LIMIT ?
                    """
                ),
                (user_id, cap),
            ).fetchall()
            return [item for item in (_row(row) for row in rows) if item]
        finally:
            conn.close()


def get_setting(key: str) -> str | None:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(_sql("SELECT value FROM settings WHERE key = ?"), (key,)).fetchone()
            data = _row(row)
            return str(data["value"]) if data else None
        finally:
            conn.close()


def set_setting(key: str, value: str) -> None:
    now = _now()
    with _lock:
        conn = connect()
        try:
            conn.execute(
                _sql(
                    """
                    INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                    """
                ),
                (key, value, now),
            )
            conn.commit()
        finally:
            conn.close()


def count_users() -> int:
    with _lock:
        conn = connect()
        try:
            row = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()
            data = _row(row) or {}
            return int(data.get("n") or 0)
        finally:
            conn.close()


def create_user(
    user_id: str,
    email: str,
    password_hash: str,
    display_name: str | None,
    role: str,
) -> dict[str, Any]:
    now = _now()
    with _lock:
        conn = connect()
        try:
            conn.execute(
                _sql(
                    """
                    INSERT INTO users (
                        id, email, password_hash, display_name, role,
                        failed_logins, locked_until, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?)
                    """
                ),
                (user_id, email, password_hash, display_name, role, now, now),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            if _unique_violation(exc):
                raise ValueError("email taken") from exc
            raise
        finally:
            conn.close()
    row = get_user_by_id(user_id)
    assert row
    return row


def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(_sql("SELECT * FROM users WHERE id = ?"), (user_id,)).fetchone()
            return _row(row)
        finally:
            conn.close()


def list_users() -> list[dict[str, Any]]:
    with _lock:
        conn = connect()
        try:
            rows = conn.execute(_sql("SELECT * FROM users ORDER BY created_at")).fetchall()
            return [item for item in (_row(row) for row in rows) if item]
        finally:
            conn.close()


def interrupted_job_ids() -> list[str]:
    with _lock:
        conn = connect()
        try:
            rows = conn.execute(
                _sql("SELECT id FROM jobs WHERE status IN ('queued', 'running') ORDER BY created_at")
            ).fetchall()
            ids: list[str] = []
            for row in rows:
                item = _row(row)
                if item and item.get("id"):
                    ids.append(str(item["id"]))
            return ids
        finally:
            conn.close()


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(_sql("SELECT * FROM users WHERE email = ?"), (email,)).fetchone()
            return _row(row)
        finally:
            conn.close()


def update_user(user_id: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    assignments = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    with _lock:
        conn = connect()
        try:
            conn.execute(_sql(f"UPDATE users SET {assignments} WHERE id = ?"), values)
            conn.commit()
        finally:
            conn.close()


def insert_refresh(
    token_id: str,
    user_id: str,
    token_hash: str,
    expires_at: str,
    user_agent: str | None,
) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                _sql(
                    """
                    INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, revoked_at, created_at, user_agent)
                    VALUES (?, ?, ?, ?, NULL, ?, ?)
                    """
                ),
                (token_id, user_id, token_hash, expires_at, _now(), user_agent),
            )
            conn.commit()
        finally:
            conn.close()


def get_refresh_by_hash(token_hash: str) -> dict[str, Any] | None:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(
                _sql("SELECT * FROM refresh_tokens WHERE token_hash = ?"),
                (token_hash,),
            ).fetchone()
            return _row(row)
        finally:
            conn.close()


def revoke_refresh(token_id: str) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                _sql("UPDATE refresh_tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL"),
                (_now(), token_id),
            )
            conn.commit()
        finally:
            conn.close()


def revoke_user_refresh(user_id: str) -> None:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                _sql("UPDATE refresh_tokens SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL"),
                (_now(), user_id),
            )
            conn.commit()
        finally:
            conn.close()


def insert_attachment(
    attachment_id: str,
    user_id: str,
    kind: str,
    filename: str,
    mime: str,
    byte_size: int,
    sha256: str,
    rel_path: str,
    content_b64: str | None = None,
) -> dict[str, Any]:
    with _lock:
        conn = connect()
        try:
            conn.execute(
                _sql(
                    """
                    INSERT INTO attachments (
                        id, user_id, kind, filename, mime, byte_size, sha256, rel_path, content_b64, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                ),
                (attachment_id, user_id, kind, filename, mime, byte_size, sha256, rel_path, content_b64, _now()),
            )
            conn.commit()
        finally:
            conn.close()
    row = get_attachment(attachment_id)
    assert row
    return row


def get_attachment(attachment_id: str) -> dict[str, Any] | None:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(_sql("SELECT * FROM attachments WHERE id = ?"), (attachment_id,)).fetchone()
            return _row(row)
        finally:
            conn.close()


def find_attachment_by_hash(user_id: str, kind: str, sha256: str) -> dict[str, Any] | None:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(
                _sql(
                    """
                    SELECT * FROM attachments
                    WHERE user_id = ? AND kind = ? AND sha256 = ?
                    ORDER BY created_at DESC LIMIT 1
                    """
                ),
                (user_id, kind, sha256),
            ).fetchone()
            return _row(row)
        finally:
            conn.close()


def list_attachments(user_id: str, limit: int = 80) -> list[dict[str, Any]]:
    cap = min(80, max(1, limit))
    with _lock:
        conn = connect()
        try:
            rows = conn.execute(
                _sql(
                    """
                    SELECT * FROM attachments WHERE user_id = ?
                    ORDER BY created_at DESC LIMIT ?
                    """
                ),
                (user_id, cap),
            ).fetchall()
            return [item for item in (_row(row) for row in rows) if item]
        finally:
            conn.close()


def attachment_quota(user_id: str) -> tuple[int, int]:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(
                _sql(
                    "SELECT COUNT(*) AS n, COALESCE(SUM(byte_size), 0) AS bytes FROM attachments WHERE user_id = ?"
                ),
                (user_id,),
            ).fetchone()
            data = _row(row) or {}
            return int(data.get("n") or 0), int(data.get("bytes") or 0)
        finally:
            conn.close()


def delete_attachment(attachment_id: str) -> dict[str, Any] | None:
    row = get_attachment(attachment_id)
    if not row:
        return None
    with _lock:
        conn = connect()
        try:
            conn.execute(_sql("DELETE FROM attachments WHERE id = ?"), (attachment_id,))
            conn.commit()
        finally:
            conn.close()
    return row


def public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row.get("display_name"),
        "role": row["role"],
    }


def public_attachment(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "filename": row["filename"],
        "mime": row["mime"],
        "byte_size": row["byte_size"],
        "sha256": row["sha256"],
        "created_at": row["created_at"],
    }


_JSON_FIELDS = {
    "input_json": "input",
    "bible_json": "bible",
    "structure_json": "structure",
    "storyboard_json": "storyboard",
    "timeline_json": "timeline",
    "artifacts_json": "artifacts",
    "storage_json": "storage",
}


def public_job(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    for src, dest in _JSON_FIELDS.items():
        raw = payload.pop(src, None)
        if not raw:
            continue
        try:
            payload[dest] = json.loads(raw)
        except json.JSONDecodeError:
            payload[dest] = raw
    return payload


def artifacts_of(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("artifacts_json") or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def storage_of(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("storage_json") or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def list_all_jobs(
    limit: int = 50,
    status: str | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    cap = min(200, max(1, limit))
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if user_id:
        clauses.append("user_id = ?")
        params.append(user_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(cap)
    with _lock:
        conn = connect()
        try:
            rows = conn.execute(
                _sql(f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?"),
                params,
            ).fetchall()
            return [item for item in (_row(row) for row in rows) if item]
        finally:
            conn.close()


def delete_job(job_id: str) -> dict[str, Any] | None:
    row = get_job(job_id)
    if not row:
        return None
    with _lock:
        conn = connect()
        try:
            conn.execute(_sql("DELETE FROM jobs WHERE id = ?"), (job_id,))
            conn.commit()
        finally:
            conn.close()
    return row


def count_operators() -> int:
    with _lock:
        conn = connect()
        try:
            row = conn.execute(_sql("SELECT COUNT(*) AS n FROM users WHERE role = ?"), ("operator",)).fetchone()
            data = _row(row) or {}
            return int(data.get("n") or 0)
        finally:
            conn.close()


def admin_stats() -> dict[str, Any]:
    with _lock:
        conn = connect()
        try:
            u_row = _row(conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()) or {}
            op_row = (
                _row(conn.execute(_sql("SELECT COUNT(*) AS n FROM users WHERE role = ?"), ("operator",)).fetchone())
                or {}
            )
            j_rows = conn.execute("SELECT status, COUNT(*) AS n FROM jobs GROUP BY status").fetchall()
            att_row = (
                _row(
                    conn.execute(
                        "SELECT COUNT(*) AS n, COALESCE(SUM(byte_size), 0) AS bytes FROM attachments"
                    ).fetchone()
                )
                or {}
            )
        finally:
            conn.close()
    by_status: dict[str, int] = {"queued": 0, "running": 0, "done": 0, "failed": 0}
    total_jobs = 0
    for r in j_rows:
        item = _row(r) or {}
        st = str(item.get("status") or "")
        n = int(item.get("n") or 0)
        total_jobs += n
        if st:
            by_status[st] = n
    return {
        "users_total": int(u_row.get("n") or 0),
        "operators_total": int(op_row.get("n") or 0),
        "jobs_total": total_jobs,
        "jobs_by_status": by_status,
        "attachments_total": int(att_row.get("n") or 0),
        "attachments_bytes": int(att_row.get("bytes") or 0),
        "db_backend": "cloudflare-d1" if is_d1() else ("postgres" if is_postgres() else "sqlite"),
    }


def signup_enabled() -> bool:
    stored = get_setting("signup_enabled")
    if stored is not None:
        return stored.strip().lower() not in ("0", "false", "no", "off")
    raw = os.environ.get("AUTH_SIGNUP", "1" if config.AUTH_SIGNUP else "0").strip().lower()
    return raw not in ("0", "false", "no", "off")


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
