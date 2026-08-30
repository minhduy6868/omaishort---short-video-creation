from __future__ import annotations

import asyncio
from pathlib import Path

from omaishort.config import ASSETS_DIR
from omaishort.engine.kenburns import ffmpeg_path, render_shot_clip
from omaishort_schema.models import Storyboard


async def compose_short(
    board: Storyboard,
    stills: dict[str, Path],
    audio_path: Path,
    ass_path: Path,
    dest: Path,
    work_dir: Path,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    clips_dir = work_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_paths: list[Path] = []
    n = 0
    for scene in board.scenes:
        still = stills[scene.still_id]
        for shot in scene.shots:
            n += 1
            clip = clips_dir / f"clip_{n:03d}.mp4"
            await render_shot_clip(still, shot, clip)
            clip_paths.append(clip)
    concat_file = work_dir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for p in clip_paths),
        encoding="utf-8",
    )
    silent = work_dir / "video_silent.mp4"
    cmd_concat = [
        ffmpeg_path(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        str(silent),
    ]
    await _run(cmd_concat, cwd=work_dir)

    bgm = ASSETS_DIR / "music" / "underscore.mp3"
    local_ass = work_dir / "captions.ass"
    if ass_path.resolve() != local_ass.resolve():
        local_ass.write_bytes(ass_path.read_bytes())
    filter_parts = [f"[0:v]subtitles={local_ass.name}[v]"]
    inputs = ["-i", silent.name, "-i", str(audio_path.resolve())]
    maps = ["-map", "[v]", "-map", "1:a:0"]
    if bgm.exists():
        inputs += ["-i", str(bgm.resolve())]
        filter_parts.append("[1:a]volume=1.0[vo]")
        filter_parts.append("[2:a]volume=0.12[bg]")
        filter_parts.append("[vo][bg]amix=inputs=2:duration=first:dropout_transition=2[a]")
        maps = ["-map", "[v]", "-map", "[a]"]
    filter_complex = ";".join(filter_parts)

    cmd = [
        ffmpeg_path(),
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        *maps,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        "-movflags",
        "+faststart",
        str(dest.resolve()),
    ]
    await _run(cmd, cwd=work_dir)
    if not dest.exists():
        raise RuntimeError("compose produced no mp4")
    return dest


async def _run(cmd: list[str], cwd: Path | None = None) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
    )
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(err.decode("utf-8", errors="ignore")[-1200:] or "ffmpeg failed")
