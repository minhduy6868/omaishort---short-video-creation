from __future__ import annotations

from pathlib import Path

from omaishort.config import DATA_DIR


def job_dir(job_id: str) -> Path:
    path = DATA_DIR / "jobs" / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def refs_dir(job_id: str) -> Path:
    path = job_dir(job_id) / "refs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def stills_dir(job_id: str) -> Path:
    path = job_dir(job_id) / "stills"
    path.mkdir(parents=True, exist_ok=True)
    return path


def audio_dir(job_id: str) -> Path:
    path = job_dir(job_id) / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_dir(job_id: str) -> Path:
    path = job_dir(job_id) / "render"
    path.mkdir(parents=True, exist_ok=True)
    return path
