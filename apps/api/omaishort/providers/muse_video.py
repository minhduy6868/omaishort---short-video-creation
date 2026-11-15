"""Drama I2V via Muse Hatch (logged-in hub session). Multi×10s with continuity."""

from __future__ import annotations

import asyncio
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from PIL import Image

from omaishort.config import MUSE_WEB_ENABLED, MUSE_WEB_TIMEOUT_MIN, MUSE_WEB_VIDEO_ENABLED
from omaishort.engine.kenburns import extract_last_frame, ffmpeg_path
from omaishort.providers import muse_web
from omaishort.providers.muse_hatch import (
    MuseHatchClient,
    MuseHatchError,
    MuseImage,
    collect_assistant_text,
    collect_session_ids,
    extract_muse_media,
    muse_items,
)
from omaishort.providers.muse_plan import (
    muse_clip_prompt,
    muse_scene_count_for_duration,
    muse_scene_draft_prompt,
    parse_muse_scenes,
)
from omaishort.providers.muse_web import device_id

_PHOTO = {".png", ".jpg", ".jpeg", ".webp"}
_CAPABILITIES = [
    "chat_cancel",
    "delta_stream",
    "custom_reactions",
    "custom_reactions_facebook_thumbs_up_v1",
]
_VIDEO_STABLE_SEC = 2.5
_POLL_SLEEP_SEC = 2.0

# One Chromium + Hatch client for the whole compose job (set by muse_job_hub).
_shared_client: MuseHatchClient | None = None
_shared_depth = 0
_hub_active = False


