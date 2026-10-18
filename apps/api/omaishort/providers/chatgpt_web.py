"""ChatGPT web session for omaishort (Playwright).

Mechanism only: persistent Chromium profile under DATA_DIR.
Headed Chrome only for `--chatgpt-login`. Later jobs are headless and
reuse one conversation per calendar day — no temporary/new chat per job.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from datetime import date
from pathlib import Path

from omaishort.config import (
    CHATGPT_WEB_ENABLED,
    CHATGPT_WEB_HEADED,
    CHATGPT_WEB_MODEL,
    CHATGPT_WEB_TIMEOUT_MIN,
    DATA_DIR,
    HUB_HEADLESS,
)
from omaishort.providers.chrome_profile import hub_launch_args, playwright_ok, system_chrome_exe

_CHAT = "https://chatgpt.com"
_COMPOSER = (
    "#prompt-textarea, "
    '[data-testid="prompt-textarea"], '
    'div.ProseMirror[contenteditable="true"], '
    '[contenteditable="true"][data-placeholder], '
    'textarea[name="prompt-textarea"]'
)
_SEND = (
    '[data-testid="send-button"], button[aria-label="Send prompt"], '
    'button[aria-label="Send message"], button[aria-label="Gửi"]'
)
_AUTH_COOKIES = (
    "__Secure-next-auth.session-token",
    "__Secure-next-auth.session-token.0",
    "__Secure-authjs.session-token",
)
_CONV = re.compile(r"https://chatgpt\.com/c/([a-zA-Z0-9-]+)", re.I)
_LOCK = asyncio.Lock()


def profile_dir() -> Path:
    return DATA_DIR / "chatgpt-web" / "profile"


def daily_path() -> Path:
    return DATA_DIR / "chatgpt-web" / "daily.json"


def _cookie_db_has_session(path: Path) -> bool:
    import sqlite3

    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=1)
    except sqlite3.Error:
        return False
    try:
        rows = conn.execute(
            "SELECT 1 FROM cookies WHERE host_key LIKE '%chatgpt.com' AND name IN (?, ?, ?) LIMIT 1",
            _AUTH_COOKIES,
        ).fetchone()
        return rows is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def is_authed() -> bool:
    """True when the Chrome profile holds a ChatGPT session cookie, not merely a cookie file."""
    root = profile_dir()
    for rel in ("Default/Network/Cookies", "Default/Cookies"):
        cookie = root / rel
        if cookie.is_file() and _cookie_db_has_session(cookie):
            return True
    return False


def today_key() -> str:
    return date.today().isoformat()


def conversation_url(raw: str) -> str:
    match = _CONV.search(raw or "")
    if not match:
        return ""
    return f"{_CHAT}/c/{match.group(1)}"


def load_daily_chat() -> dict:
    path = daily_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict) or data.get("date") != today_key():
        return {}
    url = conversation_url(str(data.get("url") or ""))
    return {"date": data["date"], "url": url} if url else {}


def save_daily_chat(url: str) -> None:
    conv = conversation_url(url)
    if not conv:
        return
    daily_path().parent.mkdir(parents=True, exist_ok=True)
    daily_path().write_text(
        json.dumps({"date": today_key(), "url": conv}, indent=2),
        encoding="utf-8",
    )


def chat_open_url(model: str = "", daily: dict | None = None) -> str:
    """Reuse today's /c/ uuid. Never temporary-chat."""
    conv = conversation_url(str((daily or {}).get("url") or ""))
    if conv:
        return conv
    name = (model or CHATGPT_WEB_MODEL or "").strip()
    if name:
        return f"{_CHAT}/?model={name}"
    return f"{_CHAT}/"


_HIDE_WEBDRIVER = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"


def _launch_args(*, headed: bool) -> dict:
    return hub_launch_args(profile_dir(), visible=headed or CHATGPT_WEB_HEADED, headless=HUB_HEADLESS)


def chrome_launch_error(exc: BaseException) -> str:
    text = str(exc)
    lowered = text.lower()
    if "in use" in lowered or "singleton" in lowered or "existing browser session" in lowered:
        return "Cửa sổ Chrome đăng nhập ChatGPT đang mở. Đăng nhập trên cửa sổ đó, hoặc đóng rồi bấm lại."
    return "Không mở được Chrome. Đóng hết cửa sổ Chrome rồi bấm Đăng nhập ChatGPT lại."


async def _prepare(ctx) -> None:
    await ctx.add_init_script(_HIDE_WEBDRIVER)


async def _account_live(page) -> bool:
    """True when /api/auth/session returns a user and an access token.

    /backend-api/me needs the bearer token, so a cookie-only fetch there never sees the account.
    """
    if page.is_closed() or not (page.url or "").startswith(_CHAT):
        return False
    try:
        me = await page.evaluate(
            """async () => {
                try {
                    const r = await fetch('/api/auth/session', {credentials:'include'});
                    if (!r.ok) return null;
                    const j = await r.json();
                    const u = j.user || {};
                    return {id: u.id || '', email: u.email || '', name: u.name || '', token: !!j.accessToken};
                } catch { return null; }
            }"""
        )
    except Exception:
        # Login redirects destroy the JS world mid-evaluate — poll again.
        return False
    if not isinstance(me, dict):
        return False
    return bool(me.get("token") and me.get("id") and (me.get("email") or me.get("name")))


