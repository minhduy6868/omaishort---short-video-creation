"""Local desktop window: studio and API on one origin."""

from __future__ import annotations

import os
import secrets
import shutil
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bootstrap import ensure_sys_path

ensure_sys_path()

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.requests import Request
from fastapi.staticfiles import StaticFiles
from starlette.routing import Route

_RAW_ROOT = os.environ.get("OMAISHORT_ROOT", "").strip()
REPO_ROOT = Path(_RAW_ROOT).resolve() if _RAW_ROOT else Path(__file__).resolve().parents[3]
_RAW_DIST = os.environ.get("OMAISHORT_WEB_DIST", "").strip()
WEB_DIST = Path(_RAW_DIST).resolve() if _RAW_DIST else (REPO_ROOT / "apps" / "web" / "dist")


_UI_PAGES = (
    "/login",
    "/register",
    "/work",
    "/drama",
    "/news",
    "/knowledge",
    "/account",
    "/admin",
    "/privacy",
    "/policy",
    "/terms",
    "/cookies",
    "/en",
    "/vi",
    "/ja",
    "/en/studio",
    "/vi/studio",
    "/ja/studio",
    "/en/privacy",
    "/vi/privacy",
    "/ja/privacy",
    "/en/terms",
    "/vi/terms",
    "/ja/terms",
    "/en/cookies",
    "/vi/cookies",
    "/ja/cookies",
)


def attach_studio(application: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    assets = dist / "assets"
    if not index.is_file():
        raise FileNotFoundError(f"Studio build missing: {index}. Run npm run build in apps/web.")
    if assets.is_dir():
        application.mount("/assets", StaticFiles(directory=assets), name="studio-assets")

    async def studio_index(_request: Request) -> FileResponse:
        return FileResponse(index)

    application.router.routes.insert(0, Route("/", studio_index, methods=["GET"]))
    for path in _UI_PAGES:
        application.router.routes.insert(0, Route(path, studio_index, methods=["GET"]))
    application.router.routes.insert(0, Route("/watch/{job_id}", studio_index, methods=["GET"]))


def find_app_browser() -> list[str] | None:
    names = ("msedge", "chrome", "chromium", "brave")
    windows = (
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    )
    for path in windows:
        if path.is_file():
            return [str(path)]
    for name in names:
        found = shutil.which(name)
        if found:
            return [found]
    return None


def open_studio_window(url: str) -> None:
    import subprocess

    browser = find_app_browser()
    if browser:
        subprocess.Popen([*browser, f"--app={url}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    import webbrowser

    webbrowser.open(url)


def _wait_until_up(url: str, timeout_sec: float = 45) -> None:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as res:
                if res.status < 500:
                    return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError(f"Studio did not start: {url}")


def ensure_portable_env(env_path: Path, data_dir: Path) -> Path:
    """Create a local-first .env on first launch of a portable desktop bundle (no secrets shipped)."""
    data_dir.mkdir(parents=True, exist_ok=True)
    if env_path.is_file():
        return env_path
    env_path.parent.mkdir(parents=True, exist_ok=True)
    db_file = (data_dir / "omaishort.db").resolve().as_posix()
    lines = [
        "# Auto-generated on first launch by omaishort portable desktop.",
        f"AUTH_SECRET={secrets.token_urlsafe(32)}",
        f"DATABASE_URL=sqlite:///{db_file}",
        f"DATA_DIR={data_dir.resolve().as_posix()}",
        "POLLINATIONS_ENABLED=1",
        "CHATGPT_WEB_ENABLED=1",
        "MUSE_WEB_ENABLED=1",
        "MUSE_WEB_VIDEO_ENABLED=1",
        "GROK_WEB_ENABLED=1",
        "GROK_WEB_VIDEO_ENABLED=1",
        "# Optional API keys (add your own keys here if needed):",
        "# OPENAI_API_KEY=",
        "# GEMINI_API_KEY=",
        "# XAI_API_KEY=",
        "# HF_TOKEN=",
        "# ELEVENLABS_API_KEY=",
        "# REA_VLM_BASE_URL=",
        "# REA_VLM_API_KEY=",
        "# REA_VLM_MODEL=",
        "",
    ]
    env_path.write_text("\n".join(lines), encoding="utf-8")
    return env_path


def _health_is_omaishort(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1.0) as res:
            return res.status == 200 and b'"ok"' in res.read(256)
    except OSError:
        return False


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def pick_desktop_port(host: str, preferred: int) -> tuple[int, bool]:
    """Return (port, already_running). Reuses running omaishort; avoids collision with other apps."""
    if _health_is_omaishort(host, preferred):
        return preferred, True
    if _port_is_free(host, preferred):
        return preferred, False
    for candidate in range(preferred + 1, preferred + 35):
        if _port_is_free(host, candidate):
            return candidate, False
    return preferred, False


def run() -> None:
    if os.environ.get("OMAISHORT_PORTABLE", "").strip().lower() in {"1", "true", "yes", "on"}:
        env_target = Path(os.environ.get("OMAISHORT_ENV_FILE") or (REPO_ROOT.parent / ".env"))
        data_target = Path(os.environ.get("DATA_DIR") or (REPO_ROOT.parent / "data"))
        ensure_portable_env(env_target, data_target)
        os.environ.setdefault("OMAISHORT_ENV_FILE", str(env_target))
        os.environ.setdefault("DATA_DIR", str(data_target))

    import uvicorn

    from omaishort.config import API_HOST, API_PORT
    from omaishort.main import app

    host = API_HOST or "127.0.0.1"
    port, already_running = pick_desktop_port(host, API_PORT)
    url = f"http://{host}:{port}/work"
    if already_running:
        open_studio_window(url)
        print(f"omaishort desktop already running  {url}")
        return

    attach_studio(app, WEB_DIST)

    def _open_when_ready() -> None:
        _wait_until_up(f"http://{host}:{port}/health")
        open_studio_window(url)
        print(f"omaishort desktop  {url}")

    threading.Thread(target=_open_when_ready, name="omaishort-window", daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run()
