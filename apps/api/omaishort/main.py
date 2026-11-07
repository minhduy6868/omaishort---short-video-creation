from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import threading
import uuid

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from omaishort import admin, config, db, storage, uploads
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
from omaishort.pipeline import fill_missing_stills, regenerate_scene_still, rerender_job, run_job
from omaishort.providers.elevenlabs_hub import ElevenLabsHubBody, load_status, update as update_elevenlabs
from omaishort.providers.llm import llm_status
from omaishort.providers.tts import list_voices
from omaishort_schema.models import (
    AttachmentKind,
    Camera,
    CharacterBible,
    MixSettings,
    Motion,
    Shot,
    StoryInput,
    StoryStructure,
    Storyboard,
    is_editorial,
)


def _resume_interrupted_jobs() -> None:
    """A restart kills in-process work. The row stays, so run it again instead of leaving it frozen."""
    for job_id in db.interrupted_job_ids():
        db.update_job(job_id, status="queued", progress="resume", error=None)

        def _run(jid: str = job_id) -> None:
            asyncio.run(run_job(jid))

        threading.Thread(target=_run, name=f"resume-{job_id}", daemon=True).start()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "jobs").mkdir(parents=True, exist_ok=True)
    (config.DATA_DIR / "attachments").mkdir(parents=True, exist_ok=True)
    db.init_db()
    _resume_interrupted_jobs()
    yield


app = FastAPI(title="omaishort", version="0.1.0", lifespan=lifespan)
app.include_router(admin.router)
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


@app.get("/robots.txt")
def robots_txt() -> Response:
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /vi\n"
        "Allow: /en\n"
        "Allow: /ja\n"
        "Allow: /vi/privacy\n"
        "Allow: /en/privacy\n"
        "Allow: /ja/privacy\n"
        "Allow: /vi/terms\n"
        "Allow: /en/terms\n"
        "Allow: /ja/terms\n"
        "Allow: /vi/cookies\n"
        "Allow: /en/cookies\n"
        "Allow: /ja/cookies\n"
        "Disallow: /admin\n"
        "Disallow: /account\n"
        "Disallow: /auth/\n"
        "Disallow: /jobs\n\n"
        "Sitemap: https://omaishort.com/sitemap.xml\n"
    )
    return Response(content=body, media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml")
def sitemap_xml() -> Response:
    urls = (
        "https://omaishort.com/vi",
        "https://omaishort.com/en",
        "https://omaishort.com/ja",
        "https://omaishort.com/vi/privacy",
        "https://omaishort.com/en/privacy",
        "https://omaishort.com/ja/privacy",
        "https://omaishort.com/vi/terms",
        "https://omaishort.com/en/terms",
        "https://omaishort.com/ja/terms",
        "https://omaishort.com/vi/cookies",
        "https://omaishort.com/en/cookies",
        "https://omaishort.com/ja/cookies",
    )
    items = "".join(f"<url><loc>{u}</loc></url>" for u in urls)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{items}</urlset>"
    )
    return Response(content=xml, media_type="application/xml; charset=utf-8")


_chatgpt_gate = threading.Lock()
_chatgpt_opening = False
_grok_gate = threading.Lock()
_grok_opening = False


@app.get("/providers")
def providers() -> dict[str, object]:
    return {
        **llm_status(),
        "chatgpt_opening": bool(_chatgpt_opening),
        "grok_opening": bool(_grok_opening),
    }


