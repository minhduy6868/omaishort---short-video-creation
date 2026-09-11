from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path

from omaishort_schema.models import Camera, Motion, Shot

# still-motion: zoompan at 2× output so 1080p steps are sub-pixel, then the filter scales to s=.
_WORK_W = 2160
_WORK_H = 3840
# Keep the working crop inside the still. close_up is drama-only; editorial lenses stay medium/wide.
_ZOOM = {
    Camera.wide: 0.04,
    Camera.medium: 0.05,
    Camera.close_up: 0.12,
}
_ZOOM_EDITORIAL = {
    Camera.wide: 0.08,
    Camera.medium: 0.11,
    Camera.close_up: 0.12,
}


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


def ffmpeg_info(path: Path) -> str:
    result = subprocess.run(
        [ffmpeg_path(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return f"{result.stderr or ''}{result.stdout or ''}"


def probe_duration(path: Path) -> float:
    info = ffmpeg_info(path)
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:[.,]\d+)?)", info)
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds.replace(",", "."))


def probe_video_size(path: Path) -> tuple[int, int] | None:
    info = ffmpeg_info(path)
    match = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", info)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def has_audio_stream(path: Path) -> bool:
    return "Audio:" in ffmpeg_info(path)


def zoompan_expr(shot: Shot, frames: int, *, editorial: bool = False) -> str:
    duration = max(1, frames)
    table = _ZOOM_EDITORIAL if editorial else _ZOOM
    amp = table.get(shot.camera, table[Camera.medium])
    ease = f"(1-cos(PI*on/{duration}))/2"
    center_x = "iw/2-(iw/zoom/2)"
    center_y = "ih/2-(ih/zoom/2)"
    hold_k = 0.28 if editorial else 0.12
    pan_k = 0.50 if editorial else 0.35
    if shot.motion == Motion.zoom_in:
        z = f"1+{amp:.2f}*{ease}"
        x, y = center_x, center_y
    elif shot.motion == Motion.zoom_out:
        z = f"{1 + amp:.2f}-{amp:.2f}*{ease}"
        x, y = center_x, center_y
    elif shot.motion == Motion.pan_right:
        z = f"{1 + amp * pan_k:.2f}"
        x = f"(iw-iw/zoom)*{ease}"
        y = center_y
    elif shot.motion == Motion.pan_left:
        z = f"{1 + amp * pan_k:.2f}"
        x = f"(iw-iw/zoom)*(1-{ease})"
        y = center_y
    else:
        z = f"1+{amp * hold_k:.2f}*{ease}"
        x, y = center_x, center_y
    return (
        f"scale={_WORK_W}:{_WORK_H}:force_original_aspect_ratio=increase,"
        f"crop={_WORK_W}:{_WORK_H},"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={duration}:s=1080x1920:fps=30,"
        f"format=yuv420p"
    )


async def render_shot_clip(still: Path, shot: Shot, dest: Path, *, editorial: bool = False) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.2, shot.t_end - shot.t_start)
    frames = max(6, int(round(duration * 30)))
    vf = zoompan_expr(shot, frames, editorial=editorial)
    cmd = [
        ffmpeg_path(),
        "-y",
        "-loop",
        "1",
        "-i",
        str(still),
        "-vf",
        vf,
        "-frames:v",
        str(frames),
        "-r",
        "30",
        "-an",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        str(dest),
    ]
    await _run_ffmpeg(cmd, dest, "ffmpeg shot failed")
    return dest


async def conform_clip(src: Path, dest: Path, duration: float) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.2, duration)
    frames = max(6, int(round(duration * 30)))
    src_dur = probe_duration(src) or duration
    factor = duration / max(0.05, src_dur)
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"setpts=PTS*{factor:.6f},"
        "fps=30,"
        "format=yuv420p"
    )
    cmd = [
        ffmpeg_path(),
        "-y",
        "-i",
        str(src),
        "-vf",
        vf,
        "-frames:v",
        str(frames),
        "-r",
        "30",
        "-an",
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        str(dest),
    ]
    await _run_ffmpeg(cmd, dest, "ffmpeg conform failed")
    return dest


async def _run_ffmpeg(cmd: list[str], dest: Path, err_label: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
    )
    _, err = await proc.communicate()
    if proc.returncode != 0 or not dest.exists():
        raise RuntimeError(err.decode("utf-8", errors="ignore")[-800:] or err_label)
