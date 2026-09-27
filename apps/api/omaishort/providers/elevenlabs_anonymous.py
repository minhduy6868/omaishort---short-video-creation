"""ElevenLabs public voice, same shape as videoai: one captcha, then anonymous TTS."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path

import httpx

from omaishort.providers.chrome_profile import playwright_ok, system_chrome_exe

DEFAULT_VOICE = "aN7cv9yXNrfIR87bDmyD"
DEFAULT_MODEL = "eleven_v3"
MODELS = ("eleven_v3", "eleven_multilingual_v2")
# Premade library ids the anonymous endpoint accepts, plus the videoai default.
PUBLIC_VOICES: tuple[dict[str, str], ...] = (
    {"id": "aN7cv9yXNrfIR87bDmyD", "name": "Default"},
    {"id": "21m00Tcm4TlvDq8ikWAM", "name": "Rachel · nữ"},
    {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah · nữ"},
    {"id": "AZnzlk1XvdvUeBnXmlld", "name": "Domi · nữ"},
    {"id": "XB0fDUnXU5powFXDhCwa", "name": "Charlotte · nữ"},
    {"id": "jBpfuIE2acCO8z3wKNLl", "name": "Gigi · nữ"},
    {"id": "pFZP5JQG7iQjIQuC4Bku", "name": "Lily · nữ"},
    {"id": "ErXwobaYiN019PkySvjV", "name": "Antoni · nam"},
    {"id": "TxGEqnHWrfWFTfGW9XjX", "name": "Josh · nam"},
    {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam · nam"},
    {"id": "VR6AewLTigWG4xSOukaG", "name": "Arnold · nam"},
    {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel · nam"},
    {"id": "nPczCjzI2devNBz1zQrb", "name": "Brian · nam"},
    {"id": "iP95p4xoKVk53GoZ742B", "name": "Chris · nam"},
)
_APP = "https://elevenlabs.io/app"
_CAPTCHA_PAGE = "https://example.com"
_CAPTCHA_SITE_KEY = "8e58fe8c-1a48-4f94-88ae-8e90b586a192"
_CAPTCHA_SCRIPT = "https://js.hcaptcha.com/1/api.js?render=explicit&onload=__onHcaptchaLoaded"
_SETTINGS = {"stability": 0.5, "use_speaker_boost": True, "similarity_boost": 0.75, "style": 0, "speed": 1}


def _chunks(body: str) -> list[dict]:
    rows: list[dict] = []
    blob = body.replace("}{", "}\n{")
    for line in blob.splitlines():
        piece = line.strip()
        if not piece:
            continue
        try:
            item = json.loads(piece)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


async def captcha_token() -> str:
    """Open a window until the operator completes the ElevenLabs captcha."""
    if not playwright_ok():
        raise RuntimeError("Playwright Chromium is not installed")
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        launch: dict = {"headless": False, "args": ["--disable-blink-features=AutomationControlled"]}
        if system_chrome_exe() is not None:
            launch["channel"] = "chrome"
        browser = await pw.chromium.launch(**launch)
        page = await browser.new_page()
        try:
            print("ElevenLabs: complete the captcha in the Chrome window.", flush=True)
            await page.goto(_CAPTCHA_PAGE, wait_until="domcontentloaded")
            await page.evaluate(
                """({sitekey, scriptUrl}) => {
                    document.title = 'omaishort — ElevenLabs';
                    document.body.innerHTML = '<main style="font-family:Segoe UI,sans-serif;max-width:520px;margin:48px auto;color:#111"><h2>ElevenLabs</h2><p>Xác minh một lần để đọc lời thoại.</p><div id="hc-box"></div><p id="hc-status">Đang tải…</p></main>';
                    window.__hcToken = '';
                    window.__onHcaptchaLoaded = () => {
                        document.getElementById('hc-status').textContent = 'Hoàn tất ô xác minh.';
                        window.hcaptcha.render('hc-box', {
                            sitekey,
                            callback: (token) => { window.__hcToken = String(token || ''); },
                        });
                    };
                    const script = document.createElement('script');
                    script.src = scriptUrl;
                    script.async = true;
                    document.head.appendChild(script);
                }""",
                {"sitekey": _CAPTCHA_SITE_KEY, "scriptUrl": _CAPTCHA_SCRIPT},
            )
            deadline = time.monotonic() + 120
            token = ""
            while time.monotonic() < deadline:
                if page.is_closed():
                    break
                token = str(await page.evaluate("() => window.__hcToken || ''") or "")
                if token:
                    break
                await asyncio.sleep(0.4)
            if not token:
                raise RuntimeError("Chưa xác minh ElevenLabs")
            return token
        finally:
            await browser.close()


async def synthesize_anonymous(
    text: str, dest: Path, voice_id: str, model_id: str | None = None
) -> Path | None:
    spoken = (text or "").strip()
    voice = (voice_id or DEFAULT_VOICE).strip() or DEFAULT_VOICE
    model = model_id if model_id in MODELS else DEFAULT_MODEL
    if not spoken:
        return None
    try:
        token = await captcha_token()
    except Exception as exc:
        print(f"elevenlabs captcha {exc}", flush=True)
        return None
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream/with-timestamps/anonymous"
    payload = {
        "text": spoken[:4500],
        "model_id": model,
        "voice_settings": _SETTINGS,
        "hcaptcha_token": token,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream,application/json",
        "Origin": "https://elevenlabs.io",
        "Referer": _APP,
    }
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        print(f"elevenlabs anonymous {exc}", flush=True)
        return None
    if response.status_code >= 400:
        print(f"elevenlabs anonymous {response.status_code} {response.text[:180]}", flush=True)
        return None
    audio = bytearray()
    for row in _chunks(response.text):
        raw = row.get("audio_base64")
        if isinstance(raw, str) and raw:
            audio.extend(base64.b64decode(raw))
    if not audio:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(bytes(audio))
    return dest