async def _blocked_reason(page) -> str:
    """Name what replaced the composer: a Cloudflare check or the logged-out landing page."""
    try:
        title = (await page.title() or "").lower()
        body = (await page.evaluate("() => (document.body && document.body.innerText || '').slice(0, 600)") or "").lower()
    except Exception:
        return ""
    if "just a moment" in title or "verify you are human" in body or "challenges.cloudflare" in body:
        return "ChatGPT đang bắt xác minh Cloudflare. Bấm Mở ChatGPT ở Tài khoản, qua bước xác minh, rồi chạy lại."
    if await page.locator('[data-testid="login-button"]').count():
        return "Phiên ChatGPT đã hết. Bấm Đăng nhập ChatGPT ở Tài khoản."
    return ""


async def _has_session(ctx, page) -> bool:
    try:
        cookies = await ctx.cookies(_CHAT)
        if any(c.get("name") in _AUTH_COOKIES and len(c.get("value") or "") > 20 for c in cookies):
            return True
        return await _account_live(page)
    except Exception:
        return False


async def open_content() -> bool:
    """Open today's ChatGPT thread and leave the window up so the user can edit it."""
    if not playwright_ok():
        print("Install: pip install playwright && python -m playwright install chromium")
        return False
    from playwright.async_api import async_playwright

    profile_dir().mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        launch = {**_launch_args(headed=True), "headless": False}
        try:
            ctx = await pw.chromium.launch_persistent_context(**launch)
        except Exception as exc:
            print(f"ChatGPT window failed: {exc}", flush=True)
            return False
        await _prepare(ctx)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        print("ChatGPT content window is open. Close it when you finish editing.", flush=True)
        await page.goto(chat_open_url(CHATGPT_WEB_MODEL, load_daily_chat()), wait_until="domcontentloaded")
        deadline = time.monotonic() + 30 * 60
        while time.monotonic() < deadline:
            if page.is_closed() or not ctx.pages:
                break
            save_daily_chat(page.url or "")
            await asyncio.sleep(1)
        try:
            await ctx.close()
        except Exception:
            pass
        return is_authed()


async def login(on_open=None) -> bool:
    """Open a visible Chrome window until chatgpt.com reports a signed-in account."""
    def _opened(exc: BaseException | None) -> None:
        if on_open is not None:
            on_open(exc)

    if not playwright_ok():
        print("Install: pip install playwright && python -m playwright install chromium")
        _opened(RuntimeError("Playwright Chromium is not installed"))
        return False
    from playwright.async_api import async_playwright

    profile_dir().mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        launch = {**_launch_args(headed=True), "headless": False}
        if launch.get("channel") == "chrome":
            print(f"Using installed Chrome at {system_chrome_exe()}")
        try:
            ctx = await pw.chromium.launch_persistent_context(**launch)
        except Exception as exc:
            print(f"ChatGPT login could not open Chrome: {exc}", flush=True)
            _opened(exc)
            return False
        await _prepare(ctx)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        _opened(None)
        print("Log in to ChatGPT in the window. It stays open until the account is saved.", flush=True)
        await page.goto(f"{_CHAT}/auth/login", wait_until="domcontentloaded")
        deadline = time.monotonic() + 30 * 60
        while time.monotonic() < deadline:
            if page.is_closed() or not ctx.pages:
                saved = is_authed()
                print("ChatGPT login window was closed." + (" Session was saved." if saved else ""), flush=True)
                return saved
            if await _has_session(ctx, page):
                await page.wait_for_timeout(1200)
                await ctx.close()
                print(f"Session saved at {profile_dir()}")
                return True
            await asyncio.sleep(2)
        await ctx.close()
        print("Login timed out.")
        return False


async def _wait_composer(page, timeout_ms: int = 45_000):
    loc = page.locator(_COMPOSER).first
    await loc.wait_for(state="visible", timeout=timeout_ms)
    return loc


_READ_REPLY_JS = """async (sentAt) => {
    const m = location.pathname.match(/\\/c\\/([A-Za-z0-9-]+)/);
    if (!m) return {state: 'no-conversation'};
    const s = await fetch('/api/auth/session', {credentials: 'include'});
    if (!s.ok) return {state: 'no-session'};
    const token = (await s.json()).accessToken;
    if (!token) return {state: 'no-session'};
    const r = await fetch('/backend-api/conversation/' + m[1], {
        credentials: 'include',
        headers: {Authorization: 'Bearer ' + token, Accept: 'application/json'},
    });
    if (!r.ok) return {state: 'http-' + r.status};
    const conv = await r.json();
    const node = conv.mapping && conv.mapping[conv.current_node];
    const msg = node && node.message;
    if (!msg || !msg.author || msg.author.role !== 'assistant') return {state: 'waiting'};
    if ((msg.create_time || 0) < sentAt - 5) return {state: 'waiting'};
    const parts = (msg.content && msg.content.parts || []).filter((p) => typeof p === 'string');
    const done = msg.end_turn === true || msg.status === 'finished_successfully';
    return {state: done ? 'done' : 'streaming', text: parts.join('\\n')};
}"""


