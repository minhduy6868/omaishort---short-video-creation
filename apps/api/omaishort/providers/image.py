from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path
from typing import Protocol

import httpx
from PIL import Image, ImageDraw, ImageFont

from omaishort.config import COMFYUI_URL, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_IMAGE_MODEL

WIDTH = 1080
HEIGHT = 1920


class ImageProvider(Protocol):
    name: str

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        ...


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:18]


class PlaceholderImageProvider:
    name = "placeholder"

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        seed = int(hashlib.md5(prompt.encode("utf-8")).hexdigest()[:8], 16) % 360
        top = _hsl_to_rgb((seed + 20) % 360, 0.28, 0.16)
        bottom = _hsl_to_rgb((seed + 200) % 360, 0.22, 0.08)
        img = Image.new("RGB", (4, HEIGHT), top)
        for y in range(HEIGHT):
            t = y / HEIGHT
            color = (
                int(top[0] + (bottom[0] - top[0]) * t),
                int(top[1] + (bottom[1] - top[1]) * t),
                int(top[2] + (bottom[2] - top[2]) * t),
            )
            img.paste(color, (0, y, 4, y + 1))
        img = img.resize((WIDTH, HEIGHT), Image.Resampling.BILINEAR)
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", 36)
            small = ImageFont.truetype("arial.ttf", 28)
        except OSError:
            font = ImageFont.load_default()
            small = font
        draw.rectangle((64, 160, WIDTH - 64, HEIGHT - 220), outline=(232, 210, 180), width=2)
        lines = _wrap(draw, prompt.replace("\n", " "), small, WIDTH - 180)
        y = 240
        for line in lines:
            draw.text((96, y), line, fill=(236, 228, 214), font=small)
            y += 40
        if refs:
            draw.text((96, HEIGHT - 160), f"refs: {len(refs)}", fill=(200, 170, 130), font=font)
        img.save(dest, "PNG")
        return dest


class ComfyUIImageProvider:
    name = "comfyui"

    async def generate(self, prompt: str, dest: Path, refs: list[Path] | None = None) -> Path | None:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                ping = await client.get(f"{COMFYUI_URL}/system_stats")
                ping.raise_for_status()
        except Exception:
            return None
        # Workflow wiring is machine-specific; ping-only stub falls through.
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


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    c = (1 - abs(2 * l - 1)) * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)


async def generate_image(prompt: str, dest: Path, refs: list[Path] | None = None) -> tuple[Path, str]:
    providers: list[ImageProvider] = [
        ComfyUIImageProvider(),
        OpenAIImageProvider(),
        PlaceholderImageProvider(),
    ]
    for provider in providers:
        result = await provider.generate(prompt, dest, refs)
        if result is not None:
            return result, provider.name
    raise RuntimeError("no image provider produced a still")