@app.post("/providers/chatgpt-login")
def start_chatgpt_login(_user: CurrentUser) -> dict[str, str]:
    """Open headed Chrome on this PC until a ChatGPT session cookie exists."""
    global _chatgpt_opening
    from omaishort.providers.chatgpt_web import login as chatgpt_login
    from omaishort.providers.chrome_profile import playwright_ok

    if not playwright_ok():
        raise HTTPException(status_code=503, detail="Playwright Chromium is not installed")
    from omaishort.providers import chatgpt_web

    if chatgpt_web._LOCK.locked():
        raise HTTPException(status_code=409, detail="Một job đang dùng phiên ChatGPT. Chờ job viết lời xong rồi bấm lại.")

    opened = threading.Event()
    box: dict[str, str] = {}

    def _on_open(exc: BaseException | None) -> None:
        if exc is not None:
            from omaishort.providers.chatgpt_web import chrome_launch_error

            box["error"] = chrome_launch_error(exc)
        opened.set()

    def _run() -> None:
        global _chatgpt_opening
        try:
            asyncio.run(chatgpt_login(_on_open))
        finally:
            opened.set()
            with _chatgpt_gate:
                _chatgpt_opening = False

    with _chatgpt_gate:
        if _chatgpt_opening:
            raise HTTPException(status_code=409, detail="Cửa sổ ChatGPT đang mở. Đăng nhập trên cửa sổ đó, hoặc đóng rồi bấm lại.")
        _chatgpt_opening = True
    threading.Thread(target=_run, name="chatgpt-login", daemon=True).start()
    opened.wait(30)
    if box.get("error"):
        with _chatgpt_gate:
            _chatgpt_opening = False
        raise HTTPException(status_code=503, detail=box["error"])
    return {"status": "opening"}


@app.post("/providers/chatgpt-open")
def open_chatgpt_content(_user: CurrentUser) -> dict[str, str]:
    """Open today's ChatGPT thread in Chrome so the operator can edit the script."""
    global _chatgpt_opening
    from omaishort.providers.chatgpt_web import is_authed, open_content
    from omaishort.providers.chrome_profile import playwright_ok

    if not is_authed():
        raise HTTPException(status_code=409, detail="Đăng nhập ChatGPT trước")
    if not playwright_ok():
        raise HTTPException(status_code=503, detail="Playwright Chromium is not installed")

    def _run() -> None:
        global _chatgpt_opening
        try:
            asyncio.run(open_content())
        finally:
            with _chatgpt_gate:
                _chatgpt_opening = False

    with _chatgpt_gate:
        if _chatgpt_opening:
            raise HTTPException(status_code=409, detail="Cửa sổ ChatGPT đang mở. Đăng nhập trên cửa sổ đó, hoặc đóng rồi bấm lại.")
        _chatgpt_opening = True
    threading.Thread(target=_run, name="chatgpt-content", daemon=True).start()
    return {"status": "opening"}


@app.post("/providers/chatgpt-check")
async def check_chatgpt_status(_user: CurrentUser) -> dict[str, object]:
    """Verify live ChatGPT Web session and report whether ChatGPT or Wikipedia fallback was used."""
    from omaishort.providers.chatgpt_web import check_live_session

    if _chatgpt_opening:
        raise HTTPException(
            status_code=409,
            detail="Cửa sổ ChatGPT đang mở. Đóng cửa sổ đó trước khi kiểm tra kết nối.",
        )
    return await check_live_session()


@app.post("/providers/grok-login")
def start_grok_login(_user: CurrentUser) -> dict[str, str]:
    """Open headed Chrome on this PC until a Grok SSO cookie exists. Drama motion only."""
    global _grok_opening
    from omaishort.providers.chrome_profile import playwright_ok
    from omaishort.providers.grok_web import chrome_launch_error
    from omaishort.providers.grok_web import login as grok_login
    from omaishort.providers.grok_web import session_lock as grok_busy

    if not playwright_ok():
        raise HTTPException(status_code=503, detail="Playwright Chromium is not installed")
    if grok_busy.locked():
        raise HTTPException(status_code=409, detail="Một job đang dùng phiên Grok để dựng chuyển động. Chờ cảnh đó xong rồi bấm lại.")

    opened = threading.Event()
    box: dict[str, str] = {}

    def _on_open(exc: BaseException | None) -> None:
        if exc is not None:
            box["error"] = chrome_launch_error(exc)
        opened.set()

    def _run() -> None:
        global _grok_opening
        try:
            asyncio.run(grok_login(on_open=_on_open))
        except Exception as exc:
            box.setdefault("error", chrome_launch_error(exc))
            opened.set()
        finally:
            opened.set()
            with _grok_gate:
                _grok_opening = False

    with _grok_gate:
        if _grok_opening:
            raise HTTPException(status_code=409, detail="Cửa sổ Grok đang mở. Đăng nhập trên cửa sổ đó, hoặc đóng rồi bấm lại.")
        _grok_opening = True
    threading.Thread(target=_run, name="grok-login", daemon=True).start()
    opened.wait(30)
    if box.get("error"):
        with _grok_gate:
            _grok_opening = False
        raise HTTPException(status_code=503, detail=box["error"])
    return {"status": "opening"}


