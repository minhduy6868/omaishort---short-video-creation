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

from omaishort.config import DATA_DIR, GROK_WEB_ENABLED, GROK_WEB_HEADED
from omaishort.providers.chrome_profile import playwright_ok, system_chrome_exe

IMAGINE = "https://grok.com/imagine"
_AUTH_COOKIES = {"sso", "sso-rw"}
_STEALTH = ["--disable-blink-features=AutomationControlled"]
session_lock = asyncio.Lock()


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
    args = list(_STEALTH)
    if not headed:
        args.append("--start-minimized")
    opts: dict = {
        "user_data_dir": str(profile_dir()),
        "headless": (not headed) and (not GROK_WEB_HEADED),
        "viewport": {"width": 1280, "height": 900},
        "args": args,
    }
    if system_chrome_exe() is not None:
        opts["channel"] = "chrome"
    return opts


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


async def login() -> bool:
    """Open a visible Chrome window until Grok SSO cookies exist."""
    if not playwright_ok():
        print("Install: pip install playwright && python -m playwright install chromium")
        return False
    from playwright.async_api import async_playwright

    profile_dir().mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        launch = {**launch_args(headed=True), "headless": False}
        if launch.get("channel") == "chrome":
            print(f"Using installed Chrome at {system_chrome_exe()}", flush=True)
        print("Grok hub: Chrome will open grok.com/imagine. Session saves when SSO cookies appear.", flush=True)
        ctx = await pw.chromium.launch_persistent_context(**launch)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(IMAGINE, wait_until="domcontentloaded")
        if not await has_session(ctx):
            await _try_fill_login(page)
        deadline = time.monotonic() + 30 * 60
        while time.monotonic() < deadline:
            if await has_session(ctx):
                await page.wait_for_timeout(1200)
                save_authed()
                await ctx.close()
                print(f"Grok hub session saved at {profile_dir()}")
                return True
            await asyncio.sleep(2)
        await ctx.close()
        print("Grok login timed out.")
        return False


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
