"""Shot-by-shot video reverse-engineering engine (inspired by JuneYaooo/rea-video & ReelMimic).

Deconstructs a reference video into a reusable omaishort VideoBlueprint:
- Media probe (duration, resolution, FPS, aspect ratio, loudness)
- Shot boundary detection via FFmpeg scene-change filter
- Audio silence / speech rhythm analysis (+ optional local faster-whisper transcript)
- Per-shot keyframe forensics via Pillow (brightness, contrast, color palette, motion & camera cues)
- Optional multimodal VLM enrichment (REA_VLM_* / Gemini / OpenAI-compatible)
- Mapping onto omaishort's 5-beat contract (hook -> conflict -> rising_action -> twist -> ending)
- Open VIDEO.md blueprint + concise script_brief for generating new videos in the same style

Never copies raw footage or people from the reference video.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
from typing import Any

from PIL import Image, ImageChops, ImageStat

from omaishort import config
from omaishort.engine.fallback import BEAT_ORDER, infer_beat
from omaishort.engine.kenburns import (
    ffmpeg_info,
    ffmpeg_path,
    has_audio_stream,
    probe_duration,
    probe_mean_volume_db,
    probe_video_size,
)
from omaishort.engine.rescale import repair_scene_shots
from omaishort.providers.vision import analyze_keyframes_vlm
from omaishort_schema.models import (
    Camera,
    Motion,
    ReverseShot,
    Shot,
    StoryStructure,
    Storyboard,
    VideoBlueprint,
    is_editorial,
)

MAX_TEMPLATE_VIDEO_BYTES = 120 * 1024 * 1024
ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
_SAFE_SLUG = re.compile(r"[^A-Za-z0-9._-]+")
_SCENE_PTS = re.compile(r"pts_time:(\d+(?:\.\d+)?)")
_FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:fps|tbr)\b")
_SILENCE_DUR_RE = re.compile(r"silence_duration:\s*(\d+(?:\.\d+)?)")
_BEAT_WEIGHTS = (0.12, 0.20, 0.32, 0.22, 0.14)
_MAX_SHOTS = 18
_MIN_SHOT_SEC = 0.8
_MAX_UNINTERRUPTED_SHOT_SEC = 10.0


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_owner(owner_id: str | None) -> str:
    cleaned = _SAFE_SLUG.sub("_", (owner_id or "cli").strip()).strip("._")
    return cleaned[:64] or "cli"


def _safe_template_id(template_id: str) -> str:
    cleaned = _SAFE_SLUG.sub("", (template_id or "").strip())
    if not cleaned or ".." in cleaned or len(cleaned) < 4 or len(cleaned) > 64:
        raise ValueError("invalid template id")
    return cleaned


def templates_root(owner_id: str | None) -> Path:
    root = config.DATA_DIR / "templates" / _safe_owner(owner_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def template_dir(owner_id: str | None, template_id: str) -> Path:
    return templates_root(owner_id) / _safe_template_id(template_id)


def _aspect_label(width: int, height: int) -> str:
    if width <= 0 or height <= 0:
        return "9:16"
    ratio = width / height
    if abs(ratio - 9 / 16) < 0.08:
        return "9:16"
    if abs(ratio - 16 / 9) < 0.08:
        return "16:9"
    if abs(ratio - 1.0) < 0.08:
        return "1:1"
    if abs(ratio - 4 / 5) < 0.08:
        return "4:5"
    g = math.gcd(width, height)
    return f"{width // g}:{height // g}"


def probe_video_metadata(video_path: Path) -> dict[str, Any]:
    info = ffmpeg_info(video_path)
    duration = probe_duration(video_path)
    size = probe_video_size(video_path) or (1080, 1920)
    fps_match = _FPS_RE.search(info)
    fps = float(fps_match.group(1)) if fps_match else 30.0
    if fps <= 0 or fps > 240:
        fps = 30.0
    audio = has_audio_stream(video_path)
    mean_db = probe_mean_volume_db(video_path) if audio else None
    return {
        "duration_sec": round(max(0.0, duration), 2),
        "width": size[0],
        "height": size[1],
        "fps": round(fps, 2),
        "aspect_ratio": _aspect_label(size[0], size[1]),
        "has_audio": audio,
        "mean_volume_db": round(mean_db, 1) if mean_db is not None else None,
    }


def detect_shots(video_path: Path, duration: float, *, scene_threshold: float = 0.28) -> list[tuple[float, float]]:
    """Detect shot cut intervals via FFmpeg scene filter; clamp micro-cuts & split ultra-long takes."""
    total = max(0.5, float(duration or 0.5))
    cmd = [
        ffmpeg_path(),
        "-hide_banner",
        "-i",
        str(video_path),
        "-vf",
        f"select='gt(scene,{scene_threshold:.2f})',showinfo",
        "-an",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    blob = f"{res.stderr or ''}{res.stdout or ''}"
    raw_cuts = sorted({float(m.group(1)) for m in _SCENE_PTS.finditer(blob) if 0.2 < float(m.group(1)) < total - 0.2})

    # Merge tiny flash cuts (< _MIN_SHOT_SEC) into neighbors.
    points: list[float] = [0.0]
    for ts in raw_cuts:
        if ts - points[-1] >= _MIN_SHOT_SEC and total - ts >= _MIN_SHOT_SEC:
            points.append(round(ts, 2))
    points.append(round(total, 2))

    # Split uninterrupted takes longer than _MAX_UNINTERRUPTED_SHOT_SEC so pacing still maps to beats.
    intervals: list[tuple[float, float]] = []
    for start, end in zip(points[:-1], points[1:]):
        span = end - start
        if span <= 0.15:
            continue
        if span > _MAX_UNINTERRUPTED_SHOT_SEC:
            chunks = max(2, int(math.ceil(span / 6.0)))
            step = span / chunks
            for i in range(chunks):
                s = round(start + i * step, 2)
                e = round(end if i == chunks - 1 else start + (i + 1) * step, 2)
                if e > s:
                    intervals.append((s, e))
        else:
            intervals.append((round(start, 2), round(end, 2)))

    # If still only 1 shot and video >= 6s, split proportionally across the 5 beats.
    if len(intervals) <= 1 and total >= 6.0:
        intervals = []
        cursor = 0.0
        for idx, weight in enumerate(_BEAT_WEIGHTS):
            nxt = round(total if idx == len(_BEAT_WEIGHTS) - 1 else cursor + total * weight, 2)
            if nxt > cursor:
                intervals.append((round(cursor, 2), nxt))
                cursor = nxt

    # Cap excessive cut counts while preserving start/end rhythm.
    while len(intervals) > _MAX_SHOTS:
        # Merge the shortest adjacent pair.
        best_i = min(range(len(intervals) - 1), key=lambda i: (intervals[i + 1][1] - intervals[i][0]))
        merged = (intervals[best_i][0], intervals[best_i + 1][1])
        intervals = intervals[:best_i] + [merged] + intervals[best_i + 2 :]

    return intervals or [(0.0, round(total, 2))]


def detect_speech_ratio(video_path: Path, duration: float, has_audio: bool) -> float:
    if not has_audio or duration <= 0.2:
        return 0.0
    cmd = [
        ffmpeg_path(),
        "-hide_banner",
        "-i",
        str(video_path),
        "-af",
        "silencedetect=noise=-32dB:d=0.35",
        "-vn",
        "-f",
        "null",
        "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    blob = f"{res.stderr or ''}{res.stdout or ''}"
    silent_total = sum(float(m.group(1)) for m in _SILENCE_DUR_RE.finditer(blob))
    active = max(0.0, duration - silent_total)
    return round(min(1.0, active / max(0.1, duration)), 2)


def _extract_frame(video_path: Path, ts: float, dest: Path, *, max_width: int = 480) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_path(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, ts):.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale='min({max_width},iw)':-2",
        "-q:v",
        "4",
        str(dest),
    ]
    res = subprocess.run(cmd, capture_output=True, check=False)
    return res.returncode == 0 and dest.is_file() and dest.stat().st_size > 0


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _analyze_frame_image(mid_path: Path, prev_path: Path | None, next_path: Path | None) -> dict[str, Any]:
    with Image.open(mid_path) as raw:
        rgb = raw.convert("RGB")
        small = rgb.resize((96, 96), Image.Resampling.BILINEAR)
        gray = small.convert("L")
        stat = ImageStat.Stat(gray)
        brightness = round(stat.mean[0] / 255.0, 3)
        contrast = round(stat.stddev[0] / 128.0, 3)

        # Quantize to find top dominant colors & flat-color ratio (motion graphic / UI vs live footage).
        quant = small.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
        palette_raw = quant.getpalette() or []
        hist = quant.histogram()
        total_px = max(1, sum(hist[:8]))
        ranked = sorted(((hist[i], i) for i in range(min(8, len(hist))) if hist[i] > 0), reverse=True)
        dominant: list[str] = []
        for _count, idx in ranked[:4]:
            base = idx * 3
            if base + 2 < len(palette_raw):
                dominant.append(_rgb_to_hex((palette_raw[base], palette_raw[base + 1], palette_raw[base + 2])))
        top2_share = sum(count for count, _ in ranked[:2]) / total_px

        # Center vs border detail ratio hints at close-up vs wide framing.
        center = gray.crop((24, 24, 72, 72))
        center_std = ImageStat.Stat(center).stddev[0]
        full_std = max(1.0, stat.stddev[0])
        center_focus = center_std / full_std

        if top2_share >= 0.72 and contrast < 0.35:
            production_type = "motion_graphic"
        elif top2_share >= 0.68 and brightness > 0.72:
            production_type = "screen_recording"
        else:
            production_type = "live_action"

        if center_focus > 1.18:
            camera = Camera.close_up
        elif center_focus < 0.88:
            camera = Camera.wide
        else:
            camera = Camera.medium

        # Estimate motion from start vs end frame difference.
        motion = Motion.hold
        if prev_path and next_path and prev_path.is_file() and next_path.is_file():
            with Image.open(prev_path) as p_img, Image.open(next_path) as n_img:
                p_g = p_img.convert("L").resize((96, 96), Image.Resampling.BILINEAR)
                n_g = n_img.convert("L").resize((96, 96), Image.Resampling.BILINEAR)
                diff_mean = ImageStat.Stat(ImageChops.difference(p_g, n_g)).mean[0]
                if diff_mean >= 18.0:
                    # Compare horizontal shift vs zoom change.
                    shift_left = ImageStat.Stat(
                        ImageChops.difference(p_g.crop((8, 0, 96, 96)), n_g.crop((0, 0, 88, 96)))
                    ).mean[0]
                    shift_right = ImageStat.Stat(
                        ImageChops.difference(p_g.crop((0, 0, 88, 96)), n_g.crop((8, 0, 96, 96)))
                    ).mean[0]
                    if shift_left < diff_mean * 0.85 and shift_left < shift_right:
                        motion = Motion.pan_right
                    elif shift_right < diff_mean * 0.85:
                        motion = Motion.pan_left
                    else:
                        p_center = ImageStat.Stat(p_g.crop((20, 20, 76, 76))).stddev[0]
                        n_center = ImageStat.Stat(n_g.crop((20, 20, 76, 76))).stddev[0]
                        motion = Motion.zoom_in if n_center >= p_center else Motion.zoom_out
                elif diff_mean >= 8.0:
                    motion = Motion.zoom_in

    tone = "dark moody" if brightness < 0.35 else "bright airy" if brightness > 0.68 else "balanced contrast"
    summary = f"{production_type.replace('_', ' ')}, {camera.value} framing, {motion.value}, {tone} ({dominant[0] if dominant else '#222222'})"
    prompt_hint = f"{camera.value.replace('_', ' ')} shot, {motion.value.replace('_', ' ')}, {tone} lighting"
    return {
        "brightness": brightness,
        "contrast": contrast,
        "dominant_colors": dominant,
        "production_type": production_type,
        "camera": camera,
        "motion": motion,
        "visual_summary": summary,
        "prompt_hint": prompt_hint,
    }


def _beat_for_midpoint(mid: float, total: float) -> str:
    ratio = max(0.0, min(0.999, mid / max(0.1, total)))
    acc = 0.0
    for beat, weight in zip(BEAT_ORDER, _BEAT_WEIGHTS):
        acc += weight
        if ratio < acc:
            return beat
    return BEAT_ORDER[-1]


def _transcribe_reference(video_path: Path, has_audio: bool, enabled: bool) -> str:
    if not enabled or not has_audio:
        return ""
    try:
        from faster_whisper import WhisperModel

        with tempfile.TemporaryDirectory(prefix="omaishort-rev-aud-") as tmp:
            wav = Path(tmp) / "audio.wav"
            res = subprocess.run(
                [
                    ffmpeg_path(),
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(video_path),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    str(wav),
                ],
                capture_output=True,
                check=False,
            )
            if res.returncode != 0 or not wav.is_file():
                return ""
            model = WhisperModel(config.WHISPER_MODEL, device="cpu", compute_type="int8")
            segments, _info = model.transcribe(str(wav), beam_size=1)
            lines = [str(seg.text or "").strip() for seg in segments if str(seg.text or "").strip()]
            return " ".join(lines)[:4000]
    except Exception:
        return ""


def _coerce_camera(value: object, fallback: Camera) -> Camera:
    raw = str(value or "").strip().lower()
    if raw in Camera._value2member_map_:
        return Camera(raw)
    return fallback


def _coerce_motion(value: object, fallback: Motion) -> Motion:
    raw = str(value or "").strip().lower()
    if raw in Motion._value2member_map_:
        return Motion(raw)
    return fallback


def _compute_beat_durations(shots: list[ReverseShot], total_duration: float) -> dict[str, float]:
    buckets: dict[str, float] = {b: 0.0 for b in BEAT_ORDER}
    for shot in shots:
        key = shot.beat if shot.beat in buckets else "rising_action"
        buckets[key] += shot.duration_sec
    # Ensure every beat has a positive weight so 5-beat planning stays balanced.
    for idx, beat in enumerate(BEAT_ORDER):
        if buckets[beat] <= 0.2:
            buckets[beat] = round(max(1.0, total_duration * _BEAT_WEIGHTS[idx]), 2)
    s = sum(buckets.values()) or 1.0
    scale = max(1.0, total_duration) / s
    return {beat: round(buckets[beat] * scale, 2) for beat in BEAT_ORDER}


def _compute_beat_lenses(shots: list[ReverseShot]) -> dict[str, list[dict[str, str]]]:
    by_beat: dict[str, list[ReverseShot]] = {b: [] for b in BEAT_ORDER}
    for shot in shots:
        key = shot.beat if shot.beat in by_beat else "rising_action"
        by_beat[key].append(shot)
    lenses: dict[str, list[dict[str, str]]] = {}
    for beat in BEAT_ORDER:
        group = by_beat[beat]
        if not group:
            continue
        first = group[0]
        second = group[-1] if len(group) > 1 else first
        lenses[beat] = [
            {"camera": first.camera.value, "motion": first.motion.value},
            {"camera": second.camera.value, "motion": second.motion.value},
        ]
    return lenses


def _build_script_brief(
    *,
    name: str,
    duration: float,
    avg_shot: float,
    pacing: str,
    speech_ratio: float,
    hook_style: str,
    visual_style: str,
    beat_durations: dict[str, float],
    vlm_brief: str,
    language: str,
) -> str:
    if vlm_brief.strip():
        lead = vlm_brief.strip()
    elif str(language).lower().startswith("vi"):
        lead = (
            f"Theo nhịp mẫu '{name}' ({duration:.0f}s, cắt {pacing} ~{avg_shot:.1f}s/cảnh, mật độ thoại {int(speech_ratio * 100)}%). "
            f"Hook: {hook_style}. Hình ảnh: {visual_style}. "
            "Viết câu ngắn gọn, giàu hình ảnh, giữ đúng nhịp mở nhanh → đẩy cao trào → bẻ lái → kết đọng lại."
        )
    else:
        lead = (
            f"Follow reference blueprint '{name}' ({duration:.0f}s, {pacing} pacing ~{avg_shot:.1f}s/shot, speech density {int(speech_ratio * 100)}%). "
            f"Hook: {hook_style}. Visuals: {visual_style}. "
            "Keep sentences crisp, concrete, and rhythm-matched across hook -> conflict -> rising_action -> twist -> ending."
        )
    beat_line = (
        f"Beat timing target: hook {beat_durations.get('hook', 6):.1f}s, "
        f"conflict {beat_durations.get('conflict', 12):.1f}s, "
        f"rising {beat_durations.get('rising_action', 20):.1f}s, "
        f"twist {beat_durations.get('twist', 14):.1f}s, "
        f"ending {beat_durations.get('ending', 8):.1f}s."
    )
    return f"{lead}\n{beat_line}"[:1800]


def render_video_md(bp: VideoBlueprint) -> str:
    mix_str = ", ".join(f"{k}: {v:.0f}%" for k, v in bp.production_mix.items()) or "unknown"
    palette_str = ", ".join(bp.color_palette) if bp.color_palette else "n/a"
    lines = [
        f"# VIDEO.md — {bp.name}",
        "",
        f"- **Blueprint ID:** `{bp.id}`",
        f"- **Source:** `{bp.source_filename}`",
        f"- **Format:** `{bp.width}x{bp.height}` ({bp.aspect_ratio}) @ `{bp.fps} fps`, duration `{bp.duration_sec:.2f}s`",
        f"- **Pacing:** `{bp.pacing}` (`{len(bp.shots)}` shots, avg `{bp.avg_shot_sec:.2f}s`/shot)",
        f"- **Audio:** `{'yes' if bp.has_audio else 'no'}` (mean `{bp.mean_volume_db} dB`, speech ratio `{int(bp.speech_ratio * 100)}%`)",
        f"- **Production Mix:** {mix_str}",
        f"- **Color Palette:** {palette_str}",
        f"- **Analyzer:** `{bp.analyzer_provider}`",
        "",
        "## Style & Hook Formula",
        "",
        f"- **Hook:** {bp.hook_style}",
        f"- **Visual style:** {bp.visual_style}",
        "",
        "## 5-Beat Pacing Map",
        "",
        "| Beat | Duration (s) | Lens Pair |",
        "| --- | ---: | --- |",
    ]
    for beat in BEAT_ORDER:
        dur = bp.beat_durations.get(beat, 0.0)
        pair = bp.beat_lenses.get(beat) or []
        lens_txt = " → ".join(f"{p['camera']}+{p['motion']}" for p in pair) or "default"
        lines.append(f"| `{beat}` | {dur:.1f} | {lens_txt} |")

    lines += [
        "",
        "## Shot-by-Shot Breakdown",
        "",
        "| # | Time (s) | Dur (s) | Beat | Type | Camera / Motion | Visual Notes |",
        "| ---: | --- | ---: | --- | --- | --- | --- |",
    ]
    for s in bp.shots:
        notes = (s.visual_summary or s.prompt_hint or "").replace("|", "/")[:120]
        lines.append(
            f"| {s.index} | {s.t_start:.1f}–{s.t_end:.1f} | {s.duration_sec:.1f} | `{s.beat}` | "
            f"`{s.production_type}` | `{s.camera.value}` / `{s.motion.value}` | {notes} |"
        )

    lines += [
        "",
        "## Reusable Production Brief (`script_brief`)",
        "",
        "```text",
        bp.script_brief,
        "```",
    ]
    if bp.transcript.strip():
        lines += [
            "",
            "## Reference Transcript (structure study only)",
            "",
            bp.transcript.strip()[:2000],
        ]
    lines.append("")
    return "\n".join(lines)


async def reverse_engineer_video(
    video_path: Path,
    *,
    owner_id: str | None = None,
    name: str | None = None,
    source_filename: str | None = None,
    language: str = "vi",
    use_vlm: bool = True,
    transcribe: bool = False,
) -> VideoBlueprint:
    """Deconstruct a local reference video into a saved VideoBlueprint + VIDEO.md + shot keyframes."""
    if not video_path.is_file():
        raise FileNotFoundError(f"reference video not found: {video_path}")

    meta = await asyncio.to_thread(probe_video_metadata, video_path)
    duration = float(meta["duration_sec"])
    if duration <= 0.1:
        raise ValueError("Could not read valid video duration from file")
    if await asyncio.to_thread(probe_video_size, video_path) is None:
        raise ValueError("File does not contain a valid video stream")

    template_id = f"tpl_{secrets.token_hex(5)}"
    owner = _safe_owner(owner_id)
    tdir = template_dir(owner, template_id)
    fdir = tdir / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    rel_prefix = f"templates/{owner}/{template_id}/frames"

    intervals, speech_ratio = await asyncio.gather(
        asyncio.to_thread(detect_shots, video_path, duration),
        asyncio.to_thread(detect_speech_ratio, video_path, duration, bool(meta["has_audio"])),
    )

    def _extract_all() -> tuple[list[ReverseShot], list[tuple[int, Path]]]:
        extracted: list[ReverseShot] = []
        frame_pairs: list[tuple[int, Path]] = []
        with tempfile.TemporaryDirectory(prefix="omaishort-rev-tmp-") as tmp:
            tmp_dir = Path(tmp)
            for idx, (start, end) in enumerate(intervals, start=1):
                span = max(0.2, round(end - start, 2))
                mid = start + span * 0.5
                prev_t = start + span * 0.18
                next_t = start + span * 0.82
                mid_path = fdir / f"shot_{idx:02d}.jpg"
                prev_path = tmp_dir / f"p_{idx:02d}.jpg"
                next_path = tmp_dir / f"n_{idx:02d}.jpg"

                ok_mid = _extract_frame(video_path, mid, mid_path)
                if not ok_mid:
                    ok_mid = _extract_frame(video_path, start, mid_path)
                _extract_frame(video_path, prev_t, prev_path, max_width=240)
                _extract_frame(video_path, next_t, next_path, max_width=240)

                if ok_mid:
                    info = _analyze_frame_image(mid_path, prev_path, next_path)
                    frame_rel: str | None = f"{rel_prefix}/{mid_path.name}"
                    frame_pairs.append((idx, mid_path))
                else:
                    info = {
                        "brightness": 0.5,
                        "contrast": 0.2,
                        "dominant_colors": [],
                        "production_type": "unknown",
                        "camera": Camera.medium,
                        "motion": Motion.hold,
                        "visual_summary": "unreadable frame",
                        "prompt_hint": "medium shot, subtle motion",
                    }
                    frame_rel = None

                extracted.append(
                    ReverseShot(
                        index=idx,
                        t_start=round(start, 2),
                        t_end=round(end, 2),
                        duration_sec=span,
                        beat=_beat_for_midpoint(mid, duration),
                        production_type=info["production_type"],
                        camera=info["camera"],
                        motion=info["motion"],
                        brightness=info["brightness"],
                        contrast=info["contrast"],
                        dominant_colors=info["dominant_colors"],
                        visual_summary=info["visual_summary"],
                        prompt_hint=info["prompt_hint"],
                        frame_rel=frame_rel,
                    )
                )
        return extracted, frame_pairs

    shots, frame_pairs = await asyncio.to_thread(_extract_all)
    if not frame_pairs:
        shutil.rmtree(tdir, ignore_errors=True)
        raise ValueError("Could not extract any valid video frames from file")
    transcript = await asyncio.to_thread(_transcribe_reference, video_path, bool(meta["has_audio"]), transcribe)

    vlm_payload: dict[str, Any] | None = None
    analyzer_provider = "ffmpeg"
    if use_vlm and frame_pairs:
        table_lines = [
            f"#{s.index}: {s.t_start:.1f}-{s.t_end:.1f}s ({s.duration_sec:.1f}s), beat={s.beat}, "
            f"local_type={s.production_type}, cam={s.camera.value}, move={s.motion.value}"
            for s in shots
        ]
        vlm_payload, analyzer_provider = await analyze_keyframes_vlm(
            shot_table="\n".join(table_lines),
            frames=frame_pairs,
            transcript=transcript,
            language=language,
        )

    vlm_brief = ""
    hook_style = ""
    visual_style = ""
    if isinstance(vlm_payload, dict):
        hook_style = str(vlm_payload.get("hook_style") or "").strip()
        visual_style = str(vlm_payload.get("visual_style") or "").strip()
        vlm_brief = str(vlm_payload.get("template_brief") or "").strip()
        raw_shots = vlm_payload.get("shots")
        if isinstance(raw_shots, list):
            by_idx = {int(item.get("index")): item for item in raw_shots if isinstance(item, dict) and str(item.get("index", "")).isdigit()}
            for shot in shots:
                patch = by_idx.get(shot.index)
                if not patch:
                    continue
                ptype = str(patch.get("production_type") or "").strip().lower()
                if ptype:
                    shot.production_type = ptype
                shot.camera = _coerce_camera(patch.get("camera"), shot.camera)
                shot.motion = _coerce_motion(patch.get("motion"), shot.motion)
                if str(patch.get("visual_summary") or "").strip():
                    shot.visual_summary = str(patch["visual_summary"]).strip()[:240]
                if str(patch.get("prompt_hint") or "").strip():
                    shot.prompt_hint = str(patch["prompt_hint"]).strip()[:240]

    avg_shot = round(sum(s.duration_sec for s in shots) / max(1, len(shots)), 2)
    pacing = "fast" if avg_shot < 2.8 else "slow" if avg_shot > 5.5 else "medium"

    # Production mix percentages weighted by shot duration.
    mix_dur: dict[str, float] = {}
    for s in shots:
        mix_dur[s.production_type] = mix_dur.get(s.production_type, 0.0) + s.duration_sec
    total_shot_dur = sum(mix_dur.values()) or 1.0
    production_mix = {k: round((v / total_shot_dur) * 100.0, 1) for k, v in sorted(mix_dur.items(), key=lambda x: -x[1])}

    # Global color palette across shots.
    color_counts = Counter(c for s in shots for c in s.dominant_colors)
    color_palette = [c for c, _ in color_counts.most_common(5)]

    avg_bright = sum(s.brightness for s in shots) / max(1, len(shots))
    avg_contrast = sum(s.contrast for s in shots) / max(1, len(shots))
    if not hook_style:
        first_shot = shots[0]
        hook_style = (
            f"Fast {first_shot.duration_sec:.1f}s opening ({first_shot.camera.value}/{first_shot.motion.value}) "
            f"with {'punchy speech lead' if speech_ratio >= 0.6 else 'visual tension lead'}"
        )
    if not visual_style:
        tone = "dark high-contrast" if avg_bright < 0.38 else "bright clean" if avg_bright > 0.65 else "cinematic balanced"
        lead_type = next(iter(production_mix.keys()), "live_action").replace("_", " ")
        visual_style = f"{lead_type}, {tone} grade (contrast {avg_contrast:.2f}), palette {', '.join(color_palette[:3]) or 'neutral'}"

    beat_durations = _compute_beat_durations(shots, duration)
    beat_lenses = _compute_beat_lenses(shots)
    clean_filename = (source_filename or video_path.name).strip() or "reference.mp4"
    clean_name = (name or Path(clean_filename).stem).strip()[:80] or template_id

    script_brief = _build_script_brief(
        name=clean_name,
        duration=duration,
        avg_shot=avg_shot,
        pacing=pacing,
        speech_ratio=speech_ratio,
        hook_style=hook_style,
        visual_style=visual_style,
        beat_durations=beat_durations,
        vlm_brief=vlm_brief,
        language=language,
    )

    blueprint = VideoBlueprint(
        id=template_id,
        name=clean_name,
        source_filename=clean_filename,
        created_at=_now_iso(),
        duration_sec=duration,
        width=int(meta["width"]),
        height=int(meta["height"]),
        fps=float(meta["fps"]),
        aspect_ratio=str(meta["aspect_ratio"]),
        has_audio=bool(meta["has_audio"]),
        mean_volume_db=meta["mean_volume_db"],
        speech_ratio=speech_ratio,
        avg_shot_sec=avg_shot,
        pacing=pacing,
        production_mix=production_mix,
        hook_style=hook_style,
        visual_style=visual_style,
        color_palette=color_palette,
        transcript=transcript,
        beat_durations=beat_durations,
        beat_lenses=beat_lenses,
        shots=shots,
        script_brief=script_brief,
        video_md="",
        analyzer_provider=analyzer_provider,
    )
    blueprint.video_md = render_video_md(blueprint)
    save_blueprint(owner, blueprint)
    return blueprint


def save_blueprint(owner_id: str | None, blueprint: VideoBlueprint) -> Path:
    tdir = template_dir(owner_id, blueprint.id)
    tdir.mkdir(parents=True, exist_ok=True)
    json_path = tdir / "blueprint.json"
    md_path = tdir / "VIDEO.md"
    json_path.write_text(blueprint.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(blueprint.video_md or render_video_md(blueprint), encoding="utf-8")
    return json_path


def load_blueprint(owner_id: str | None, template_id: str) -> VideoBlueprint | None:
    try:
        tid = _safe_template_id(template_id)
    except ValueError:
        return None
    candidates = [_safe_owner(owner_id)]
    if "cli" not in candidates:
        candidates.append("cli")
    for owner in candidates:
        path = config.DATA_DIR / "templates" / owner / tid / "blueprint.json"
        if path.is_file():
            try:
                return VideoBlueprint.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                return None
    from omaishort import cloud_client

    if cloud_client.cloud_mode_enabled():
        try:
            remote = cloud_client.templates_get(tid)
            if remote:
                return VideoBlueprint.model_validate(remote)
        except Exception:
            return None
    return None


def list_blueprints(owner_id: str | None, limit: int = 30) -> list[VideoBlueprint]:
    root = templates_root(owner_id)
    items: list[VideoBlueprint] = []
    for sub in root.iterdir():
        if not sub.is_dir():
            continue
        bp_file = sub / "blueprint.json"
        if not bp_file.is_file():
            continue
        try:
            items.append(VideoBlueprint.model_validate_json(bp_file.read_text(encoding="utf-8")))
        except Exception:
            continue
    items.sort(key=lambda item: item.created_at or "", reverse=True)
    return items[:limit]


def delete_blueprint(owner_id: str | None, template_id: str) -> bool:
    try:
        tdir = template_dir(owner_id, template_id)
    except ValueError:
        return False
    if not tdir.is_dir():
        return False
    shutil.rmtree(tdir, ignore_errors=True)
    return True


def merge_template_brief(existing: str | None, blueprint: VideoBlueprint) -> str:
    base = (existing or "").strip()
    tpl = (blueprint.script_brief or "").strip()
    if not tpl:
        return base[:2000]
    if not base:
        return tpl[:2000]
    if tpl[:60].lower() in base.lower():
        return base[:2000]
    return f"{base}\n\n[Reference Blueprint: {blueprint.name}]\n{tpl}"[:2000]


def apply_blueprint_to_structure(
    structure: StoryStructure,
    blueprint: VideoBlueprint,
    target_seconds: float,
) -> StoryStructure:
    """Scale the reference video's 5-beat pacing proportions onto StoryStructure."""
    durs = blueprint.beat_durations
    if not durs:
        return structure
    raw = [max(1.0, float(durs.get(b) or 4.0)) for b in BEAT_ORDER]
    total = sum(raw) or 1.0
    scale = max(15.0, float(target_seconds or 60.0)) / total
    scaled = [round(v * scale, 2) for v in raw]
    return structure.model_copy(
        update={
            "hook_sec": scaled[0],
            "conflict_sec": scaled[1],
            "rising_sec": scaled[2],
            "twist_sec": scaled[3],
            "ending_sec": scaled[4],
        }
    )


