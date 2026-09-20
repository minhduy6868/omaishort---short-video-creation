from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import uuid

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from omaishort import config, db, uploads
from omaishort.auth import (
    CurrentUser,
    LoginBody,
    RefreshBody,
    RegisterBody,
    authenticate,
    clear_auth_cookies,
    hash_refresh,
    register_user,
    require_job,
    rotate_refresh,
    session_from_user,
    set_auth_cookies,
    token_payload,
)
from omaishort.files import resolve_public_file
from omaishort.pipeline import run_job
from omaishort.providers.llm import llm_status
from omaishort.providers.tts import list_voices
from omaishort_schema.models import AttachmentKind, StoryInput


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "jobs").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "attachments").mkdir(parents=True, exist_ok=True)
    db.init_db()
    yield


app = FastAPI(title="omaishort", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "omaishort", "health": "/health", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/providers")
def providers() -> dict[str, object]:
    return llm_status()


@app.get("/voices")
def voices(language: str | None = None) -> dict[str, object]:
    return {"voices": list_voices(language)}


@app.post("/auth/register", status_code=201)
def auth_register(body: RegisterBody, request: Request, response: Response) -> dict:
    user = register_user(body)
    return session_from_user(user, response, request.headers.get("user-agent"))


@app.post("/auth/login")
def auth_login(body: LoginBody, request: Request, response: Response) -> dict:
    user = authenticate(body)
    return session_from_user(user, response, request.headers.get("user-agent"))


@app.post("/auth/refresh")
def auth_refresh(request: Request, response: Response, body: RefreshBody | None = None) -> dict:
    raw = (body.refresh_token if body else None) or request.cookies.get("omaishort_rt")
    if not raw:
        raise HTTPException(401, "not authenticated")
    user, refresh = rotate_refresh(raw, request.headers.get("user-agent"))
    payload = token_payload(user, refresh)
    set_auth_cookies(response, payload["access_token"], refresh)
    return payload


@app.post("/auth/logout", status_code=204, response_model=None)
def auth_logout(request: Request, response: Response, body: RefreshBody | None = None) -> None:
    raw = (body.refresh_token if body else None) or request.cookies.get("omaishort_rt")
    if raw:
        row = db.get_refresh_by_hash(hash_refresh(raw))
        if row:
            db.revoke_refresh(row["id"])
    clear_auth_cookies(response)


@app.get("/auth/me")
def auth_me(user: CurrentUser) -> dict:
    return db.public_user(user)


@app.post("/attachments", status_code=201)
async def create_attachment(
    user: CurrentUser,
    kind: AttachmentKind = Query(...),
    file: UploadFile = File(...),
) -> dict:
    row = await uploads.save_upload(user["id"], kind, file)
    return db.public_attachment(row)


@app.get("/attachments")
def list_attachment_rows(user: CurrentUser) -> dict:
    return {"attachments": [db.public_attachment(row) for row in db.list_attachments(user["id"])]}


@app.get("/attachments/{attachment_id}")
def read_attachment(attachment_id: str, user: CurrentUser) -> dict:
    row = uploads.require_owned_attachment(attachment_id, user["id"])
    return db.public_attachment(row)


@app.get("/attachments/{attachment_id}/file")
def download_attachment(attachment_id: str, user: CurrentUser) -> FileResponse:
    row = uploads.require_owned_attachment(attachment_id, user["id"])
    path = uploads.attachment_abs(row)
    return FileResponse(path, media_type=row["mime"], filename=row["filename"])


@app.delete("/attachments/{attachment_id}", status_code=204, response_model=None)
def remove_attachment(attachment_id: str, user: CurrentUser) -> None:
    uploads.delete_owned(attachment_id, user["id"])


@app.post("/jobs")
async def create_job(story: StoryInput, background: BackgroundTasks, user: CurrentUser) -> dict[str, str]:
    uploads.load_job_files(user["id"], story.attachments)
    job_id = uuid.uuid4().hex[:12]
    db.create_job(job_id, story.model_dump_json(), user_id=user["id"])
    background.add_task(run_job, job_id)
    return {"id": job_id, "status": "queued"}


@app.get("/jobs")
def list_job_rows(user: CurrentUser, limit: int = Query(20, ge=1, le=50)) -> dict:
    return {"jobs": [db.public_job(row) for row in db.list_jobs(user["id"], limit)]}


@app.get("/jobs/{job_id}")
def read_job(job_id: str, user: CurrentUser) -> dict:
    return db.public_job(require_job(job_id, user))


@app.get("/jobs/{job_id}/artifacts")
def list_artifacts(job_id: str, user: CurrentUser) -> dict:
    row = require_job(job_id, user)
    return {
        "id": job_id,
        "stage": row["stage"],
        "status": row["status"],
        "artifacts": db.artifacts_of(row),
    }


@app.get("/jobs/{job_id}/download")
def download_mp4(job_id: str, user: CurrentUser) -> FileResponse:
    row = require_job(job_id, user)
    mp4 = db.artifacts_of(row).get("mp4")
    if not mp4:
        raise HTTPException(404, "mp4 not ready")
    path = Path(str(mp4)).resolve()
    try:
        path.relative_to(config.DATA_DIR.resolve())
    except ValueError:
        raise HTTPException(404, "mp4 not ready") from None
    if not path.is_file():
        raise HTTPException(404, "mp4 not ready")
    return FileResponse(
        str(path),
        media_type="video/mp4",
        filename=f"omaishort-{job_id}.mp4",
        content_disposition_type="inline",
    )


@app.get("/files/{path:path}")
def read_data_file(path: str, user: CurrentUser) -> FileResponse:
    dest = resolve_public_file(path, user)
    return FileResponse(dest)
