"""ChatGPT web session for omaishort (Playwright).

Mechanism only: persistent Chromium profile under DATA_DIR, first login headed,
later replies headless. Not a fork of chatgpt-pro-web.
"""

from __future__ import annotations

import asyncio
import time

from omaishort.config import (
    CHATGPT_WEB_ENABLED,
    CHATGPT_WEB_HEADED,
    CHATGPT_WEB_MODEL,
    CHATGPT_WEB_TIMEOUT_MIN,
    DATA_DIR,
)

_CHAT = "https://chatgpt.com"
_COMPOSER = "#prompt-textarea"
_STOP = '[data-testid="stop-button"], button[aria-label="Stop streaming"], button[aria-label="Stop generating"]'
_TURN = '[data-message-author-role="assistant"]'
_AUTH_COOKIES = (
    "__Secure-next-auth.session-token",
    "__Secure-next-auth.session-token.0",
    "__Secure-authjs.session-token",
)
_STEALTH = ["--disable-blink-features=AutomationControlled"]
_LOCK = asyncio.Lock()


def profile_dir() -> Path:
    return DATA_DIR / "chatgpt-web" / "profile"


def playwright_ok() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def is_authed() -> bool:
    root = profile_dir()
    for rel in ("Default/Network/Cookies", "Default/Cookies"):
        cookie = root / rel
        if cookie.is_file() and cookie.stat().st_size > 100:
            return True
    return False


def _launch_args(*, headed: bool) -> dict:
    args = list(_STEALTH)
    if not headed:
        args.append("--start-minimized")
    return {
        "user_data_dir": str(profile_dir()),
        "headless": (not headed) and (not CHATGPT_WEB_HEADED),
        "viewport": {"width": 1280, "height": 900},
        "args": args,
    }


async def _has_session(ctx, page) -> bool:
    cookies = await ctx.cookies(_CHAT)
    if any(c.get("name") in _AUTH_COOKIES and len(c.get("value") or "") > 20 for c in cookies):
        return True
    me = await page.evaluate(
        """async () => {
            try {
                const r = await fetch('/backend-api/me', {credentials:'include'});
                if (!r.ok) return null;
                const j = await r.json();
                return {id: j.id || '', email: j.email || '', name: j.name || ''};
            } catch { return null; }
        }"""
    )
    if not isinstance(me, dict):
        return False
    ident = str(me.get("id") or "")
    return bool(ident and not ident.startswith("ua-") and (me.get("email") or me.get("name")))


async def login() -> bool:
    """Open a visible Chrome window until ChatGPT session cookies exist."""
    if not playwright_ok():
        print("Install: pip install playwright && python -m playwright install chromium")
        return False
    from playwright.async_api import async_playwright

    profile_dir().mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            **{**_launch_args(headed=True), "headless": False}
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        print("Log in to ChatGPT in the window. It closes when the session is saved.")
        await page.goto(f"{_CHAT}/auth/login", wait_until="domcontentloaded")
        deadline = time.monotonic() + 30 * 60
        while time.monotonic() < deadline:
            if await _has_session(ctx, page):
                await page.wait_for_timeout(1200)
                await ctx.close()
                print(f"Session saved at {profile_dir()}")
                return True
            await asyncio.sleep(2)
        await ctx.close()
        print("Login timed out.")
        return False


async def _fill_and_wait(page, prompt: str, timeout_ms: int) -> str:
    if not await page.query_selector(_COMPOSER):
        await page.wait_for_selector(_COMPOSER, timeout=30_000)
    before = await page.locator(_TURN).count()
    box = page.locator(_COMPOSER)
    await box.click()
    await page.keyboard.insert_text(prompt)
    await page.wait_for_timeout(200)
    await page.keyboard.press("Enter")
    await page.wait_for_function(
        """([sel, n]) => document.querySelectorAll(sel).length > n""",
        arg=[_TURN, before],
        timeout=60_000,
    )
    quiet_since: float | None = None
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        present = await page.query_selector(_STOP)
        if present:
            quiet_since = None
        else:
            now = time.monotonic()
            if quiet_since is None:
                quiet_since = now
            elif now - quiet_since >= 5:
                break
        await page.wait_for_timeout(500)
    else:
        raise TimeoutError("ChatGPT reply did not finish in time")
    copied = await page.evaluate(
        """async () => {
            const turns = document.querySelectorAll('[data-message-author-role="assistant"]');
            if (!turns.length) return '';
            const last = turns[turns.length - 1];
            const section = last.closest('[data-testid^="conversation-turn-"]') || last.parentElement;
            const btn = section && section.querySelector(
                '[data-testid="copy-turn-action-button"], button[aria-label="Copy"]'
            );
            if (!btn) return last.innerText || '';
            btn.click();
            await new Promise((r) => setTimeout(r, 300));
            try { return await navigator.clipboard.readText(); } catch { return last.innerText || ''; }
        }"""
    )
    return (copied or "").strip()


async def _complete_once(prompt: str, *, headed: bool, timeout_ms: int) -> str:
    from playwright.async_api import async_playwright

    profile_dir().mkdir(parents=True, exist_ok=True)
    model = (CHATGPT_WEB_MODEL or "").strip()
    query = ["temporary-chat=true"]
    if model:
        query.append(f"model={model}")
    url = f"{_CHAT}/?{'&'.join(query)}"
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(**_launch_args(headed=headed))
        try:
            await ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=_CHAT)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            if not await _has_session(ctx, page):
                raise RuntimeError("not logged in")
            return await _fill_and_wait(page, prompt, timeout_ms)
        finally:
            await ctx.close()


async def complete(prompt: str) -> str:
    """Send a prompt; headless after login, visible Chrome only if stealth fails."""
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
        try:
            if CHATGPT_WEB_HEADED:
                return await _complete_once(text, headed=True, timeout_ms=timeout_ms)
            return await _complete_once(text, headed=False, timeout_ms=timeout_ms)
        except Exception:
            if CHATGPT_WEB_HEADED:
                raise
            return await _complete_once(text, headed=True, timeout_ms=timeout_ms)


async def complete_json_prompt(system: str, user: str) -> str:
    blob = f"{system.strip()}\n\n{user.strip()}\n\nReturn ONLY valid JSON. No markdown."
    return await complete(blob)


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(login()) else 1)
