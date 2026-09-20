"""Drama I2V through the Grok hub session (in-page REST on grok.com/imagine)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from omaishort.config import GROK_WEB_ENABLED, GROK_WEB_TIMEOUT_MIN, GROK_WEB_VIDEO_ENABLED
from omaishort.providers import grok_web

_PHOTO = {".png", ".jpg", ".jpeg", ".webp"}
_CREATE_POST = "https://grok.com/rest/media/post/create"
_CONVERSATION = "https://grok.com/rest/app-chat/conversations/new"
_ASSETS = "https://assets.grok.com"


def grok_hub_duration_sec(duration: float) -> int:
    """Consumer Imagine video is 6s or 10s."""
    return 10 if float(duration) >= 8 else 6


def deep_first(root: object, keys: tuple[str, ...]) -> str:
    stack: list[object] = [root]
    seen: set[int] = set()
    while stack:
        value = stack.pop(0)
        if isinstance(value, dict):
            ident = id(value)
            if ident in seen:
                continue
            seen.add(ident)
            for key in keys:
                found = value.get(key)
                if isinstance(found, str) and found.strip():
                    return found.strip()
            stack.extend(value.values())
        elif isinstance(value, list):
            stack.extend(value)
    return ""


def absolute_asset(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if not url:
        return ""
    return f"{_ASSETS}{url if url.startswith('/') else '/' + url}"


def video_conversation_body(prompt: str, parent_post_id: str, seconds: int, content_url: str | None) -> dict:
    config = {
        "parentPostId": parent_post_id,
        "aspectRatio": "9:16",
        "videoLength": grok_hub_duration_sec(seconds),
        "isVideoEdit": False,
        "resolutionName": "720p",
    }
    message = " ".join(prompt.split())[:400]
    if content_url:
        message = f"{content_url}  {message} --mode=custom".strip()
    else:
        message = f"{message} --mode=custom".strip()
    body: dict = {
        "temporary": True,
        "modelName": "imagine-video-gen",
        "message": message,
        "enableSideBySide": True,
        "responseMetadata": {"experiments": [], "modelConfigOverride": {"modelMap": {"videoGenModelConfig": config}}},
    }
    if parent_post_id:
        body["fileAttachments"] = [parent_post_id]
    return body


def stream_video_url(raw: str) -> str:
    found = ""
    for line in raw.splitlines():
        blob = line.strip()
        if blob.startswith("data:"):
            blob = blob[5:].strip()
        if not blob or blob == "[DONE]" or not blob.startswith("{"):
            continue
        try:
            frame = json.loads(blob)
        except json.JSONDecodeError:
            continue
        stream = _stream_obj(frame)
        if stream.get("moderated") is True:
            return ""
        url = absolute_asset(str(stream.get("videoUrl") or ""))
        if not url:
            url = absolute_asset(deep_first(frame, ("videoUrl", "video_url")))
        if not url:
            continue
        progress = stream.get("progress")
        if progress is None or float(progress) >= 100:
            found = url
    return found


def _stream_obj(frame: object) -> dict:
    if not isinstance(frame, dict):
        return {}
    result = frame.get("result") if isinstance(frame.get("result"), dict) else {}
    response = result.get("response") if isinstance(result, dict) else {}
    stream = response.get("streamingVideoGenerationResponse") if isinstance(response, dict) else {}
    return stream if isinstance(stream, dict) else {}


class GrokHubVideoProvider:
    name = "grok_hub_video"

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
        del end_image_url, end_still, image_url
        if not GROK_WEB_ENABLED or not GROK_WEB_VIDEO_ENABLED:
            return None
        if not grok_web.playwright_ok() or not grok_web.is_authed():
            return None
        if still is None or not still.is_file() or still.suffix.lower() not in _PHOTO:
            return None
        async with grok_web.session_lock:
            return await _generate_locked(prompt, dest, still, duration)


async def _generate_locked(prompt: str, dest: Path, still: Path, duration: float) -> Path | None:
    from playwright.async_api import async_playwright

    mime = "image/jpeg" if still.suffix.lower() in {".jpg", ".jpeg"} else "image/webp" if still.suffix.lower() == ".webp" else "image/png"
    timeout_ms = max(60_000, GROK_WEB_TIMEOUT_MIN * 60_000)
    try:
        async with async_playwright() as pw:
            launch = grok_web.launch_args(headed=False)
            ctx = await pw.chromium.launch_persistent_context(**launch)
            try:
                if not await grok_web.has_session(ctx):
                    grok_web.clear_authed()
                    print("grok hub not logged in (python -m omaishort --grok-login)", flush=True)
                    return None
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                await page.goto(grok_web.IMAGINE, wait_until="domcontentloaded")
                status, uploaded = await grok_web.page_upload(page, still.read_bytes(), still.name, mime)
                if status >= 400 or not uploaded:
                    print(f"grok hub upload {status} {uploaded[:160]}", flush=True)
                    return None
                try:
                    payload = json.loads(uploaded)
                except json.JSONDecodeError:
                    print("grok hub upload not json", flush=True)
                    return None
                file_id = grok_hub_file_id(payload)
                file_uri = deep_first(payload, ("fileUri", "contentUrl", "url", "uri"))
                content_url = absolute_asset(file_uri) if file_uri else ""
                if not content_url and file_id:
                    content_url = f"{_ASSETS}/{file_id}/content"
                if not content_url:
                    print("grok hub upload missing url", flush=True)
                    return None
                status, created = await grok_web.page_fetch(
                    page,
                    _CREATE_POST,
                    body=json.dumps({"mediaType": "MEDIA_POST_TYPE_IMAGE", "mediaUrl": content_url}),
                )
                if status >= 400:
                    print(f"grok hub create-post {status} {created[:160]}", flush=True)
                    return None
                try:
                    post = json.loads(created)
                except json.JSONDecodeError:
                    print("grok hub create-post not json", flush=True)
                    return None
                parent = media_post_id(post)
                if not parent:
                    print("grok hub create-post no id", flush=True)
                    return None
                body = video_conversation_body(prompt, parent, int(duration), content_url)
                status, stream = await grok_web.page_fetch(
                    page,
                    _CONVERSATION,
                    body=json.dumps(body),
                    timeout_ms=timeout_ms,
                )
                if status >= 400:
                    print(f"grok hub conversation {status} {stream[:180]}", flush=True)
                    return None
                video_url = stream_video_url(stream)
                if not video_url:
                    print("grok hub no video url", flush=True)
                    return None
                cookies = await ctx.cookies()
                cookie_header = "; ".join(
                    f"{item.get('name')}={item.get('value')}"
                    for item in cookies
                    if grok_web.grok_domain(str(item.get("domain") or ""))
                )
            finally:
                await ctx.close()
    except Exception as exc:
        print(f"grok hub {exc}", flush=True)
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    headers = {"Accept": "video/mp4,video/*,*/*;q=0.8", "Referer": "https://grok.com/", "Cookie": cookie_header}
    try:
        async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
            res = await client.get(video_url, headers=headers)
            res.raise_for_status()
            if not res.content or res.content[:16].lstrip().startswith(b"<"):
                print("grok hub download not mp4", flush=True)
                return None
            dest.write_bytes(res.content)
    except Exception as exc:
        print(f"grok hub download {exc}", flush=True)
        return None
    return dest if dest.is_file() and dest.stat().st_size > 32 else None


def media_post_id(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    post = payload.get("post")
    if isinstance(post, dict):
        ident = post.get("id")
        if isinstance(ident, str) and ident.strip():
            return ident.strip()
    ident = payload.get("id")
    if isinstance(ident, str) and ident.strip():
        return ident.strip()
    return deep_first(payload, ("postId",))


def grok_hub_file_id(payload: object) -> str:
    return deep_first(payload, ("fileMetadataId", "fileId", "assetId"))
