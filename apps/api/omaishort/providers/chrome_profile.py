"""Shared Chrome / Playwright helpers for ChatGPT-web and Grok hub."""

from __future__ import annotations

import os
from pathlib import Path


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
