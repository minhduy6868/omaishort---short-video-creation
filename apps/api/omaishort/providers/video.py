from __future__ import annotations

from pathlib import Path
from typing import Protocol
from urllib.parse import quote, urlencode
import json

import httpx

from omaishort.config import (
    COMFYUI_URL,
    HF_I2V_ENABLED,
    HF_I2V_SPACE_URL,
    HF_I2V_WAN_URL,
    HF_TOKEN,
    POLLINATIONS_KEY,
    POLLINATIONS_VIDEO_ENABLED,
    POLLINATIONS_VIDEO_MODEL,
    POLLINATIONS_VIDEO_URL,
)
from omaishort.providers.pollinations import load_ref_url, looks_like_photo


class VideoProvider(Protocol):
    name: str

    async def generate(
        self,
        prompt: str,
        dest: Path,
        *,
        image_url: str | None,
        duration: float,
        still: Path | None = None,
    ) -> Path | None:
        ...


class ComfyUIVideoProvider:
    name = "comfyui_video"

    async def generate(
        self,
        prompt: str,
        dest: Path,
        *,
        image_url: str | None,
        duration: float,
        still: Path | None = None,
    ) -> Path | None:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                ping = await client.get(f"{COMFYUI_URL}/system_stats")
                ping.raise_for_status()
        except Exception:
            return None
        return None


def _hf_headers() -> dict[str, str]:
    if not HF_TOKEN:
        return {}
    return {"Authorization": f"Bearer {HF_TOKEN}"}


def _gradio_file_data(path: str, orig_name: str, url: str | None = None) -> dict:
    """Gradio 5 ImageData: path or url required; public examples set both to the same http URL."""
    data: dict = {
        "path": path,
        "orig_name": orig_name,
        "meta": {"_type": "gradio.FileData"},
    }
    resolved = url or (path if path.startswith("http") else None)
    if resolved:
        data["url"] = resolved
    return data


def _file_data_from_upload(payload, orig_name: str, base: str) -> dict | None:
    remote = payload[0] if isinstance(payload, list) and payload else payload
    if isinstance(remote, dict) and remote.get("path"):
        path = str(remote["path"])
        url = remote.get("url")
        if not isinstance(url, str) or not url:
            url = path if path.startswith("http") else f"{base}/gradio_api/file={path}"
        return _gradio_file_data(path, str(remote.get("orig_name") or orig_name), url)
    if isinstance(remote, str) and remote:
        url = remote if remote.startswith("http") else f"{base}/gradio_api/file={remote}"
        return _gradio_file_data(remote, orig_name, url)
    return None


async def _resolve_gradio_image(
    client: httpx.AsyncClient,
    base: str,
    *,
    still: Path | None,
    image_url: str | None,
    log: str,
) -> dict | None:
    # Public URL first so Spaces can fetch without a local upload.
    if image_url:
        name = still.name if still is not None else "still.png"
        return _gradio_file_data(image_url, name, image_url)
    if still is None or not still.exists():
        return None
    uploaded = await client.post(
        f"{base}/gradio_api/upload",
        files={"files": (still.name, still.read_bytes(), "image/png")},
    )
    if uploaded.status_code >= 400:
        print(f"{log} upload {uploaded.status_code}", flush=True)
        return None
    try:
        return _file_data_from_upload(uploaded.json(), still.name, base)
    except Exception:
        return None


async def _gradio_await_video(
    client: httpx.AsyncClient,
    base: str,
    endpoint: str,
    data: list,
    dest: Path,
    log: str,
) -> Path | None:
    last_err = "no video url"
    for _attempt in range(2):
        posted = await client.post(
            f"{base}/gradio_api/call/{endpoint}",
            json={"data": data},
            headers={"Content-Type": "application/json"},
        )
        if posted.status_code >= 400:
            last_err = f"{posted.status_code} {posted.text[:160]}"
            print(f"{log} {last_err}", flush=True)
            continue
        event_id = (posted.json() or {}).get("event_id")
        if not event_id:
            last_err = "missing event_id"
            print(f"{log} missing event_id", flush=True)
            continue
        print(f"{log} queued {event_id[:8]}", flush=True)
        video_url = None
        async with client.stream("GET", f"{base}/gradio_api/call/{endpoint}/{event_id}") as stream:
            event = ""
            async for line in stream.aiter_lines():
                if line.startswith("event:"):
                    event = line.split(":", 1)[1].strip()
                elif line.startswith("data:"):
                    raw = line.split(":", 1)[1].strip()
                    if event in {"error", "unexpected_error"}:
                        last_err = raw[:160]
                        print(f"{log} error {last_err}", flush=True)
                        video_url = None
                        break
                    if event == "complete":
                        video_url = _video_url_from_sse(raw, base)
                        if not video_url:
                            last_err = f"complete {raw[:160]}"
                            print(f"{log} {last_err}", flush=True)
                        break
        if not video_url:
            continue
        video = await client.get(video_url)
        if video.status_code >= 400 or len(video.content) < 8000:
            last_err = f"download {video.status_code}"
            print(f"{log} {last_err}", flush=True)
            continue
        dest.write_bytes(video.content)
        print(f"{log} ok {len(video.content)}b", flush=True)
        return dest
    print(f"{log} fail {last_err}", flush=True)
    return None


