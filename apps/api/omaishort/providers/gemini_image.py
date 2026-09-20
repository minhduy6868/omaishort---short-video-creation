"""Gemini native image via official HTTP (not a web scrape).

Banana / Nano Banana in Google Flow is the same family — we call Gemini
`generateContent`, not labs.google/fx. Login-once Playwright stays ChatGPT-text only.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import httpx
from PIL import Image

from omaishort.config import GEMINI_API_KEY, GEMINI_IMAGE_MODEL
from omaishort.providers.placeholder import HEIGHT, WIDTH

_PHOTO = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_REF_BYTES = 3_500_000


def gemini_image_parts(prompt: str, refs: list[Path] | None = None) -> list[dict]:
    """Text plus Banana-class refs (up to four photo stills). Identity from the photo, not a new face dump."""
    lead = "Vertical 9:16 photograph, no text overlay."
    attached = [path for path in (refs or []) if _usable_ref(path)][:4]
    if attached:
        lead += " Keep the exact face, hair, and clothes from the attached reference photograph."
    parts: list[dict] = [{"text": f"{lead} {prompt[:2800]}"}]
    for path in attached:
        raw = path.read_bytes()
        mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        if path.suffix.lower() == ".webp":
            mime = "image/webp"
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(raw).decode()}})
    return parts


def _usable_ref(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() not in _PHOTO:
        return False
    size = path.stat().st_size
    if size < 8000 or size > _MAX_REF_BYTES:
        return False
    try:
        from omaishort.providers.pollinations import looks_like_photo

        return looks_like_photo(path)
    except Exception:
        return True


class GeminiImageProvider:
    name = "gemini_image"

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        if not GEMINI_API_KEY:
            return None
        model = (GEMINI_IMAGE_MODEL or "gemini-2.5-flash-image").strip()
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        payload = {
            "contents": [{"parts": gemini_image_parts(prompt, refs)}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    params={"key": GEMINI_API_KEY},
                    json=payload,
                )
                if response.status_code >= 400:
                    return None
                raw = _inline_image(response.json())
                if not raw:
                    return None
                dest.parent.mkdir(parents=True, exist_ok=True)
                img = Image.open(io.BytesIO(raw)).convert("RGB")
                img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
                img.save(dest, "PNG")
                return dest
        except Exception:
            return None


def _inline_image(body: object) -> bytes:
    if not isinstance(body, dict):
        return b""
    for cand in body.get("candidates") or []:
        content = cand.get("content") if isinstance(cand, dict) else None
        parts = (content or {}).get("parts") if isinstance(content, dict) else None
        for part in parts or []:
            if not isinstance(part, dict):
                continue
            blob = part.get("inlineData") or part.get("inline_data") or {}
            data = blob.get("data") if isinstance(blob, dict) else None
            if isinstance(data, str) and len(data) > 20:
                try:
                    return base64.b64decode(data)
                except Exception:
                    return b""
    return b""
