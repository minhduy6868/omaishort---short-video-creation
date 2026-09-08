"""Gemini native image via official HTTP (not a web scrape).

Same adapter slot as Pollinations/OpenAI images. Do not fork Gemini UI
or ImageFX into this tree — login-once Playwright is ChatGPT-text only.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import httpx
from PIL import Image

from omaishort.config import GEMINI_API_KEY, GEMINI_IMAGE_MODEL
from omaishort.providers.placeholder import HEIGHT, WIDTH


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
            "contents": [{"parts": [{"text": f"Vertical 9:16 photograph, no text overlay. {prompt[:3000]}"}]}],
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
