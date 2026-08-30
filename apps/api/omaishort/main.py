from __future__ import annotations

from contextlib import asynccontextmanager
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from omaishort import db
from omaishort.config import DATA_DIR
from omaishort.pipeline import run_job
from omaishort_schema.models import StoryInput


@asynccontextmanager
async def lifespan(_app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "jobs").mkdir(parents=True, exist_ok=True)
    db.init_db()
    yield


app = FastAPI(title="omaishort", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/files", StaticFiles(directory=str(DATA_DIR)), name="files")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "omaishort", "health": "/health", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/jobs")
async def create_job(story: StoryInput, background: BackgroundTasks) -> dict[str, str]:
    job_id = uuid.uuid4().hex[:12]
    db.create_job(job_id, story.model_dump_json())
    background.add_task(run_job, job_id)
    return {"id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def read_job(job_id: str) -> dict:
    row = db.get_job(job_id)
    if not row:
        raise HTTPException(404, "job not found")
    return db.public_job(row)


@app.get("/jobs/{job_id}/artifacts")
def list_artifacts(job_id: str) -> dict:
    row = db.get_job(job_id)
    if not row:
        raise HTTPException(404, "job not found")
    return {
        "id": job_id,
        "stage": row["stage"],
        "status": row["status"],
        "artifacts": db.artifacts_of(row),
    }


@app.get("/jobs/{job_id}/download")
def download_mp4(job_id: str) -> FileResponse:
    row = db.get_job(job_id)
    if not row:
        raise HTTPException(404, "job not found")
    mp4 = db.artifacts_of(row).get("mp4")
    if not mp4 or not Path(str(mp4)).exists():
        raise HTTPException(404, "mp4 not ready")
    return FileResponse(str(mp4), media_type="video/mp4", filename=f"omaishort-{job_id}.mp4")
