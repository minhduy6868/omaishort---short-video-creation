from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

from omaishort_schema.models import Motion, Shot


def ffmpeg_path() -> str:
    env = os.environ.get("FFMPEG_PATH", "").strip()
    if env and Path(env).exists():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("ffmpeg not found on PATH and imageio-ffmpeg is unavailable") from exc


def zoompan_expr(shot: Shot, frames: int) -> str:
    duration = max(1, frames)
    if shot.motion == Motion.zoom_in:
        z = "min(1+0.18*on/%d,1.18)" % duration
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif shot.motion == Motion.zoom_out:
        z = "if(eq(on,0),1.18,max(1.18-0.18*on/%d,1))" % duration
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    elif shot.motion == Motion.pan_right:
        z = "1.12"
        x = "min(%d*on/%d, iw-iw/zoom)" % (240, duration)
        y = "ih/2-(ih/zoom/2)"
    elif shot.motion == Motion.pan_left:
        z = "1.12"
        x = "max(iw-iw/zoom-%d*on/%d,0)" % (240, duration)
        y = "ih/2-(ih/zoom/2)"
    else:
        z = "1.04"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    return (
        f"scale=1350:2400:force_original_aspect_ratio=increase,"
        f"crop=1350:2400,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={duration}:s=1080x1920:fps=30,"
        f"format=yuv420p"
    )


async def render_shot_clip(still: Path, shot: Shot, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.2, shot.t_end - shot.t_start)
    frames = max(6, int(round(duration * 30)))
    vf = zoompan_expr(shot, frames)
    cmd = [
        ffmpeg_path(),
        "-y",
        "-loop",
        "1",
        "-i",
        str(still),
        "-vf",
        vf,
        "-t",
        f"{duration:.3f}",
        "-r",
        "30",
        "-an",
        "-pix_fmt",
        "yuv420p",
        str(dest),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, err = await proc.communicate()
    if proc.returncode != 0 or not dest.exists():
        raise RuntimeError(err.decode("utf-8", errors="ignore")[-800:] or "ffmpeg shot failed")
    return dest
