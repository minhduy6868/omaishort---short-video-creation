"""Muse.ai Browser Hub for omaishort (Playwright persistent profile).

Mirrors videoai Browser Hub / musePlugin contracts:
- headed login window (partition-style profile under DATA_DIR)
- auth via /api/session + challenge URL detection (not cookie names alone)
- Hatch HTTP uses the same Chromium session (context.request / in-page fetch)
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from omaishort.config import DATA_DIR, HUB_HEADLESS, MUSE_WEB_ENABLED, MUSE_WEB_HEADED
from omaishort.providers.chrome_profile import (
    bring_chrome_windows_to_front,
    hub_launch_args,
    kill_stale_profile_chrome,
    playwright_ok,
    system_chrome_exe,
)

MUSE_HOME = "https://muse.ai/"
MUSE_ORIGIN = "https://muse.ai"
_AUTH_COOKIES = {"hatch_sess", "hatch_native_auth_device"}
_REQUIRED_AUTH = "hatch_sess"
_CHALLENGE_RE = re.compile(
    r"captcha|challenge|verify|checkpoint|turnstile|arkose|recaptcha|security|auth\.meta\.com",
    re.I,
)
_LOGIN_RE = re.compile(r"muse\.ai/(?:login|sign.?in)", re.I)
_HIDE_WEBDRIVER = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
session_lock = asyncio.Lock()


async def prepare(ctx) -> None:
    await ctx.add_init_script(_HIDE_WEBDRIVER)


def chrome_launch_error(exc: BaseException) -> str:
    text = str(exc)
    lowered = text.lower()
    if "in use" in lowered or "singleton" in lowered or "existing browser session" in lowered:
        return "Cửa sổ Chrome hub Muse đang mở. Đăng nhập / vượt checkpoint trên cửa sổ đó, hoặc đóng rồi bấm lại."
    return "Không mở được Chrome. Đóng hết cửa sổ Chrome rồi bấm Đăng nhập Muse lại."


def profile_dir() -> Path:
    return DATA_DIR / "muse-web" / "profile"


def session_path() -> Path:
    return DATA_DIR / "muse-web" / "session.json"


def device_path() -> Path:
    return DATA_DIR / "muse-web" / "device.json"


def muse_domain(domain: str | None) -> bool:
    host = (domain or "").lstrip(".").lower()
    return host == "muse.ai" or host.endswith(".muse.ai") or host.endswith(".metaaivm.com")


def _cookie_db_ok() -> bool:
    root = profile_dir()
    for rel in ("Default/Network/Cookies", "Default/Cookies"):
        cookie = root / rel
        if cookie.is_file() and cookie.stat().st_size > 100:
            return True
    return False


def _read_marker() -> dict[str, Any]:
    path = session_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def is_authed() -> bool:
    """Hub ready for Muse video — logged in and not stuck on Meta checkpoint."""
    if not MUSE_WEB_ENABLED:
        return False
    data = _read_marker()
    if not bool(data.get("authed")):
        return False
    if bool(data.get("challenge")):
        return False
    return _cookie_db_ok()


def is_challenge() -> bool:
    if not MUSE_WEB_ENABLED:
        return False
    return bool(_read_marker().get("challenge"))


def checkpoint_url() -> str:
    value = _read_marker().get("checkpoint_url")
    return value.strip() if isinstance(value, str) else ""


def save_marker(*, authed: bool, challenge: bool = False, checkpoint: str | None = None) -> None:
    session_path().parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"authed": bool(authed), "challenge": bool(challenge)}
    if checkpoint:
        payload["checkpoint_url"] = checkpoint
    session_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def save_authed() -> None:
    save_marker(authed=True, challenge=False)


def save_challenge(url: str | None = None) -> None:
    save_marker(authed=False, challenge=True, checkpoint=url)


def clear_authed() -> None:
    try:
        session_path().unlink(missing_ok=True)
    except OSError:
        pass


def launch_args(*, headed: bool) -> dict:
    return hub_launch_args(profile_dir(), visible=headed or MUSE_WEB_HEADED, headless=HUB_HEADLESS)


def cookies_have_auth(cookies: list[dict]) -> bool:
    names = {str(item.get("name") or "") for item in cookies if muse_domain(str(item.get("domain") or ""))}
    return _REQUIRED_AUTH in names and bool(names & _AUTH_COOKIES)


def url_is_challenge(url: str) -> bool:
    return bool(_CHALLENGE_RE.search(url or ""))


def url_is_login(url: str) -> bool:
    return bool(_LOGIN_RE.search(url or ""))


async def has_session(ctx) -> bool:
    try:
        cookies = await ctx.cookies()
    except Exception:
        return False
    return cookies_have_auth(cookies)


def device_id() -> str:
    path = device_path()
    if path.is_file():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(saved, dict) and isinstance(saved.get("device_id"), str) and saved["device_id"]:
                return saved["device_id"]
        except Exception:
            pass
    import uuid

    value = str(uuid.uuid4())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"device_id": value}, indent=2), encoding="utf-8")
    return value


async def page_fetch(
    page,
    url: str,
    *,
    method: str = "GET",
    body: str | None = None,
    headers: dict[str, str] | None = None,
    timeout_ms: int = 60_000,
) -> tuple[int, str]:
    """Same-origin credentials:include fetch inside the Muse hub page (Electron session.fetch analog)."""
    payload = {
        "url": url,
        "method": method,
        "body": body,
        "headers": headers or {},
        "timeoutMs": timeout_ms,
    }
    script = """async ({url, method, body, headers, timeoutMs}) => {
            const ctrl = new AbortController();
            const timer = setTimeout(() => ctrl.abort(), timeoutMs);
            try {
                const reqHeaders = Object.assign(
                    {Accept: 'application/json,text/html,*/*;q=0.8', 'Accept-Language': 'en-US,en;q=0.9'},
                    headers || {}
                );
                if (body && method !== 'GET' && !reqHeaders['Content-Type']) {
                    reqHeaders['Content-Type'] = 'application/json';
                }
                const res = await fetch(url, {
                    method,
                    headers: reqHeaders,
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
        }"""
    last_err = ""
    for _ in range(4):
        try:
            result = await page.evaluate(script, payload)
            if not isinstance(result, dict):
                return 0, ""
            return int(result.get("status") or 0), str(result.get("text") or "")
        except Exception as exc:
            last_err = str(exc)
            # Meta OIDC / checkpoint navigates the hub mid-probe.
            if "Execution context was destroyed" in last_err or "navigation" in last_err.lower():
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=15_000)
                except Exception:
                    await asyncio.sleep(1.5)
                continue
            return 0, last_err
    return 0, last_err or "page_fetch failed"


async def open_hub(page) -> None:
    await page.goto(MUSE_HOME, wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)


def _parse_json(text: str) -> Any:
    if not text or not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def bootstrap_has_gateway(html: str) -> bool:
    """True when Muse RSC/bootstrap embeds a real gatewayUrl string (not null)."""
    if not html:
        return False
    if re.search(r'"gatewayUrl"\s*:\s*null', html):
        # Still allow a later non-null occurrence.
        pass
    return bool(re.search(r'"gatewayUrl"\s*:\s*"https?://[^"]+"', html))


async def detect_auth(ctx, page) -> dict[str, Any]:
    """videoai musePlugin-shaped probe: Logged In | Challenge | Logged Out | Unknown."""
    url = page.url or ""
    if url_is_challenge(url):
        return {"authStatus": "Challenge", "checkpoint_url": url, "url": url}
    if url_is_login(url):
        return {"authStatus": "Logged Out", "url": url}

    cookies_ok = await has_session(ctx)
    status, session_text = await page_fetch(page, f"{MUSE_ORIGIN}/api/session")
    if status in (401, 403):
        return {"authStatus": "Logged Out", "url": url, "session_status": status}
    if status == 0:
        return {"authStatus": "Unknown", "url": url, "session_error": session_text[:200]}

    boot_status, boot_text = await page_fetch(page, f"{MUSE_ORIGIN}/api/hatch/bootstrap")
    boot = _parse_json(boot_text) if boot_text else None
    if boot_status == 403 and isinstance(boot, dict) and boot.get("type") == "checkpointRequired":
        checkpoint = str(boot.get("checkpoint_url") or "")
        return {
            "authStatus": "Challenge",
            "checkpoint_url": checkpoint,
            "url": url,
            "detail": str(boot.get("detail") or "Meta security checkpoint required"),
        }

    html_status, html = await page_fetch(
        page,
        MUSE_ORIGIN + "/",
        headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    )
    has_gateway = bootstrap_has_gateway(html) if html_status and html else False

    if not cookies_ok:
        return {"authStatus": "Logged Out", "url": url, "session_status": status}

    if not has_gateway:
        # Cookie present but Hatch VM not ready — keep hub open (same pain videoai sees as missing gatewayUrl).
        return {
            "authStatus": "Challenge" if boot_status == 403 else "Unknown",
            "url": url,
            "session_status": status,
            "bootstrap_status": boot_status,
            "detail": "Muse Hatch gateway not ready yet",
            "session": _parse_json(session_text),
        }

    session = _parse_json(session_text)
    identity: dict[str, str] = {}
    if isinstance(session, dict):
        user = session.get("user") or session.get("account") or {}
        if isinstance(user, dict):
            name = user.get("name") or user.get("displayName") or user.get("display_name")
            email = user.get("email")
            if isinstance(name, str) and name.strip():
                identity["displayName"] = name.strip()
            if isinstance(email, str) and email.strip():
                identity["email"] = email.strip()

    return {
        "authStatus": "Logged In",
        "url": url,
        "session_status": status,
        "identity": identity,
        "session": session,
    }


async def login(on_open=None) -> bool:
    """Open headed Muse hub until Logged In (session + Hatch gateway), like videoai Browser Hub."""

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
        print(
            "Muse hub: Chrome opens muse.ai (Browser Hub style). "
            "Sign in / finish Meta checkpoint until Hatch gateway is ready.",
            flush=True,
        )
        try:
            ctx = await pw.chromium.launch_persistent_context(**launch)
        except Exception as exc:
            print(f"Muse login could not open Chrome: {exc}", flush=True)
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
            await open_hub(page)
            bring_chrome_windows_to_front()
            deadline = time.monotonic() + 30 * 60
            last_note = ""
            while time.monotonic() < deadline:
                try:
                    detected = await detect_auth(ctx, page)
                except Exception as exc:
                    msg = str(exc)
                    if "Execution context was destroyed" in msg or "navigation" in msg.lower():
                        await asyncio.sleep(1.5)
                        continue
                    raise
                status = detected.get("authStatus")
                if status == "Logged In":
                    await page.wait_for_timeout(800)
                    save_authed()
                    await ctx.close()
                    print(f"Muse hub session saved at {profile_dir()}", flush=True)
                    return True
                if status == "Challenge":
                    checkpoint = str(detected.get("checkpoint_url") or "")
                    save_challenge(checkpoint or None)
                    note = detected.get("detail") or "Meta security checkpoint"
                    if note != last_note:
                        print(f"Muse hub Challenge: {note}", flush=True)
                        last_note = str(note)
                    if checkpoint:
                        host = urlparse(checkpoint).hostname or ""
                        current = page.url or ""
                        if "checkpoint" in checkpoint and host and host not in current:
                            try:
                                await page.goto(checkpoint, wait_until="domcontentloaded")
                                bring_chrome_windows_to_front()
                            except Exception as exc:
                                print(f"Muse hub could not open checkpoint: {exc}", flush=True)
                    bring_chrome_windows_to_front()
                await asyncio.sleep(2)
            await ctx.close()
            print("Muse login timed out.", flush=True)
            return False
        except Exception:
            try:
                await ctx.close()
            except Exception:
                pass
            raise


async def load_cookies() -> list[dict] | None:
    """Legacy helper: export Muse cookies from the hub profile."""
    if not playwright_ok() or not is_authed():
        return None
    from playwright.async_api import async_playwright

    try:
        async with async_playwright() as pw:
            kill_stale_profile_chrome(profile_dir())
            launch = launch_args(headed=False)
            ctx = await pw.chromium.launch_persistent_context(**launch)
            try:
                await prepare(ctx)
                if not await has_session(ctx):
                    clear_authed()
                    return None
                cookies = await ctx.cookies()
                return [c for c in cookies if muse_domain(str(c.get("domain") or ""))]
            finally:
                await ctx.close()
    except Exception as exc:
        print(f"muse hub cookies {exc}", flush=True)
        return None