def apply_blueprint_to_storyboard(board: Storyboard, blueprint: VideoBlueprint) -> Storyboard:
    """Apply reverse-engineered beat lenses & visual tone onto Storyboard.

    Respects omaishort invariants:
    - One still_id per scene; every shot in a scene shares that still_id.
    - Editorial (news/knowledge) NEVER receives close_up punch-ins.
    """
    editorial = is_editorial(board.kind)
    total = max(1, len(board.scenes))
    style_hint = (blueprint.visual_style or "").strip()[:120]
    for idx, scene in enumerate(board.scenes):
        beat = infer_beat(scene, idx, total)
        pair = blueprint.beat_lenses.get(beat)
        if pair and len(pair) >= 2:
            c1 = _coerce_camera(pair[0].get("camera"), Camera.medium)
            m1 = _coerce_motion(pair[0].get("motion"), Motion.zoom_in)
            c2 = _coerce_camera(pair[1].get("camera"), Camera.medium)
            m2 = _coerce_motion(pair[1].get("motion"), Motion.zoom_in)
            if editorial:
                if c1 == Camera.close_up:
                    c1 = Camera.medium
                if c2 == Camera.close_up:
                    c2 = Camera.medium
            dur = max(0.4, float(scene.duration_sec))
            split = round(dur * 0.55, 2)
            if split <= 0.1 or split >= dur - 0.1:
                split = round(dur / 2, 2)
            scene.shots = [
                Shot(camera=c1, motion=m1, t_start=0.0, t_end=split, still_id=scene.still_id),
                Shot(camera=c2, motion=m2, t_start=split, t_end=dur, still_id=scene.still_id),
            ]
            repair_scene_shots(scene)
        if style_hint and style_hint.lower() not in (scene.lighting or "").lower():
            scene.lighting = f"{scene.lighting}; {style_hint}".strip("; ") if scene.lighting else style_hint
    return board
