from __future__ import annotations

import asyncio
import base64
import io
from pathlib import Path
from typing import Protocol

import httpx
from PIL import Image

from omaishort.config import (
    COMFYUI_URL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_IMAGE_MODEL,
    POLLINATIONS_ENABLED,
)
from omaishort.providers.placeholder import HEIGHT, WIDTH, paint_placeholder_still
from omaishort.providers.pollinations import PollinationsImageProvider, looks_like_photo


class ImageProvider(Protocol):
    name: str

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        ...


class PlaceholderImageProvider:
    name = "placeholder"

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        img = paint_placeholder_still(prompt, refs)
        img.save(dest, "PNG")
        return dest


class ComfyUIImageProvider:
    name = "comfyui"

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                ping = await client.get(f"{COMFYUI_URL}/system_stats")
                ping.raise_for_status()
        except Exception:
            return None
        return None


class OpenAIImageProvider:
    name = "openai_image"

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        if not OPENAI_API_KEY:
            return None
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": OPENAI_IMAGE_MODEL,
            "prompt": prompt[:3800],
            "size": "1024x1792",
            "n": 1,
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{OPENAI_BASE_URL}/images/generations",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()["data"][0]
                dest.parent.mkdir(parents=True, exist_ok=True)
                if "b64_json" in data:
                    dest.write_bytes(base64.b64decode(data["b64_json"]))
                    return dest
                url = data.get("url")
                if not url:
                    return None
                raw = await client.get(url)
                raw.raise_for_status()
                img = Image.open(io.BytesIO(raw.content)).convert("RGB")
                img = img.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
                img.save(dest, "PNG")
                return dest
        except Exception:
            return None


async def generate_image(
    prompt: str,
    dest: Path,
    refs: list[Path] | None = None,
    *,
    photo: bool = False,
    skip_remote: bool = False,
) -> tuple[Path, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if skip_remote:
        img = paint_placeholder_still(prompt, refs)
        img.save(dest, "PNG")
        return dest, "placeholder"

    require_photo = photo and (POLLINATIONS_ENABLED or bool(OPENAI_API_KEY))
    poll = PollinationsImageProvider()
    attempts = 2 if require_photo else 1
    for attempt in range(attempts):
        result = await poll.generate(prompt, dest, refs)
        if result is not None and (not require_photo or looks_like_photo(result)):
            return result, poll.name
        if require_photo and attempt < attempts - 1:
            await asyncio.sleep(16)

    if not require_photo:
        comfy = await ComfyUIImageProvider().generate(prompt, dest, refs)
        if comfy is not None:
            return comfy, "comfyui"

    openai = await OpenAIImageProvider().generate(prompt, dest, refs)
    if openai is not None and (not require_photo or looks_like_photo(openai)):
        return openai, "openai_image"

    if require_photo:
        raise RuntimeError(f"could not generate a photographic still for {dest.name}")
    img = paint_placeholder_still(prompt, refs)
    img.save(dest, "PNG")
    return dest, "placeholder"