@app.get("/providers/elevenlabs")
def elevenlabs_hub(_user: CurrentUser) -> dict[str, object]:
    return load_status()


@app.put("/providers/elevenlabs")
def save_elevenlabs_hub(body: ElevenLabsHubBody, _user: CurrentUser) -> dict[str, object]:
    try:
        return update_elevenlabs(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/voices")
def voices(language: str | None = None) -> dict[str, object]:
    return {"voices": list_voices(language)}


SITE_THEMES = ("brutal", "soft")


class SiteThemeBody(BaseModel):
    theme: str


def site_theme_value() -> str:
    value = db.get_setting("site_theme")
    return value if value in SITE_THEMES else SITE_THEMES[0]


@app.get("/site/theme")
def read_site_theme() -> dict[str, object]:
    return {"theme": site_theme_value(), "themes": list(SITE_THEMES)}


@app.put("/site/theme")
def save_site_theme(body: SiteThemeBody, user: CurrentUser) -> dict[str, object]:
    if user.get("role") != "operator":
        raise HTTPException(status_code=403, detail="Chỉ admin (operator) đổi được giao diện.")
    if body.theme not in SITE_THEMES:
        raise HTTPException(status_code=422, detail=f"theme must be one of {', '.join(SITE_THEMES)}")
    db.set_setting("site_theme", body.theme)
    return {"theme": body.theme, "themes": list(SITE_THEMES)}


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
    out = []
    for row in db.list_jobs(user["id"], limit):
        pub = db.public_job(row)
        pub["storage"] = storage.inspect_job_storage(str(row["id"]), row)
        out.append(pub)
    return {"jobs": out}


@app.get("/jobs/{job_id}")
def read_job(job_id: str, user: CurrentUser) -> dict:
    row = require_job(job_id, user)
    pub = db.public_job(row)
    pub["storage"] = storage.inspect_job_storage(job_id, row)
    return pub


class DraftScriptBody(BaseModel):
    kind: str = "knowledge"
    text: str
    language: str = "vi"
    target_seconds: int = 90
    source_url: str | None = None
    script_brief: str | None = None


class RewriteScriptBody(BaseModel):
    kind: str = "knowledge"
    title: str = ""
    language: str = "vi"
    target_seconds: int = 90
    beat: str = "all"
    instruction: str = ""
    structure: dict[str, object]


@app.post("/scripts/draft")
async def draft_script_endpoint(body: DraftScriptBody, _user: CurrentUser) -> dict[str, object]:
    from omaishort.engine.analyzer import draft_content_structure

    return await draft_content_structure(
        kind=body.kind,
        text=body.text,
        language=body.language,
        target_seconds=body.target_seconds,
        source_url=body.source_url,
        script_brief=body.script_brief,
    )


@app.post("/scripts/rewrite")
async def rewrite_script_endpoint(body: RewriteScriptBody, _user: CurrentUser) -> dict[str, object]:
    from omaishort.engine.analyzer import rewrite_content_beats

    updated, provider = await rewrite_content_beats(
        body.structure,
        kind=body.kind,
        language=body.language,
        target_seconds=body.target_seconds,
        beat=body.beat,
        instruction=body.instruction,
        title=body.title,
    )
    text = "\n\n".join(
        str(updated.get(k) or "").strip()
        for k in ("hook", "conflict", "rising_action", "twist", "ending")
        if str(updated.get(k) or "").strip()
    )
    return {"structure": updated, "provider": provider, "text": text}


class JobMetaPatchBody(BaseModel):
    title: str | None = None
    voice_id: str | None = None
    language: str | None = None
    target_seconds: int | None = None
    script_brief: str | None = None
    bgm_enabled: bool | None = None
    bgm_volume: float | None = None
    logo_enabled: bool | None = None


def _require_idle_job(row: dict) -> None:
    if row.get("status") in {"running", "queued"}:
        raise HTTPException(
            status_code=409,
            detail="Job đang chạy, vui lòng chờ hoàn tất trước khi chỉnh sửa hoặc render lại.",
        )


@app.patch("/jobs/{job_id}")
def patch_job_meta(job_id: str, body: JobMetaPatchBody, user: CurrentUser) -> dict:
    from omaishort.paths import job_dir

    row = require_job(job_id, user)
    _require_idle_job(row)
    story = StoryInput.model_validate_json(row["input_json"])
    updates: dict[str, object] = {}
    if body.voice_id is not None:
        updates["voice_id"] = body.voice_id.strip() or story.voice_id
    if body.language is not None and body.language.strip():
        updates["language"] = body.language.strip()[:8]
    if body.target_seconds is not None:
        updates["target_seconds"] = max(15, min(600, int(body.target_seconds)))
    if body.script_brief is not None:
        updates["script_brief"] = body.script_brief.strip() or None
    if any(v is not None for v in (body.bgm_enabled, body.bgm_volume, body.logo_enabled)):
        mix = (story.mix or MixSettings()).model_copy(
            update={
                k: v
                for k, v in {
                    "bgm_enabled": body.bgm_enabled,
                    "bgm_volume": body.bgm_volume,
                    "logo_enabled": body.logo_enabled,
                }.items()
                if v is not None
            }
        )
        updates["mix"] = mix
    if updates:
        story = story.model_copy(update=updates)

    board_json = row.get("storyboard_json")
    if board_json:
        board = Storyboard.model_validate_json(board_json)
        if body.title is not None and body.title.strip():
            board.title = body.title.strip()[:200]
        if body.language is not None and body.language.strip():
            board.language = body.language.strip()[:8]
        if body.target_seconds is not None:
            board.target_seconds = float(max(15, min(600, int(body.target_seconds))))
        db.dump_json(job_dir(job_id) / "storyboard.json", board.model_dump(mode="json"))
        board_json = board.model_dump_json()

    db.update_job(job_id, input_json=story.model_dump_json(), storyboard_json=board_json)
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    return pub


class StructurePatchBody(BaseModel):
    hook: str | None = None
    conflict: str | None = None
    rising_action: str | None = None
    twist: str | None = None
    ending: str | None = None
    hook_sec: float | None = None
    conflict_sec: float | None = None
    rising_sec: float | None = None
    twist_sec: float | None = None
    ending_sec: float | None = None
    sync_scenes: bool = True


def _apply_structure_to_job(
    job_id: str,
    row: dict,
    structure: StoryStructure,
    *,
    sync_scenes: bool = True,
) -> dict:
    from omaishort.engine.fallback import BEAT_ORDER, fallback_analyze, fallback_plan, infer_beat
    from omaishort.engine.image_prompts import build_scene_prompt, fill_image_prompts
    from omaishort.engine.rescale import repair_scene_shots
    from omaishort.paths import job_dir

    story = StoryInput.model_validate_json(row["input_json"])
    bible = (
        CharacterBible.model_validate_json(row["bible_json"])
        if row.get("bible_json")
        else fallback_analyze(story)[0]
    )
    beats = [
        structure.hook,
        structure.conflict,
        structure.rising_action,
        structure.twist,
        structure.ending,
    ]
    secs = [
        structure.hook_sec,
        structure.conflict_sec,
        structure.rising_sec,
        structure.twist_sec,
        structure.ending_sec,
    ]
    story = story.model_copy(update={"text": "\n\n".join(beats)})

    board_json = row.get("storyboard_json")
    if sync_scenes:
        if board_json:
            board = Storyboard.model_validate_json(board_json)
            if len(board.scenes) == 5:
                for idx, scene in enumerate(board.scenes):
                    scene.dialogue_or_vo = beats[idx]
                    if secs[idx] and secs[idx] >= 1.0:
                        scene.duration_sec = round(float(secs[idx]), 2)
                    repair_scene_shots(scene)
                    scene.image_prompt = build_scene_prompt(scene, bible)
            elif is_editorial(story.kind):
                board = fallback_plan(story, bible, structure)
                fill_image_prompts(board, bible)
            else:
                total = max(1, len(board.scenes))
                beat_map = dict(zip(BEAT_ORDER, beats))
                by_beat: dict[str, list] = {b: [] for b in BEAT_ORDER}
                for idx, scene in enumerate(board.scenes):
                    bname = infer_beat(scene, idx, total)
                    by_beat.setdefault(bname, []).append(scene)
                for bname, group in by_beat.items():
                    text_block = (beat_map.get(bname) or "").strip()
                    if not group or not text_block:
                        continue
                    if len(group) == 1:
                        group[0].dialogue_or_vo = text_block
                        group[0].mood = text_block[:80]
                    else:
                        import re as _re

                        sents = [s.strip() for s in _re.split(r"(?<=[.!?…])\s+", text_block) if s.strip()] or [text_block]
                        for s_idx, sc in enumerate(group):
                            sc.mood = text_block[:80]
                            if s_idx < len(sents):
                                sc.dialogue_or_vo = sents[s_idx] if s_idx < len(group) - 1 else " ".join(sents[s_idx:])
                    for sc in group:
                        repair_scene_shots(sc)
        else:
            board = fallback_plan(story, bible, structure)
            fill_image_prompts(board, bible)
        db.dump_json(job_dir(job_id) / "storyboard.json", board.model_dump(mode="json"))
        board_json = board.model_dump_json()

    db.dump_json(job_dir(job_id) / "structure.json", structure.model_dump(mode="json"))
    db.update_job(
        job_id,
        input_json=story.model_dump_json(),
        structure_json=structure.model_dump_json(),
        storyboard_json=board_json,
    )
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    return pub


@app.patch("/jobs/{job_id}/structure")
def patch_job_structure(job_id: str, body: StructurePatchBody, user: CurrentUser) -> dict:
    from omaishort.engine.fallback import fallback_analyze

    row = require_job(job_id, user)
    _require_idle_job(row)
    story = StoryInput.model_validate_json(row["input_json"])
    current = (
        StoryStructure.model_validate_json(row["structure_json"])
        if row.get("structure_json")
        else fallback_analyze(story)[1]
    )
    updates: dict[str, object] = {}
    for key in ("hook", "conflict", "rising_action", "twist", "ending"):
        val = getattr(body, key)
        if val is not None and val.strip():
            updates[key] = val.strip()
    for sec_key in ("hook_sec", "conflict_sec", "rising_sec", "twist_sec", "ending_sec"):
        sec_val = getattr(body, sec_key)
        if sec_val is not None and float(sec_val) >= 1.0:
            updates[sec_key] = round(float(sec_val), 2)
    structure = current.model_copy(update=updates)
    return _apply_structure_to_job(job_id, row, structure, sync_scenes=body.sync_scenes)


class JobAiRewriteBody(BaseModel):
    beat: str = "all"
    instruction: str = ""
    sync_scenes: bool = True


@app.post("/jobs/{job_id}/ai-rewrite")
async def ai_rewrite_job_structure(job_id: str, body: JobAiRewriteBody, user: CurrentUser) -> dict:
    from omaishort.engine.analyzer import rewrite_content_beats
    from omaishort.engine.fallback import fallback_analyze

    row = require_job(job_id, user)
    _require_idle_job(row)
    story = StoryInput.model_validate_json(row["input_json"])
    current = (
        StoryStructure.model_validate_json(row["structure_json"])
        if row.get("structure_json")
        else fallback_analyze(story)[1]
    )
    board_title = ""
    if row.get("storyboard_json"):
        try:
            board_title = Storyboard.model_validate_json(row["storyboard_json"]).title
        except Exception:
            board_title = ""
    rewritten_dict, provider = await rewrite_content_beats(
        current.model_dump(mode="json"),
        kind=story.kind.value,
        language=story.language,
        target_seconds=story.target_seconds,
        beat=body.beat,
        instruction=body.instruction,
        title=board_title or story.text[:80],
    )
    structure = StoryStructure.model_validate(rewritten_dict)
    pub = _apply_structure_to_job(job_id, row, structure, sync_scenes=body.sync_scenes)
    pub["rewrite_provider"] = provider
    return pub


@app.patch("/jobs/{job_id}/bible")
def patch_job_bible(job_id: str, bible: CharacterBible, user: CurrentUser) -> dict:
    from omaishort.engine.fallback import stamp_identity_locks
    from omaishort.engine.image_prompts import fill_image_prompts
    from omaishort.paths import job_dir

    row = require_job(job_id, user)
    _require_idle_job(row)
    locked = stamp_identity_locks(bible)
    board_json = row.get("storyboard_json")
    if board_json:
        board = Storyboard.model_validate_json(board_json)
        fill_image_prompts(board, locked)
        db.dump_json(job_dir(job_id) / "storyboard.json", board.model_dump(mode="json"))
        board_json = board.model_dump_json()
    db.dump_json(job_dir(job_id) / "bible.json", locked.model_dump(mode="json"))
    db.update_job(job_id, bible_json=locked.model_dump_json(), storyboard_json=board_json)
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    return pub


class ScenePatchBody(BaseModel):
    dialogue_or_vo: str | None = None
    action: str | None = None
    image_prompt: str | None = None
    location: str | None = None
    emotion: str | None = None
    mood: str | None = None
    lighting: str | None = None
    duration_sec: float | None = None
    camera: str | None = None
    motion: str | None = None


@app.patch("/jobs/{job_id}/scenes/{scene_index}")
def patch_job_scene(
    job_id: str,
    scene_index: int,
    body: ScenePatchBody,
    user: CurrentUser,
) -> dict:
    from omaishort.engine.fallback import fallback_analyze
    from omaishort.engine.image_prompts import build_scene_prompt
    from omaishort.engine.rescale import repair_scene_shots
    from omaishort.paths import job_dir

    row = require_job(job_id, user)
    _require_idle_job(row)
    if not row.get("storyboard_json"):
        raise HTTPException(409, "Storyboard chưa sẵn sàng")
    story = StoryInput.model_validate_json(row["input_json"])
    bible = (
        CharacterBible.model_validate_json(row["bible_json"])
        if row.get("bible_json")
        else fallback_analyze(story)[0]
    )
    board = Storyboard.model_validate_json(row["storyboard_json"])
    target = next((s for s in board.scenes if s.index == scene_index), None)
    if target is None and 1 <= scene_index <= len(board.scenes):
        target = board.scenes[scene_index - 1]
    if target is None:
        raise HTTPException(404, f"Không tìm thấy cảnh {scene_index}")

    old_prompt = (target.image_prompt or "").strip()
    old_auto_prompt = build_scene_prompt(target, bible).strip()

    if body.dialogue_or_vo is not None and body.dialogue_or_vo.strip():
        target.dialogue_or_vo = body.dialogue_or_vo.strip()
    if body.action is not None and body.action.strip():
        target.action = body.action.strip()
    if body.location is not None and body.location.strip():
        target.location = body.location.strip()
    if body.emotion is not None and body.emotion.strip():
        target.emotion = body.emotion.strip()
    if body.mood is not None and body.mood.strip():
        target.mood = body.mood.strip()
    if body.lighting is not None and body.lighting.strip():
        target.lighting = body.lighting.strip()
    if body.duration_sec is not None and float(body.duration_sec) >= 1.0:
        target.duration_sec = round(float(body.duration_sec), 2)
    if body.camera is not None and body.camera in Camera._value2member_map_:
        cam = Camera(body.camera)
        if target.shots:
            target.shots[0].camera = cam
        else:
            target.shots = [
                Shot(
                    camera=cam,
                    motion=Motion.zoom_in,
                    t_start=0,
                    t_end=target.duration_sec,
                    still_id=target.still_id,
                )
            ]
    if body.motion is not None and body.motion in Motion._value2member_map_:
        mot = Motion(body.motion)
        if target.shots:
            target.shots[0].motion = mot
            if mot == Motion.hold:
                for sh in target.shots[1:]:
                    sh.motion = Motion.hold
        else:
            target.shots = [
                Shot(
                    camera=Camera.medium,
                    motion=mot,
                    t_start=0,
                    t_end=target.duration_sec,
                    still_id=target.still_id,
                )
            ]
    repair_scene_shots(target)
    new_auto_prompt = build_scene_prompt(target, bible)
    if body.image_prompt is not None and body.image_prompt.strip():
        submitted_prompt = body.image_prompt.strip()
        if submitted_prompt != old_prompt or (old_prompt and old_prompt != old_auto_prompt):
            target.image_prompt = submitted_prompt
        else:
            target.image_prompt = new_auto_prompt
    else:
        target.image_prompt = new_auto_prompt

    # Sync structure if 5-scene editorial
    struct_json = row.get("structure_json")
    if len(board.scenes) == 5 and struct_json:
        try:
            struct = StoryStructure.model_validate_json(struct_json)
            beat_keys = ("hook", "conflict", "rising_action", "twist", "ending")
            idx = target.index - 1
            if 0 <= idx < 5:
                struct = struct.model_copy(update={beat_keys[idx]: target.dialogue_or_vo})
                db.dump_json(job_dir(job_id) / "structure.json", struct.model_dump(mode="json"))
                struct_json = struct.model_dump_json()
        except Exception:
            pass

    db.dump_json(job_dir(job_id) / "storyboard.json", board.model_dump(mode="json"))
    db.update_job(job_id, storyboard_json=board.model_dump_json(), structure_json=struct_json)
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    return pub


class RegenerateStillBody(BaseModel):
    prompt: str | None = None
    source: str = "auto"


@app.post("/jobs/{job_id}/scenes/{scene_index}/regenerate-still")
async def regenerate_scene_still_endpoint(
    job_id: str,
    scene_index: int,
    user: CurrentUser,
    body: RegenerateStillBody | None = None,
) -> dict:
    row = require_job(job_id, user)
    _require_idle_job(row)
    try:
        res = await regenerate_scene_still(
            job_id,
            scene_index,
            custom_prompt=body.prompt if body else None,
            source=body.source if body else "auto",
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    pub["still_provider"] = res.get("provider")
    return pub


class FillStillsBody(BaseModel):
    source: str = "auto"
    force_all: bool = False


@app.post("/jobs/{job_id}/fill-stills")
async def fill_missing_stills_endpoint(
    job_id: str,
    user: CurrentUser,
    body: FillStillsBody | None = None,
) -> dict:
    row = require_job(job_id, user)
    _require_idle_job(row)
    try:
        res = await fill_missing_stills(
            job_id,
            source=body.source if body else "auto",
            force_all=bool(body.force_all) if body else False,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    pub["updated_scenes"] = res.get("updated_scenes", [])
    pub["still_source"] = res.get("source", "auto")
    return pub


@app.post("/jobs/{job_id}/pause")
def pause_job_endpoint(job_id: str, user: CurrentUser) -> dict:
    from omaishort.engine.fallback import fallback_analyze, fallback_plan
    from omaishort.engine.image_prompts import fill_image_prompts
    from omaishort.paths import job_dir

    row = require_job(job_id, user)
    story = StoryInput.model_validate_json(row["input_json"])
    bible_json = row.get("bible_json")
    struct_json = row.get("structure_json")
    board_json = row.get("storyboard_json")

    if not bible_json or not struct_json:
        fb_bible, fb_struct = fallback_analyze(story)
        if not bible_json:
            bible_json = fb_bible.model_dump_json()
            db.dump_json(job_dir(job_id) / "bible.json", fb_bible.model_dump(mode="json"))
        if not struct_json:
            struct_json = fb_struct.model_dump_json()
            db.dump_json(job_dir(job_id) / "structure.json", fb_struct.model_dump(mode="json"))

    if not board_json:
        bible = CharacterBible.model_validate_json(bible_json)
        structure = StoryStructure.model_validate_json(struct_json)
        board = fallback_plan(story, bible, structure)
        fill_image_prompts(board, bible)
        board_json = board.model_dump_json()
        db.dump_json(job_dir(job_id) / "storyboard.json", board.model_dump(mode="json"))

    db.update_job(
        job_id,
        status="paused",
        progress="paused:editing",
        bible_json=bible_json,
        structure_json=struct_json,
        storyboard_json=board_json,
    )
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    return pub


class RerenderBody(BaseModel):
    regenerate_stills: bool = False


@app.post("/jobs/{job_id}/resume")
async def resume_job_endpoint(
    job_id: str,
    background: BackgroundTasks,
    user: CurrentUser,
    body: RerenderBody | None = None,
) -> dict:
    row = require_job(job_id, user)
    _require_idle_job(row)
    regen = bool(body.regenerate_stills) if body else False
    db.update_job(job_id, status="running", progress="resume:queued", error=None)
    background.add_task(rerender_job, job_id, regenerate_stills=regen)
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    return pub


@app.post("/jobs/{job_id}/scenes/{scene_index}/upload-still")
async def upload_scene_still_endpoint(
    job_id: str,
    scene_index: int,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> dict:
    import json as _json
    from omaishort.engine.brief_media import conform_photo
    from omaishort.paths import stills_dir

    row = require_job(job_id, user)
    _require_idle_job(row)
    if not row.get("storyboard_json"):
        raise HTTPException(409, "Storyboard chưa sẵn sàng")
    board = Storyboard.model_validate_json(row["storyboard_json"])
    target = next((s for s in board.scenes if s.index == scene_index), None)
    if target is None and 1 <= scene_index <= len(board.scenes):
        target = board.scenes[scene_index - 1]
    if target is None:
        raise HTTPException(404, f"Không tìm thấy cảnh {scene_index}")

    raw = await file.read(uploads.MAX_IMAGE + 1)
    if len(raw) < 64:
        raise HTTPException(400, "File ảnh không hợp lệ")
    if len(raw) > uploads.MAX_IMAGE:
        raise HTTPException(413, "File ảnh vượt quá giới hạn 8MB")
    uploads.sniff_bytes(raw, AttachmentKind.editorial, file.filename or "still.png")
    uploads._verify_image(raw)

    safe_id = Path(target.still_id).name
    sdir = stills_dir(job_id)
    sdir.mkdir(parents=True, exist_ok=True)
    tmp = sdir / f"{safe_id}.upload"
    dest = sdir / f"{safe_id}.png"
    tmp.write_bytes(raw)
    try:
        conform_photo(tmp, dest)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise HTTPException(400, f"Không đọc được file ảnh: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)

    artifacts = db.artifacts_of(row)
    artifacts[target.still_id] = dest.as_posix()
    db.update_job(job_id, artifacts_json=_json.dumps(artifacts))
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    return pub


@app.post("/jobs/{job_id}/rerender")
async def rerender_job_endpoint(
    job_id: str,
    background: BackgroundTasks,
    user: CurrentUser,
    body: RerenderBody | None = None,
) -> dict:
    row = require_job(job_id, user)
    _require_idle_job(row)
    regen = bool(body.regenerate_stills) if body else False
    db.update_job(job_id, status="running", stage="tts", progress="rerender:queued", error=None)
    background.add_task(rerender_job, job_id, regenerate_stills=regen)
    fresh = db.get_job(job_id) or row
    pub = db.public_job(fresh)
    pub["storage"] = storage.inspect_job_storage(job_id, fresh)
    return pub


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
