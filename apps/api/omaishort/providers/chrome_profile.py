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


_DESKTOP_BUF = None


def ensure_default_desktop(*, visible: bool = True) -> None:
    """Bind current thread and PEB ProcessParameters to WinSta0\\Default and SW_SHOWNORMAL on Windows."""
    global _DESKTOP_BUF
    if os.name != "nt":
        return
    try:
        import ctypes
        import ctypes.wintypes as wt

        u32 = ctypes.windll.user32
        hdesk = u32.OpenDesktopW("Default", 0, True, 0x01FF)
        if hdesk:
            u32.SetThreadDesktop(hdesk)
            u32.CloseDesktop(hdesk)

        class UNICODE_STRING(ctypes.Structure):
            _fields_ = [
                ("Length", wt.USHORT),
                ("MaximumLength", wt.USHORT),
                ("Buffer", ctypes.c_void_p),
            ]

        class PROCESS_BASIC_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("Reserved1", ctypes.c_void_p),
                ("PebBaseAddress", ctypes.c_void_p),
                ("Reserved2", ctypes.c_void_p * 2),
                ("UniqueProcessId", ctypes.c_void_p),
                ("Reserved3", ctypes.c_void_p),
            ]

        pbi = PROCESS_BASIC_INFORMATION()
        status = ctypes.windll.ntdll.NtQueryInformationProcess(
            ctypes.c_void_p(-1), 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None
        )
        if status == 0 and pbi.PebBaseAddress:
            pp = ctypes.c_void_p.from_address(pbi.PebBaseAddress + 0x20).value
            if pp:
                target = "WinSta0\\Default"
                if _DESKTOP_BUF is None:
                    _DESKTOP_BUF = ctypes.create_unicode_buffer(target)
                desk = UNICODE_STRING.from_address(pp + 0xC0)
                desk.Length = len(target) * 2
                desk.MaximumLength = (len(target) + 1) * 2
                desk.Buffer = ctypes.addressof(_DESKTOP_BUF)
                # WindowFlags (0xA8) = STARTF_USESHOWWINDOW (1), ShowWindowFlags (0xAC) = SW_SHOWNORMAL (1)
                ctypes.c_uint32.from_address(pp + 0xA8).value = 1
                ctypes.c_uint32.from_address(pp + 0xAC).value = 1 if visible else 0
    except Exception:
        pass


def kill_stale_profile_chrome(user_data_dir: Path) -> None:
    """Terminate any orphaned Chrome process still locking user_data_dir on a hidden desktop."""
    if os.name != "nt":
        return
    cookie_rel = ("Default/Network/Cookies", "Default/Cookies")
    locked = False
    for rel in cookie_rel:
        cpath = user_data_dir / rel
        if cpath.is_file():
            try:
                with open(cpath, "rb") as fh:
                    fh.read(4)
            except PermissionError:
                locked = True
                break
            except OSError:
                pass
    if not locked and not (user_data_dir / "SingletonLock").exists():
        return
    try:
        import subprocess

        needle = str(user_data_dir).replace("'", "''")
        ps_cmd = (
            "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe'\" | "
            f"Where-Object {{ $_.CommandLine -like '*{needle}*' }} | "
            "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
    except Exception:
        pass


def bring_chrome_windows_to_front() -> None:
    """Force any Chrome top-level windows on WinSta0\\Default to be shown and foregrounded."""
    if os.name != "nt":
        return
    try:
        import ctypes
        import ctypes.wintypes as wt

        u32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        u32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]

        def _cb(hwnd, _lparam):
            cls_buf = ctypes.create_unicode_buffer(64)
            u32.GetClassNameW(wt.HWND(hwnd), cls_buf, 64)
            if cls_buf.value == "Chrome_WidgetWin_1":
                title_buf = ctypes.create_unicode_buffer(256)
                u32.GetWindowTextW(wt.HWND(hwnd), title_buf, 256)
                title = (title_buf.value or "").lower()
                if any(
                    k in title
                    for k in (
                        "chatgpt",
                        "grok",
                        "openai",
                        "x.ai",
                        "imagine",
                        "sign in",
                        "log in",
                        "just a moment",
                        "auth",
                    )
                ):
                    u32.ShowWindow(wt.HWND(hwnd), 9)  # SW_RESTORE
                    u32.ShowWindow(wt.HWND(hwnd), 5)  # SW_SHOW
                    u32.SetForegroundWindow(wt.HWND(hwnd))
            return True

        u32.EnumWindows(WNDENUMPROC(_cb), 0)
    except Exception:
        pass


def hub_launch_args(user_data_dir: Path, *, visible: bool, headless: bool = False) -> dict:
    """Persistent-profile launch for a hub.

    Background jobs use a real headed window parked off-screen. Cloudflare on chatgpt.com
    and grok.com challenges headless Chrome, so the composer or the fetch never answers.
    """
    ensure_default_desktop(visible=visible)
    args = list(_STEALTH)
    if not visible and not headless:
        args.extend(_OFFSCREEN)
    elif visible:
        args.extend(["--window-position=120,60", "--window-size=1280,900"])
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
