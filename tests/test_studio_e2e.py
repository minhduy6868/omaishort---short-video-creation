"""System test: real browser against the built studio served the way the desktop serves it.

Skips when apps/web/dist is missing (run `npm run build` in apps/web) or no Chromium/Chrome
is available to Playwright. No provider is called; the database is a temp SQLite file.
"""

from __future__ import annotations

import os
import socket
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "apps" / "web" / "dist"

pytestmark = pytest.mark.skipif(not (DIST / "index.html").is_file(), reason="studio build missing: npm run build in apps/web")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture(scope="module")
def studio_url(tmp_path_factory):
    import uvicorn
    from fastapi import FastAPI

    tmp = tmp_path_factory.mktemp("e2e")
    mp = pytest.MonkeyPatch()
    mp.setenv("AUTH_SECRET", "e2e-secret-e2e-secret-e2e-secret")
    mp.setenv("DATA_DIR", str(tmp))
    mp.setenv("DATABASE_URL", f"sqlite:///{(tmp / 'omaishort.db').as_posix()}")
    import omaishort.config as cfg

    mp.setattr(cfg, "DATA_DIR", tmp)
    mp.setattr(cfg, "DATABASE_URL", os.environ["DATABASE_URL"])
    from omaishort import db
    from omaishort.desktop import attach_studio
    from omaishort.main import app as api

    db.init_db()
    app = FastAPI()
    app.router.routes.extend(api.router.routes)
    attach_studio(app, DIST)

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        pytest.fail("studio server did not start")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)
    mp.undo()


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    pw = sync_api.sync_playwright().start()
    launched = None
    for kwargs in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            launched = pw.chromium.launch(headless=True, **kwargs)
            break
        except Exception:
            continue
    if launched is None:
        pw.stop()
        pytest.skip("no Chromium/Chrome/Edge for Playwright")
    yield launched
    launched.close()
    pw.stop()


def _theme(page) -> str:
    page.wait_for_function("() => document.documentElement.dataset.theme")
    return page.evaluate("() => document.documentElement.dataset.theme")


def _register(page, base: str, email: str) -> dict:
    res = page.request.post(f"{base}/auth/register", data={"email": email, "password": "password1"})
    assert res.status == 201, res.text()
    return res.json()


def test_root_lands_on_vi_and_studio_needs_login(studio_url, browser):
    page = browser.new_page()
    page.goto(f"{studio_url}/")
    page.wait_for_url("**/vi")
    page.locator("h1").first.wait_for()
    assert page.locator("h1").first.is_visible()
    assert _theme(page) == "brutal"

    page.goto(f"{studio_url}/work")
    page.wait_for_url("**/login")
    page.get_by_role("heading", name="Đăng nhập").wait_for()
    assert page.get_by_role("heading", name="Đăng nhập").is_visible()
    page.close()


def test_operator_theme_reaches_every_visitor(studio_url, browser):
    admin = browser.new_context()
    admin_page = admin.new_page()
    admin_page.goto(f"{studio_url}/vi")
    body = _register(admin_page, studio_url, "admin@example.com")
    assert body["user"]["role"] == "operator"

    saved = admin_page.request.put(f"{studio_url}/site/theme", data={"theme": "soft"})
    assert saved.status == 200, saved.text()

    visitor = browser.new_context()
    page = visitor.new_page()
    page.goto(f"{studio_url}/vi")
    page.wait_for_function("() => document.documentElement.dataset.theme === 'soft'")

    page.goto(f"{studio_url}/vi?theme=brutal")
    assert _theme(page) == "brutal"
    page.goto(f"{studio_url}/vi")
    page.wait_for_function("() => document.documentElement.dataset.theme === 'soft'")

    admin_page.request.put(f"{studio_url}/site/theme", data={"theme": "brutal"})
    admin.close()
    visitor.close()


def test_only_the_operator_can_click_the_site_theme(studio_url, browser):
    context = browser.new_context()
    page = context.new_page()
    page.goto(f"{studio_url}/vi")
    browser.new_page().request.post(
        f"{studio_url}/auth/register", data={"email": "owner@example.com", "password": "password1"}
    )
    assert _register(page, studio_url, "creator@example.com")["user"]["role"] == "creator"

    page.goto(f"{studio_url}/account")
    picker = page.get_by_role("radiogroup", name="Giao diện toàn site")
    picker.wait_for()
    radios = picker.get_by_role("radio")
    assert radios.count() == 2
    for index in range(2):
        assert radios.nth(index).is_disabled()
    assert page.get_by_text("Admin (operator) chọn giao diện cho toàn site.").is_visible()
    assert page.get_by_role("button", name="Kiểm tra ChatGPT thật").is_visible()
    context.close()


def test_policy_pages_and_seo_endpoints(studio_url, browser):
    page = browser.new_page()
    robots = page.request.get(f"{studio_url}/robots.txt")
    assert robots.status == 200
    assert "Sitemap:" in robots.text()

    sitemap = page.request.get(f"{studio_url}/sitemap.xml")
    assert sitemap.status == 200
    assert "/vi/privacy" in sitemap.text()

    page.goto(f"{studio_url}/vi/privacy")
    h1 = page.get_by_role("heading", name="Chính sách Bảo mật")
    h1.wait_for()
    assert h1.is_visible()

    page.goto(f"{studio_url}/vi/terms")
    terms_h1 = page.get_by_role("heading", name="Điều khoản Dịch vụ")
    terms_h1.wait_for()
    assert terms_h1.is_visible()
    page.close()


def test_operator_can_open_admin_console_and_tabs(studio_url, browser):
    admin = browser.new_context()
    page = admin.new_page()
    page.goto(f"{studio_url}/vi")
    res = page.request.post(
        f"{studio_url}/auth/login",
        data={"email": "admin@example.com", "password": "password1"},
    )
    if res.status != 200:
        res = page.request.post(
            f"{studio_url}/auth/login",
            data={"email": "owner@example.com", "password": "password1"},
        )
    assert res.status == 200, res.text()

    page.goto(f"{studio_url}/admin")
    heading = page.get_by_role("heading", name="Quản trị Hệ thống")
    heading.wait_for()
    assert heading.is_visible()
    tablist = page.get_by_role("tablist", name="Phân hệ quản trị")
    assert tablist.is_visible()

    tablist.get_by_role("tab", name="Người dùng").click()
    users_h = page.get_by_role("heading", name="Quản lý Người dùng", exact=False)
    users_h.wait_for()
    assert users_h.is_visible()

    tablist.get_by_role("tab", name="Lưu trữ Video Local").click()
    storage_h = page.get_by_role("heading", name="Quản lý Lưu trữ Video Local", exact=False)
    storage_h.wait_for()
    assert storage_h.is_visible()
    admin.close()
