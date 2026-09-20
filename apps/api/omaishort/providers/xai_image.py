"""xAI Grok Imagine via official HTTP (not grok.com scrape).

LocalForge Grok splits no-ref Imagine vs with-ref image-edit. Same split here:
`/v1/images/generations` vs `/v1/images/edits` with passport data URIs.
Do not port grok.com WebSocket or ChatGPT Images.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import httpx
from PIL import Image

from omaishort.config import XAI_API_KEY, XAI_IMAGE_MODEL, XAI_URL
from omaishort.providers.placeholder import HEIGHT, WIDTH

_PHOTO = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_REF_BYTES = 3_500_000
_LEAD = "Vertical 9:16 photograph, no text overlay."


def xai_ref_limit(model: str) -> int:
    """Official multi-image edit: 5 on Imagine 2.0, else 3. grok.com's 7-ref cap is scrape-only."""
    return 5 if "2.0" in (model or "") else 3


def xai_image_body(prompt: str, model: str) -> dict:
    return {
        "model": model,
        "prompt": f"{_LEAD} {prompt}"[:3800],
        "n": 1,
        "aspect_ratio": "9:16",
    }


def xai_edit_body(prompt: str, model: str, refs: list[Path]) -> dict | None:
    images = [_data_uri(path) for path in _usable_refs(refs, xai_ref_limit(model))]
    if not images:
        return None
    lead = _LEAD + " Keep the exact face, hair, and clothes from the attached reference photograph."
    payload: dict = {
        "model": model,
        "prompt": f"{lead} {prompt}"[:3800],
        "n": 1,
        "aspect_ratio": "9:16",
    }
    items = [{"url": uri, "type": "image_url"} for uri in images]
    payload["image"] = items[0] if len(items) == 1 else items
    return payload


def _usable_refs(refs: list[Path] | None, limit: int) -> list[Path]:
    out: list[Path] = []
    for path in refs or []:
        if not _usable_ref(path):
            continue
        out.append(path)
        if len(out) >= limit:
            break
    return out


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


def _data_uri(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/webp" if suffix == ".webp" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _write_png(raw: bytes, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    img.save(dest, "PNG")
    return dest


class XaiImageProvider:
    name = "xai_image"

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        if not XAI_API_KEY:
            return None
        model = (XAI_IMAGE_MODEL or "grok-imagine-image").strip()
        edit = xai_edit_body(prompt, model, refs or [])
        path = "/images/edits" if edit else "/images/generations"
        body = edit or xai_image_body(prompt, model)
        url = f"{XAI_URL.rstrip('/')}{path}"
        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=body)
                if response.status_code >= 400:
                    return None
                data = (response.json() or {}).get("data") or []
                if not data or not isinstance(data[0], dict):
                    return None
                first = data[0]
                if first.get("b64_json"):
                    return _write_png(base64.b64decode(first["b64_json"]), dest)
                image_url = first.get("url")
                if not isinstance(image_url, str) or not image_url.startswith("http"):
                    return None
                raw = await client.get(image_url)
                if raw.status_code >= 400:
                    return None
                return _write_png(raw.content, dest)
        except Exception:
            return None