class HuggingFaceWanFastProvider:
    """Free Wan 2.1 I2V via multimodalart/wan2-1-fast (ZeroGPU A10G, 4 steps)."""

    name = "hf_space_wan"

    async def generate(
        self,
        prompt: str,
        dest: Path,
        *,
        image_url: str | None,
        duration: float,
        still: Path | None = None,
    ) -> Path | None:
        if not HF_I2V_ENABLED or not HF_TOKEN:
            return None
        compact = " ".join(prompt.split())[:400]
        seconds = max(1.0, min(2.0, float(duration)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        base = HF_I2V_WAN_URL.rstrip("/")
        negative = (
            "Bright tones, overexposed, static, blurred details, subtitles, watermark, text, "
            "worst quality, still picture"
        )
        try:
            async with httpx.AsyncClient(
                timeout=300.0, follow_redirects=True, headers=_hf_headers()
            ) as client:
                file_data = await _resolve_gradio_image(
                    client, base, still=still, image_url=image_url, log="hf wan"
                )
                if file_data is None:
                    return None
                return await _gradio_await_video(
                    client,
                    base,
                    "generate_video",
                    [
                        file_data,
                        compact,
                        512,
                        320,
                        negative,
                        seconds,
                        1.0,
                        4,
                        42,
                        True,
                    ],
                    dest,
                    "hf wan",
                )
        except Exception as exc:
            print(f"hf wan fail {type(exc).__name__}", flush=True)
            return None


class HuggingFaceSpaceVideoProvider:
    """Free LTX I2V via the public Hugging Face Space (ZeroGPU queue)."""

    name = "hf_space_ltx"

    async def generate(
        self,
        prompt: str,
        dest: Path,
        *,
        image_url: str | None,
        duration: float,
        still: Path | None = None,
    ) -> Path | None:
        if not HF_I2V_ENABLED or not HF_TOKEN:
            return None
        compact = " ".join(prompt.split())[:400]
        seconds = max(1.0, min(2.0, float(duration)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        base = HF_I2V_SPACE_URL.rstrip("/")
        try:
            async with httpx.AsyncClient(
                timeout=300.0, follow_redirects=True, headers=_hf_headers()
            ) as client:
                file_data = await _resolve_gradio_image(
                    client, base, still=still, image_url=image_url, log="hf i2v"
                )
                if file_data is None:
                    return None
                return await _gradio_await_video(
                    client,
                    base,
                    "image_to_video",
                    [
                        compact,
                        "worst quality, inconsistent motion, blurry, jittery, distorted, watermark, text, subtitles",
                        file_data,
                        None,
                        512,
                        320,
                        "image-to-video",
                        seconds,
                        9,
                        42,
                        True,
                        1.0,
                        False,
                    ],
                    dest,
                    "hf i2v",
                )
        except Exception as exc:
            print(f"hf i2v fail {type(exc).__name__}", flush=True)
            return None


def _video_url_from_sse(raw: str, base: str) -> str | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    item = data[0] if isinstance(data, list) and data else data
    if isinstance(item, str) and item.startswith("http"):
        return item
    if not isinstance(item, dict):
        return None
    url = item.get("url") or item.get("video") or item.get("path")
    if isinstance(url, dict):
        url = url.get("url") or url.get("path")
    if not isinstance(url, str) or not url:
        return None
    if url.startswith("http"):
        return url
    if url.startswith("/"):
        return f"{base}{url}"
    return f"{base}/gradio_api/file={url}"


class PollinationsVideoProvider:
    name = "pollinations_video"

    async def generate(
        self,
        prompt: str,
        dest: Path,
        *,
        image_url: str | None,
        duration: float,
        still: Path | None = None,
    ) -> Path | None:
        if not POLLINATIONS_VIDEO_ENABLED or not POLLINATIONS_KEY or not image_url:
            return None
        compact = " ".join(prompt.split())[:400]
        seconds = 5 if "wan-fast" in POLLINATIONS_VIDEO_MODEL else max(4, min(5, int(round(duration))))
        params = {
            "model": POLLINATIONS_VIDEO_MODEL,
            "duration": str(seconds),
            "aspectRatio": "9:16",
            "image": image_url,
            "audio": "false",
            "referrer": "omaishort",
        }
        url = f"{POLLINATIONS_VIDEO_URL.rstrip('/')}/video/{quote(compact, safe='')}?{urlencode(params)}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            headers = {
                "Accept": "video/mp4",
                "Authorization": f"Bearer {POLLINATIONS_KEY}",
            }
            async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)
            if response.status_code >= 400:
                detail = (response.text or "")[:180].replace("\n", " ")
                print(f"pollinations video {response.status_code} {detail}", flush=True)
                return None
            ctype = (response.headers.get("content-type") or "").lower()
            body = response.content
            if "json" in ctype or "html" in ctype or len(body) < 8000:
                return None
            dest.write_bytes(body)
            return dest
        except Exception:
            return None


async def generate_clip(
    prompt: str,
    dest: Path,
    still: Path,
    *,
    duration: float,
) -> tuple[Path, str] | None:
    image_url = load_ref_url(still)
    if not image_url and not looks_like_photo(still):
        return None
    providers: list[VideoProvider] = [
        HuggingFaceWanFastProvider(),
        HuggingFaceSpaceVideoProvider(),
        PollinationsVideoProvider(),
        ComfyUIVideoProvider(),
    ]
    for provider in providers:
        result = await provider.generate(
            prompt, dest, image_url=image_url, duration=duration, still=still
        )
        if result is not None:
            return result, provider.name
    return None