def _mime(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suf == ".webp":
        return "image/webp"
    return "image/png"


def _prepare_image(path: Path) -> MuseImage:
    data = path.read_bytes()
    mime = _mime(path)
    if len(data) <= 3_500_000:
        return MuseImage(name=path.name, mime_type=mime, data=data)
    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        scale = min(1.0, 2048 / max(w, h))
        if scale < 1:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
        import io

        png_buf = io.BytesIO()
        img.save(png_buf, format="PNG")
        jpeg_buf = io.BytesIO()
        img.save(jpeg_buf, format="JPEG", quality=88)
        if png_buf.tell() <= jpeg_buf.tell():
            return MuseImage(name=path.stem + ".png", mime_type="image/png", data=png_buf.getvalue())
        return MuseImage(name=path.stem + ".jpg", mime_type="image/jpeg", data=jpeg_buf.getvalue())


def _media_aliases(item: dict[str, str]) -> list[str]:
    return [v for v in (item.get("path"), item.get("handle"), item.get("url")) if v]


def _dedupe_media(items: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: list[dict[str, str]] = []
    for item in items:
        aliases = _media_aliases(item)
        index = next(
            (i for i, existing in enumerate(unique) if any(a in _media_aliases(existing) for a in aliases)),
            -1,
        )
        if index < 0:
            unique.append(item)
        else:
            unique[index] = {
                **unique[index],
                **item,
                "path": item.get("path") or unique[index].get("path") or "",
                "url": item.get("url") or unique[index].get("url") or "",
                "handle": item.get("handle") or unique[index].get("handle") or "",
            }
    return unique


async def _concat_clips(clips: list[Path], dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    listing = dest.with_suffix(".concat.txt")
    listing.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for p in clips),
        encoding="utf-8",
    )
    cmd = [
        ffmpeg_path(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(listing),
        "-c",
        "copy",
        str(dest),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, err = await proc.communicate()
    if proc.returncode != 0 or not dest.is_file():
        cmd = [
            ffmpeg_path(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(dest),
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
        )
        _, err = await proc.communicate()
        if proc.returncode != 0 or not dest.is_file():
            raise RuntimeError(f"muse concat failed: {(err or b'')[:160]!r}")
    return dest


@asynccontextmanager
async def muse_job_hub() -> AsyncIterator[None]:
    """Hold one Muse Chromium + Hatch client for the whole compose job."""
    global _shared_client, _shared_depth, _hub_active
    if _hub_active:
        _shared_depth += 1
        try:
            yield
        finally:
            _shared_depth -= 1
        return
    if (
        not MUSE_WEB_ENABLED
        or not MUSE_WEB_VIDEO_ENABLED
        or not muse_web.playwright_ok()
        or not muse_web.is_authed()
    ):
        _hub_active = True
        try:
            yield
        finally:
            _hub_active = False
        return

    from playwright.async_api import async_playwright

    from omaishort.providers.chrome_profile import kill_stale_profile_chrome

    _hub_active = True
    _shared_depth = 1
    try:
        async with muse_web.session_lock:
            kill_stale_profile_chrome(muse_web.profile_dir())
            async with async_playwright() as pw:
                launch = muse_web.launch_args(headed=False)
                ctx = await pw.chromium.launch_persistent_context(**launch)
                client: MuseHatchClient | None = None
                try:
                    await muse_web.prepare(ctx)
                    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                    await muse_web.open_hub(page)
                    detected = await muse_web.detect_auth(ctx, page)
                    status = detected.get("authStatus")
                    if status == "Challenge":
                        checkpoint = detected.get("checkpoint_url")
                        muse_web.save_challenge(str(checkpoint) if checkpoint else None)
                        print(
                            "muse hub Challenge — finish Meta checkpoint"
                            + (f": {checkpoint}" if checkpoint else " (python -m omaishort --muse-login)"),
                            flush=True,
                        )
                        yield
                        return
                    if status != "Logged In" or not await muse_web.has_session(ctx):
                        muse_web.clear_authed()
                        print("muse hub not logged in (python -m omaishort --muse-login)", flush=True)
                        yield
                        return
                    cookies = [c for c in await ctx.cookies() if muse_web.muse_domain(str(c.get("domain") or ""))]
                    client = MuseHatchClient(cookies, request=ctx.request, timeout_min=MUSE_WEB_TIMEOUT_MIN)
                    await client.connect()
                    _shared_client = client
                    try:
                        yield
                    finally:
                        _shared_client = None
                        await client.close()
                finally:
                    await ctx.close()
    finally:
        _shared_client = None
        _shared_depth = 0
        _hub_active = False


class MuseVideoProvider:
    name = "muse"

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
        identity_refs: list[Path] | None = None,
    ) -> Path | None:
        del image_url, end_image_url, end_still
        if not MUSE_WEB_ENABLED or not MUSE_WEB_VIDEO_ENABLED:
            return None
        if not muse_web.playwright_ok() or not muse_web.is_authed():
            return None
        if still is None or not still.is_file() or still.suffix.lower() not in _PHOTO:
            return None
        compact = " ".join(str(prompt or "").split())
        if not compact:
            return None
        try:
            if _shared_client is not None:
                return await _generate_with_shared(compact, dest, still, duration, identity_refs or [])
            return await _generate_locked(compact, dest, still, duration, identity_refs or [])
        except MuseHatchError as exc:
            if exc.code == "AUTH_REQUIRED":
                if "checkpoint" in str(exc).lower():
                    muse_web.save_challenge()
                else:
                    muse_web.clear_authed()
            print(f"muse {exc.code}: {exc}", flush=True)
            return None
        except Exception as exc:
            print(f"muse fail {type(exc).__name__}: {exc}", flush=True)
            return None


async def _generate_with_shared(
    prompt: str,
    dest: Path,
    still: Path,
    duration: float,
    identity_refs: list[Path],
) -> Path | None:
    assert _shared_client is not None
    scene_count = muse_scene_count_for_duration(duration)
    timeout_ms = max(120_000, MUSE_WEB_TIMEOUT_MIN * 60_000)
    identity = [_prepare_image(p) for p in identity_refs if p.is_file() and p.suffix.lower() in _PHOTO][:6]
    start = _prepare_image(still)
    dest.parent.mkdir(parents=True, exist_ok=True)
    return await _run_hatch_shots(
        _shared_client,
        prompt,
        dest,
        start,
        identity,
        scene_count,
        timeout_ms,
    )


async def _generate_locked(
    prompt: str,
    dest: Path,
    still: Path,
    duration: float,
    identity_refs: list[Path],
) -> Path | None:
    """One-off Hatch session when compose did not open muse_job_hub."""
    if _hub_active:
        # Inside compose hub (possibly auth-failed) — do not re-enter Chrome.
        if _shared_client is None:
            return None
        return await _generate_with_shared(prompt, dest, still, duration, identity_refs)
    async with muse_job_hub():
        if _shared_client is None:
            return None
        return await _generate_with_shared(prompt, dest, still, duration, identity_refs)


async def _run_hatch_shots(
    client: MuseHatchClient,
    prompt: str,
    dest: Path,
    start: MuseImage,
    identity: list[MuseImage],
    scene_count: int,
    timeout_ms: int,
) -> Path | None:
    shots = [prompt]
    if scene_count > 1:
        before_draft = collect_session_ids(await _safe_list(client))
        draft_events = await client.subscribe(
            "/chat/stream",
            {
                "items": muse_items([], muse_scene_draft_prompt(prompt, scene_count)),
                "node_id": device_id(),
                "capabilities": _CAPABILITIES,
            },
            30_000,
        )
        draft_ids = collect_session_ids(draft_events)
        draft_session_id = draft_ids[-1] if draft_ids else None
        if not draft_session_id:
            after = collect_session_ids(await _safe_list(client))
            draft_session_id = next((v for v in after if v not in before_draft), after[0] if after else None)
        draft_text = ""
        deadline = asyncio.get_running_loop().time() + min(timeout_ms, 240_000) / 1000
        while asyncio.get_running_loop().time() < deadline and not parse_muse_scenes(draft_text, scene_count):
            history = await client.json_rpc(
                "GET",
                "/chat/history",
                {
                    **({"session_id": draft_session_id} if draft_session_id else {}),
                    "limit": 80,
                    "transcript_mode": "messages",
                },
            )
            draft_text = "\n".join(collect_assistant_text(history))
            if parse_muse_scenes(draft_text, scene_count):
                break
            await asyncio.sleep(2)
        parsed = parse_muse_scenes(draft_text, scene_count)
        if not parsed:
            print(f"muse draft missing {scene_count} shots", flush=True)
            return None
        shots = parsed

    with tempfile.TemporaryDirectory(prefix="muse-scenes-") as tmp:
        work = Path(tmp)
        clips: list[Path] = []
        continuity: MuseImage | None = None
        for index, shot in enumerate(shots):
            scene_images = ([continuity] if continuity else [start]) + identity
            before_sessions = collect_session_ids(await _safe_list(client))
            before_history = await _safe_history(client)
            baseline = {a for item in extract_muse_media(before_history) for a in _media_aliases(item)}
            has_continuity = continuity is not None or index == 0
            events = await client.subscribe(
                "/chat/stream",
                {
                    "items": muse_items(
                        scene_images,
                        muse_clip_prompt(shot, has_continuity_frame=has_continuity),
                    ),
                    "node_id": device_id(),
                    "capabilities": _CAPABILITIES,
                },
                30_000,
            )
            session_id = (collect_session_ids(events) or [None])[-1]
            if not session_id:
                after = collect_session_ids(await _safe_list(client))
                session_id = next((v for v in after if v not in before_sessions), after[0] if after else None)
            latest: list[dict[str, str]] = []
            stable_at = 0.0
            gen_deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
            while asyncio.get_running_loop().time() < gen_deadline:
                history = await client.json_rpc(
                    "GET",
                    "/chat/history",
                    {
                        **({"session_id": session_id} if session_id else {}),
                        "limit": 80,
                        "transcript_mode": "messages",
                    },
                )
                latest = _dedupe_media(
                    [
                        item
                        for item in extract_muse_media(history)
                        if item.get("type") == "Video"
                        and not any(a in baseline for a in _media_aliases(item))
                    ]
                )
                now = asyncio.get_running_loop().time()
                if latest:
                    if not stable_at:
                        stable_at = now
                    if now - stable_at >= _VIDEO_STABLE_SEC:
                        break
                else:
                    stable_at = 0.0
                print(f"muse generating shot {index + 1}/{len(shots)}", flush=True)
                await asyncio.sleep(_POLL_SLEEP_SEC)
            if not latest:
                print(f"muse no video for shot {index + 1}/{len(shots)}", flush=True)
                return None
            raw = await client.fetch_media(latest[0])
            clip_path = work / f"scene-{index + 1:02d}.mp4"
            clip_path.write_bytes(raw)
            clips.append(clip_path)
            if index < len(shots) - 1:
                frame_path = work / f"continuity-{index + 1:02d}.jpg"
                await extract_last_frame(clip_path, frame_path.with_suffix(".png"))
                png = frame_path.with_suffix(".png")
                continuity = _prepare_image(png if png.is_file() else clip_path)
        if len(clips) == 1:
            dest.write_bytes(clips[0].read_bytes())
        else:
            await _concat_clips(clips, dest)
    if dest.is_file() and dest.stat().st_size > 8000:
        print(f"muse ok {dest.stat().st_size}b shots={len(shots)}", flush=True)
        return dest
    return None


async def _safe_list(client: MuseHatchClient) -> Any:
    try:
        return await client.json_rpc("GET", "/api/session/list", {})
    except Exception:
        return None


async def _safe_history(client: MuseHatchClient) -> Any:
    try:
        return await client.json_rpc("GET", "/chat/history", {"limit": 80, "transcript_mode": "messages"})
    except Exception:
        return None
