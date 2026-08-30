from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from omaishort.config import DATA_DIR

DB_PATH = DATA_DIR / "omaishort.db"
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


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
                    progress TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def create_job(job_id: str, input_json: str) -> None:
    now = _now()
    with _lock:
        conn = connect()
        try:
            conn.execute(
                """
                INSERT INTO jobs (id, status, stage, error, created_at, updated_at, input_json, progress)
                VALUES (?, 'queued', 'queued', NULL, ?, ?, ?, 'queued')
                """,
                (job_id, now, now, input_json),
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
            conn.execute(f"UPDATE jobs SET {assignments} WHERE id = ?", values)
            conn.commit()
        finally:
            conn.close()


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        conn = connect()
        try:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


_JSON_FIELDS = {
    "input_json": "input",
    "bible_json": "bible",
    "structure_json": "structure",
    "storyboard_json": "storyboard",
    "timeline_json": "timeline",
    "artifacts_json": "artifacts",
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


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
