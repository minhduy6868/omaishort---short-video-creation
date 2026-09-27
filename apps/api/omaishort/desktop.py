"""Local desktop window: studio and API on one origin."""

from __future__ import annotations

import shutil
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

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_DIST = REPO_ROOT / "apps" / "web" / "dist"


_UI_PAGES = ("/login", "/register", "/work", "/drama", "/news", "/knowledge", "/account")


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


def run() -> None:
    import uvicorn

    from omaishort.config import API_HOST, API_PORT
    from omaishort.main import app

    attach_studio(app, WEB_DIST)
    host = API_HOST or "127.0.0.1"
    url = f"http://{host}:{API_PORT}/"

    def _open_when_ready() -> None:
        _wait_until_up(f"http://{host}:{API_PORT}/health")
        open_studio_window(url)
        print(f"omaishort desktop  {url}")

    threading.Thread(target=_open_when_ready, name="omaishort-window", daemon=True).start()
    uvicorn.run(app, host=host, port=API_PORT, log_level="info")


if __name__ == "__main__":
    run()