async def _read_reply(page, sent_at: float, timeout_ms: int) -> str:
    """Poll the conversation JSON for the finished assistant turn. The chat DOM changes too often to scrape."""
    deadline = time.monotonic() + timeout_ms / 1000
    last: dict = {}
    while time.monotonic() < deadline:
        try:
            last = await page.evaluate(_READ_REPLY_JS, sent_at) or {}
        except Exception:
            last = {}
        if last.get("state") == "done" and (last.get("text") or "").strip():
            return str(last["text"]).strip()
        if last.get("state") == "no-session":
            raise RuntimeError("Phiên ChatGPT đã hết. Bấm Đăng nhập ChatGPT ở Tài khoản.")
        await page.wait_for_timeout(1500)
    raise TimeoutError(f"ChatGPT reply did not finish in time ({last.get('state') or 'no reply'})")


async def _composer_text(box) -> str:
    try:
        return (await box.evaluate("e => e.innerText || e.value || ''")) or ""
    except Exception:
        return ""


async def _sent(page, box, timeout_ms: int = 10_000) -> bool:
    """ChatGPT clears the composer once it takes the prompt. That holds across UI redesigns."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        if not (await _composer_text(box)).strip():
            return True
        await page.wait_for_timeout(300)
    return False


async def _fill_and_wait(page, prompt: str, timeout_ms: int) -> str:
    box = await _wait_composer(page)
    await box.click()
    # ChatGPT restores an unsent draft from the last run; clear it so the prompt is not doubled.
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Delete")
    await page.keyboard.insert_text(prompt)
    await page.wait_for_timeout(200)
    if not (await _composer_text(box)).strip():
        await box.fill(prompt)
        await page.wait_for_timeout(200)
    sent_at = float(await page.evaluate("() => Date.now() / 1000"))
    await page.keyboard.press("Enter")
    if not await _sent(page, box):
        send = page.locator(_SEND).first
        if await send.count():
            await send.click()
        if not await _sent(page, box):
            raise RuntimeError("ChatGPT did not accept the prompt (send button never fired)")
    try:
        await page.wait_for_url("**/c/**", timeout=60_000)
    except Exception as exc:
        raise RuntimeError("ChatGPT took the prompt but never opened a conversation") from exc
    return await _read_reply(page, sent_at, timeout_ms)


async def _complete_once(prompt: str, *, headed: bool, timeout_ms: int) -> str:
    from playwright.async_api import async_playwright

    profile_dir().mkdir(parents=True, exist_ok=True)
    daily = load_daily_chat()
    url = chat_open_url(CHATGPT_WEB_MODEL, daily)
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(**_launch_args(headed=headed))
        await _prepare(ctx)
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            if not await _has_session(ctx, page):
                raise RuntimeError("Phiên ChatGPT đã hết. Bấm Đăng nhập ChatGPT ở Tài khoản.")
            try:
                await _wait_composer(page, 20_000)
            except Exception:
                await page.goto(f"{_CHAT}/", wait_until="domcontentloaded")
                try:
                    await _wait_composer(page)
                except Exception as exc:
                    reason = await _blocked_reason(page)
                    raise RuntimeError(reason or f"ChatGPT composer did not appear: {exc}") from exc
            text = await _fill_and_wait(page, prompt, timeout_ms)
            try:
                await page.wait_for_url("**/c/**", timeout=8_000)
            except Exception:
                pass
            save_daily_chat(page.url or "")
            return text
        finally:
            await ctx.close()


async def complete(prompt: str) -> str:
    """Send a prompt on today's thread. Headless after login; no extra Chrome window."""
    if not CHATGPT_WEB_ENABLED:
        raise RuntimeError("ChatGPT web is disabled")
    if not playwright_ok():
        raise RuntimeError("playwright is not installed")
    if not is_authed():
        raise RuntimeError("run: python -m omaishort --chatgpt-login")
    minutes = max(3, min(int(CHATGPT_WEB_TIMEOUT_MIN or 8), 45))
    timeout_ms = minutes * 60 * 1000
    text = prompt.strip()[:12000]
    async with _LOCK:
        return await _complete_once(
            text,
            headed=bool(CHATGPT_WEB_HEADED),
            timeout_ms=timeout_ms,
        )


async def complete_json_prompt(system: str, user: str) -> str:
    blob = (
        "Independent JSON job. Ignore earlier topics in this chat.\n"
        "Return ONLY valid JSON. No markdown.\n\n"
        f"{system.strip()}\n\n{user.strip()}"
    )
    return await complete(blob)


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(login()) else 1)
