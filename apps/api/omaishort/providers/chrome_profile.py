"""Shared Chrome / Playwright helpers for ChatGPT-web and Grok hub."""

from __future__ import annotations

import os
from pathlib import Path

_STEALTH = ["--disable-blink-features=AutomationControlled"]
_OFFSCREEN = ["--window-position=-32000,-32000", "--window-size=1280,900"]


def playwright_ok() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def system_chrome_exe() -> Path | None:
    """Installed Google Chrome — skip Playwright's 190MB CDN download when that host times out."""
    roots = [
        os.environ.get("PROGRAMFILES") or r"C:\Program Files",
        os.environ.get("PROGRAMFILES(X86)") or r"C:\Program Files (x86)",
        os.environ.get("LOCALAPPDATA") or "",
    ]
    for root in roots:
        if not root:
            continue
        exe = Path(root) / "Google" / "Chrome" / "Application" / "chrome.exe"
        if exe.is_file():
            return exe
    return None


def hub_launch_args(user_data_dir: Path, *, visible: bool, headless: bool = False) -> dict:
    """Persistent-profile launch for a hub.

    Background jobs use a real headed window parked off-screen. Cloudflare on chatgpt.com
    and grok.com challenges headless Chrome, so the composer or the fetch never answers.
    """
    args = list(_STEALTH)
    if not visible and not headless:
        args.extend(_OFFSCREEN)
    opts: dict = {
        "user_data_dir": str(user_data_dir),
        "headless": headless and not visible,
        "viewport": {"width": 1280, "height": 900},
        "args": args,
        # Google rejects Playwright's default --enable-automation ("this browser may not be secure").
        "ignore_default_args": ["--enable-automation"],
    }
    if system_chrome_exe() is not None:
        opts["channel"] = "chrome"
    return opts
