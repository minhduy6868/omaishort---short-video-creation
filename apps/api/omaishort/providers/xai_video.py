"""xAI Grok Imagine video via official HTTP (not grok.com scrape)."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path

import httpx

from omaishort.config import (
    XAI_API_KEY,
    XAI_URL,
    XAI_VIDEO_ENABLED,
    XAI_VIDEO_MODEL,
    XAI_VIDEO_RESOLUTION,
)

_PHOTO = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_STILL_BYTES = 3_500_000


def xai_video_duration_sec(duration: float) -> int:
    """Imagine video accepts 1–15 seconds."""
    return max(1, min(15, int(round(float(duration))) or 8))


def xai_video_body(
    prompt: str,
    model: str,
    image_url: str,
    duration: float,
    *,
    resolution: str = "720p",
) -> dict:
    return {
        "model": model,
        "prompt": " ".join(prompt.split())[:400],
        "image": {"url": image_url},
        "duration": xai_video_duration_sec(duration),
        "aspect_ratio": "9:16",
        "resolution": resolution if resolution in {"480p", "720p", "1080p"} else "720p",
    }


def _data_uri(path: Path) -> str | None:
    if not path.is_file() or path.suffix.lower() not in _PHOTO:
        return None
    if path.stat().st_size > _MAX_STILL_BYTES:
        return None
    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/webp" if suffix == ".webp" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _video_url(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    video = payload.get("video")
    if isinstance(video, dict):
        url = video.get("url")
        if isinstance(url, str) and url.startswith("http"):
            return url
    url = payload.get("url")
    return url if isinstance(url, str) and url.startswith("http") else None


class XaiVideoProvider:
    name = "xai_video"

    async def generate(
        self,
        prompt: str,
        dest: Path,
        *,
        image_url: str | None,
        duration: float,
        still: Path | None = None,
        end_image_url: str | None = None,
        end_still: Path | None = None,
    ) -> Path | None:
        del end_image_url, end_still
        if not XAI_VIDEO_ENABLED or not XAI_API_KEY:
            return None
        start = image_url if image_url and image_url.startswith("http") else None
        if not start and still is not None:
            start = _data_uri(still)
        if not start:
            return None
        model = (XAI_VIDEO_MODEL or "grok-imagine-video-1.5").strip()
        body = xai_video_body(
            prompt,
            model,
            start,
            duration,
            resolution=XAI_VIDEO_RESOLUTION,
        )
        headers = {
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        }
        base = XAI_URL.rstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                created = await client.post(f"{base}/videos/generations", headers=headers, json=body)
            if created.status_code >= 400:
                print(f"xai video {created.status_code} {created.text[:180]}", flush=True)
                return None
            payload = created.json()
            ready = _video_url(payload)
            if ready:
                return await _download_mp4(ready, dest)
            request_id = payload.get("request_id") if isinstance(payload, dict) else None
            if not isinstance(request_id, str) or not request_id:
                print("xai video no request_id", flush=True)
                return None
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                for _ in range(60):
                    await asyncio.sleep(5.0)
                    polled = await client.get(f"{base}/videos/{request_id}", headers=headers)
                    if polled.status_code >= 400:
                        continue
                    try:
                        status_body = polled.json()
                    except Exception:
                        continue
                    status = str(status_body.get("status") or "").lower() if isinstance(status_body, dict) else ""
                    if status in {"failed", "expired", "error"}:
                        print(f"xai video {status}", flush=True)
                        return None
                    video_url = _video_url(status_body)
                    if video_url:
                        return await _download_mp4(video_url, dest)
            print("xai video poll timeout", flush=True)
            return None
        except Exception as exc:
            print(f"xai video fail {type(exc).__name__}", flush=True)
            return None


async def _download_mp4(url: str, dest: Path) -> Path | None:
    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(url)
        if response.status_code >= 400 or len(response.content) < 8000:
            return None
        dest.write_bytes(response.content)
        return dest
    except Exception:
        return None
