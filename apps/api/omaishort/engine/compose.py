from __future__ import annotations

import asyncio
import json
from pathlib import Path

from omaishort.config import (
    ASSETS_DIR,
    HF_I2V_ENABLED,
    HF_TOKEN,
    POLLINATIONS_KEY,
    POLLINATIONS_VIDEO_ENABLED,
    WAVESPEED_API_KEY,
    WAVESPEED_ENABLED,
)
from omaishort.engine.fallback import apply_beat_lenses
from omaishort.engine.kenburns import conform_clip, ffmpeg_path, render_shot_clip
from omaishort.engine.motion_prompt import motion_prompt
from omaishort.providers.video import generate_clip
from omaishort_schema.models import MixSettings, Storyboard, is_editorial

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac"}


def i2v_ready() -> bool:
    if POLLINATIONS_VIDEO_ENABLED and POLLINATIONS_KEY:
        return True
    if HF_I2V_ENABLED and HF_TOKEN:
        return True
    if WAVESPEED_ENABLED and WAVESPEED_API_KEY:
        return True
    return False


def i2v_wanted(board: Storyboard) -> bool:
    """Drama may I2V. News/knowledge are still collages (Ken Burns only)."""
    return i2v_ready() and not is_editorial(board.kind)


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def pick_bgm() -> Path | None:
    folder = ASSETS_DIR / "music"
    if not folder.is_dir():
        return None
    files = sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS and p.stem.lower() != "readme"
    )
    return files[0] if files else None


def pick_logo(mix: MixSettings) -> Path | None:
    if not mix.logo_enabled:
        return None
    if mix.logo_path:
        path = Path(mix.logo_path)
        if path.is_file():
            return path
    folder = ASSETS_DIR / "logo"
    if not folder.is_dir():
        return None
    files = sorted(
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS and p.stem.lower() != "readme"
    )
    return files[0] if files else None


async def compose_short(
    board: Storyboard,
    stills: dict[str, Path],
    audio_path: Path,
    ass_path: Path,
    dest: Path,
    work_dir: Path,
    mix: MixSettings | None = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    work_dir = work_dir.resolve()
    dest = dest.resolve()
    apply_beat_lenses(board)
    clips_dir = work_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    clip_paths: list[Path] = []
    i2v_ids: list[str] = []
    n = 0
    want_i2v = i2v_wanted(board)
    for scene in board.scenes:
        still = stills[scene.still_id]
        i2v_used = False
        if want_i2v:
            raw = work_dir / "i2v" / f"{scene.still_id}.mp4"
            generated = await generate_clip(motion_prompt(scene), raw, still, duration=min(5.0, scene.duration_sec))
            if generated is not None:
                n += 1
                clip = clips_dir / f"clip_{n:03d}.mp4"
                await conform_clip(generated[0], clip, scene.duration_sec)
                clip_paths.append(clip)
                i2v_ids.append(scene.still_id)
                i2v_used = True
        if not i2v_used:
            for shot in scene.shots:
                n += 1
                clip = clips_dir / f"clip_{n:03d}.mp4"
                await render_shot_clip(still, shot, clip)
                clip_paths.append(clip)
    if not i2v_ids:
        mode = "kenburns"
    elif len(i2v_ids) == len(board.scenes):
        mode = "i2v"
    else:
        mode = "mixed"
    (work_dir / "motion.json").write_text(
        json.dumps({"mode": mode, "i2v_still_ids": i2v_ids}, indent=2),
        encoding="utf-8",
    )
    concat_file = work_dir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for p in clip_paths),
        encoding="utf-8",
    )
    silent = work_dir / "video_silent.mp4"
    try:
        await _concat(concat_file, silent, work_dir, copy=True)
    except RuntimeError:
        await _concat(concat_file, silent, work_dir, copy=False)

    mix = mix or MixSettings()
    bgm = pick_bgm() if mix.bgm_enabled else None
    logo = pick_logo(mix)
    local_ass = work_dir / "captions.ass"
    if ass_path.resolve() != local_ass.resolve():
        local_ass.write_bytes(ass_path.read_bytes())

    attempts: list[tuple[Path | None, bool, bool, Path | None]] = []
    if bgm is not None and mix.duck:
        attempts.append((bgm, True, True, logo))
    if bgm is not None:
        attempts.append((bgm, False, True, logo))
    attempts.append((None, False, True, logo))
    attempts.append((None, False, True, None))
    attempts.append((None, False, False, None))

    last_error = RuntimeError("compose mux failed")
    for mix_bgm, duck, subtitles, mix_logo in attempts:
        try:
            dest.unlink(missing_ok=True)
            await _mux(
                silent,
                audio_path,
                local_ass,
                dest,
                work_dir,
                mix_bgm,
                mix,
                duck=duck,
                subtitles=subtitles,
                logo=mix_logo,
            )
            if dest.exists() and dest.stat().st_size > 0:
                return dest
        except RuntimeError as exc:
            last_error = exc
    raise last_error


async def _concat(concat_file: Path, dest: Path, work_dir: Path, *, copy: bool) -> None:
    cmd = [
        ffmpeg_path(),
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file.name,
    ]
    if copy:
        cmd += ["-c", "copy"]
    else:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", "-preset", "veryfast"]
    cmd.append(str(dest))
    await _run(cmd, cwd=work_dir)


async def _mux(
    silent: Path,
    audio_path: Path,
    local_ass: Path,
    dest: Path,
    work_dir: Path,
    bgm: Path | None,
    mix: MixSettings,
    *,
    duck: bool,
    subtitles: bool,
    logo: Path | None = None,
) -> None:
    filter_parts: list[str] = []
    inputs = ["-i", silent.name, "-i", str(audio_path.resolve())]
    next_idx = 2
    v_src = "0:v"
    if logo is not None:
        inputs += ["-i", str(logo.resolve())]
        margin = max(8, min(200, mix.logo_margin))
        filter_parts.append(f"[{next_idx}:v]scale=160:-1[lg]")
        filter_parts.append(f"[{v_src}][lg]overlay=W-w-{margin}:{margin}[vlogo]")
        v_src = "[vlogo]"
        next_idx += 1
    if subtitles:
        src = v_src if v_src.startswith("[") else f"[{v_src}]"
        filter_parts.append(f"{src}subtitles={local_ass.name}[v]")
        vmap = "[v]"
    else:
        vmap = v_src if v_src.startswith("[") else "0:v"
    maps = ["-map", vmap, "-map", "1:a:0"]
    if bgm is not None:
        inputs += ["-stream_loop", "-1", "-i", str(bgm.resolve())]
        vol = max(0.0, min(1.0, mix.bgm_volume))
        filter_parts.append("[1:a]aformat=sample_fmts=fltp:channel_layouts=stereo,volume=1.0[vo]")
        filter_parts.append(f"[{next_idx}:a]aformat=sample_fmts=fltp:channel_layouts=stereo,volume={vol:.3f}[bg]")
        if duck:
            filter_parts.append(
                "[bg][vo]sidechaincompress=threshold=0.05:ratio=8:attack=150:release=600:makeup=1[ducked]"
            )
            filter_parts.append("[vo][ducked]amix=inputs=2:duration=first:dropout_transition=2[a]")
        else:
            filter_parts.append("[vo][bg]amix=inputs=2:duration=first:dropout_transition=2[a]")
        maps = ["-map", vmap, "-map", "[a]"]
    cmd = [
        ffmpeg_path(),
        "-y",
        *inputs,
    ]
    if filter_parts:
        cmd += ["-filter_complex", ";".join(filter_parts)]
    cmd += [
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
