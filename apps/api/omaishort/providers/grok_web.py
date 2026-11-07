"""Grok Imagine hub for omaishort (Playwright persistent profile).

Same exception class as ChatGPT-web: login-once Chrome under DATA_DIR.
Later I2V uses in-page fetch on grok.com/imagine — not Electron Browser Hub,
not DOM clicks on the Imagine UI.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path

from omaishort.config import DATA_DIR, GROK_WEB_ENABLED, GROK_WEB_HEADED, HUB_HEADLESS
from omaishort.providers.chrome_profile import (
    bring_chrome_windows_to_front,
    hub_launch_args,
    kill_stale_profile_chrome,
    playwright_ok,
    system_chrome_exe,
)

IMAGINE = "https://grok.com/imagine"
_AUTH_COOKIES = {"sso", "sso-rw"}
_HIDE_WEBDRIVER = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
session_lock = asyncio.Lock()


async def prepare(ctx) -> None:
    await ctx.add_init_script(_HIDE_WEBDRIVER)


def chrome_launch_error(exc: BaseException) -> str:
    text = str(exc)
    lowered = text.lower()
    if "in use" in lowered or "singleton" in lowered or "existing browser session" in lowered:
        return "Cửa sổ Chrome đăng nhập Grok đang mở. Đăng nhập trên cửa sổ đó, hoặc đóng rồi bấm lại."
    return "Không mở được Chrome. Đóng hết cửa sổ Chrome rồi bấm Đăng nhập Grok lại."


def profile_dir() -> Path:
    return DATA_DIR / "grok-web" / "profile"


def session_path() -> Path:
    return DATA_DIR / "grok-web" / "session.json"


def grok_domain(domain: str | None) -> bool:
    host = (domain or "").lstrip(".").lower()
    return host == "grok.com" or host.endswith(".grok.com") or host in {"x.ai", "assets.grok.com"} or host.endswith(".x.ai")


def _cookie_db_ok() -> bool:
    root = profile_dir()
    for rel in ("Default/Network/Cookies", "Default/Cookies"):
        cookie = root / rel
        if cookie.is_file() and cookie.stat().st_size > 100:
            return True
    return False


def is_authed() -> bool:
    """True only when login marker and Chromium cookie DB both exist (ChatGPT-web pattern)."""
    if not GROK_WEB_ENABLED:
        return False
    marker = session_path()
    if not marker.is_file():
        return False
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return False
    if not (isinstance(data, dict) and bool(data.get("authed"))):
        return False
    return _cookie_db_ok()


def save_authed() -> None:
    session_path().parent.mkdir(parents=True, exist_ok=True)
    session_path().write_text(json.dumps({"authed": True}, indent=2), encoding="utf-8")


def clear_authed() -> None:
    """Drop the hub marker so later scenes skip Playwright after SSO expiry."""
    try:
        session_path().unlink(missing_ok=True)
    except OSError:
        pass


def launch_args(*, headed: bool) -> dict:
    return hub_launch_args(profile_dir(), visible=headed or GROK_WEB_HEADED, headless=HUB_HEADLESS)


def cookies_have_sso(cookies: list[dict]) -> bool:
    names = {str(item.get("name") or "") for item in cookies if grok_domain(str(item.get("domain") or ""))}
    return bool(names & _AUTH_COOKIES)


async def has_session(ctx) -> bool:
    try:
        cookies = await ctx.cookies()
    except Exception:
        return False
    return cookies_have_sso(cookies)


async def _click_first(page, names: list[str]) -> bool:
    for name in names:
        loc = page.get_by_role("button", name=re.compile(name, re.I))
        if await loc.count():
            await loc.first.click()
            return True
        link = page.get_by_role("link", name=re.compile(name, re.I))
        if await link.count():
            await link.first.click()
            return True
    return False


async def _try_fill_login(page) -> None:
    """Optional env GROK_WEB_EMAIL / GROK_WEB_PASSWORD. Never print the secret."""
    email = os.environ.get("GROK_WEB_EMAIL", "").strip()
    password = os.environ.get("GROK_WEB_PASSWORD", "").strip()
    if not email or not password:
        return
    await _click_first(page, [r"sign in", r"log in", r"đăng nhập"])
    await page.wait_for_timeout(800)
    await _click_first(page, [r"email", r"sign in with email", r"continue with email"])
    await page.wait_for_timeout(600)
    email_box = page.locator(
        'input[type="email"], input[name="email"], input[name="username"], '
        'input[autocomplete="username"], input[autocomplete="email"]'
    ).first
    try:
        await email_box.wait_for(state="visible", timeout=12_000)
        await email_box.fill(email)
        await _click_first(page, [r"^next$", r"continue", r"sign in", r"log in"])
        await page.wait_for_timeout(800)
    except Exception:
        return
    pwd = page.locator('input[type="password"], input[name="password"], input[autocomplete="current-password"]').first
    try:
        await pwd.wait_for(state="visible", timeout=12_000)
        await pwd.fill(password)
        if not await _click_first(page, [r"sign in", r"log in", r"continue", r"^next$"]):
            await pwd.press("Enter")
    except Exception:
        return


async def login(on_open=None) -> bool:
    """Open a visible Chrome window until Grok SSO cookies exist."""
    def _opened(exc: BaseException | None) -> None:
        if on_open is not None:
            on_open(exc)

    if not playwright_ok():
        print("Install: pip install playwright && python -m playwright install chromium")
        _opened(RuntimeError("Playwright Chromium is not installed"))
        return False
    from playwright.async_api import async_playwright

    profile_dir().mkdir(parents=True, exist_ok=True)
    kill_stale_profile_chrome(profile_dir())
    async with async_playwright() as pw:
        launch = {**launch_args(headed=True), "headless": False}
        if launch.get("channel") == "chrome":
            print(f"Using installed Chrome at {system_chrome_exe()}", flush=True)
        print("Grok hub: Chrome will open grok.com/imagine. Session saves when SSO cookies appear.", flush=True)
        try:
            ctx = await pw.chromium.launch_persistent_context(**launch)
        except Exception as exc:
            print(f"Grok login could not open Chrome: {exc}", flush=True)
            _opened(exc)
            return False
        await prepare(ctx)
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            try:
                await page.bring_to_front()
            except Exception:
                pass
            bring_chrome_windows_to_front()
            _opened(None)
            await page.goto(IMAGINE, wait_until="domcontentloaded")
            bring_chrome_windows_to_front()
            await page.wait_for_timeout(2000)
            bring_chrome_windows_to_front()
            was_already_authed = await has_session(ctx)
            saw_logged_out = not was_already_authed
            if not was_already_authed:
                clear_authed()
                await _try_fill_login(page)
            else:
                save_authed()
            deadline = time.monotonic() + 30 * 60
            while time.monotonic() < deadline:
                open_pages = [p for p in ctx.pages if not p.is_closed()]
                if not open_pages:
                    if await has_session(ctx):
                        save_authed()
                    saved = is_authed()
                    print("Grok login window was closed." + (" Session was saved." if saved else ""), flush=True)
                    return saved
                has_sso = await has_session(ctx)
                if not has_sso:
                    saw_logged_out = True
                else:
                    save_authed()
                    if saw_logged_out:
                        on_grok = [p for p in open_pages if "grok.com" in (p.url or "")]
                        target = on_grok[0] if on_grok else open_pages[0]
                        await target.wait_for_timeout(1500)
                        print(f"Grok hub session saved at {profile_dir()}", flush=True)
                        return True
                await asyncio.sleep(2)
            print("Grok login timed out.", flush=True)
            return False
        finally:
            try:
                await ctx.close()
            except Exception:
                pass


async def open_imagine(page) -> None:
    """grok.com/imagine reloads itself once after domcontentloaded; an in-page fetch during that dies."""
    await page.goto(IMAGINE, wait_until="load")
    await page.wait_for_timeout(2500)
    if not page.url.startswith(IMAGINE):
        await page.goto(IMAGINE, wait_until="load")
        await page.wait_for_timeout(1500)


async def page_fetch(page, url: str, *, method: str = "POST", body: str | None = None, timeout_ms: int = 60_000) -> tuple[int, str]:
    """Same-origin fetch inside grok.com/imagine. Not a DOM click."""
    result = await page.evaluate(
        """async ({url, method, body, timeoutMs}) => {
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), timeoutMs);
            try {
                const headers = {Accept: '*/*', 'Accept-Language': 'en-US,en;q=0.9'};
                if (body && method !== 'GET') headers['Content-Type'] = 'application/json';
                const res = await fetch(url, {
                    method,
                    headers,
                    body: body && method !== 'GET' ? body : undefined,
                    credentials: 'include',
                    signal: ctrl.signal,
                });
                return {status: res.status, text: await res.text()};
            } catch (err) {
                return {status: 0, text: String(err && err.message ? err.message : err)};
            } finally {
                clearTimeout(timer);
            }
        }""",
        {"url": url, "method": method, "body": body, "timeoutMs": timeout_ms},
    )
    if not isinstance(result, dict):
        return 0, ""
    return int(result.get("status") or 0), str(result.get("text") or "")


async def page_upload(page, data: bytes, filename: str, mime: str, timeout_ms: int = 90_000) -> tuple[int, str]:
    import base64

    result = await page.evaluate(
        """async ({b64, filename, mime, timeoutMs}) => {
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), timeoutMs);
            try {
                const binary = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
                const form = new FormData();
                form.append('file', new Blob([binary], {type: mime}), filename);
                form.append('file_source', 'IMAGINE_SELF_UPLOAD_FILE_SOURCE');
                const res = await fetch('https://grok.com/http/upload-file-v2/direct', {
                    method: 'POST',
                    body: form,
                    credentials: 'include',
                    signal: ctrl.signal,
                });
                return {status: res.status, text: await res.text()};
            } catch (err) {
                return {status: 0, text: String(err && err.message ? err.message : err)};
            } finally {
                clearTimeout(timer);
            }
        }""",
        {
            "b64": base64.b64encode(data).decode(),
            "filename": filename,
            "mime": mime,
            "timeoutMs": timeout_ms,
        },
    )
    if not isinstance(result, dict):
        return 0, ""
    return int(result.get("status") or 0), str(result.get("text") or "")
