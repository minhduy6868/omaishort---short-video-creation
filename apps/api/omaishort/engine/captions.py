from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from omaishort_schema.models import SubtitleStyle

EDGE_TICKS_PER_SECOND = 10_000_000.0


@dataclass
class WordStamp:
    word: str
    start: float
    end: float


def edge_ticks_to_seconds(ticks: float | int) -> float:
    return float(ticks) / EDGE_TICKS_PER_SECOND


def hex_to_ass(hex_color: str, *, override: bool = False) -> str:
    raw = (hex_color or "").strip().lstrip("#")
    if len(raw) == 8:
        alpha, raw = raw[:2], raw[2:]
    else:
        alpha = "00"
    if len(raw) != 6 or any(c not in "0123456789abcdefABCDEF" for c in raw + alpha):
        return "&HFFFFFF&" if override else "&H00FFFFFF"
    blue, green, red = raw[4:6], raw[2:4], raw[0:2]
    body = f"{blue}{green}{red}".upper()
    if override:
        return f"&H{body}&"
    return f"&H{alpha.upper()}{body}"


def _clean_words(text: str) -> list[str]:
    return [w for w in re.findall(r"\S+", text) if w]


def even_split(text: str, duration: float) -> list[WordStamp]:
    words = _clean_words(text)
    if not words:
        return []
    slot = duration / len(words)
    stamps = []
    t = 0.0
    for word in words:
        stamps.append(WordStamp(word=word, start=t, end=t + slot))
        t += slot
    return stamps


def transcribe_words(audio_path: Path, script: str, duration: float, model_name: str) -> tuple[list[WordStamp], str]:
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _info = model.transcribe(str(audio_path), word_timestamps=True)
        stamps: list[WordStamp] = []
        for segment in segments:
            for word in segment.words or []:
                token = (word.word or "").strip()
                if token:
                    stamps.append(WordStamp(word=token, start=float(word.start), end=float(word.end)))
        if stamps:
            return stamps, "faster-whisper"
    except Exception:
        pass
    return even_split(script, duration), "even-split"


def clamp_word_stamps(stamps: list[WordStamp], duration: float) -> list[WordStamp]:
    if duration <= 0:
        return stamps
    out: list[WordStamp] = []
    for stamp in stamps:
        start = max(0.0, min(float(stamp.start), duration))
        end = max(start + 0.04, min(float(stamp.end), duration))
        if start < duration - 0.02:
            out.append(WordStamp(word=stamp.word, start=start, end=end))
    return out


def resolve_word_stamps(
    *,
    edge_words: list[WordStamp] | None,
    audio_path: Path,
    script: str,
    duration: float,
    whisper_model: str,
) -> tuple[list[WordStamp], str]:
    if edge_words:
        clamped = clamp_word_stamps(edge_words, duration)
        if clamped:
            return clamped, "edge-tts"
    stamps, src = transcribe_words(audio_path, script, duration, whisper_model)
    return clamp_word_stamps(stamps, duration) or even_split(script, duration), src


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def words_to_ass(
    stamps: list[WordStamp],
    dest: Path,
    play_res: tuple[int, int] = (1080, 1920),
    style: SubtitleStyle | None = None,
) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    style = style or SubtitleStyle()
    font = (style.font or "Arial").replace(",", " ")
    primary = hex_to_ass(style.primary_hex)
    highlight = hex_to_ass(style.highlight_hex)
    outline = hex_to_ass(style.outline_hex)
    primary_ov = hex_to_ass(style.primary_hex, override=True)
    highlight_ov = hex_to_ass(style.highlight_hex, override=True)
    header = f"""[Script Info]
Title: omaishort
ScriptType: v4.00+
PlayResX: {play_res[0]}
PlayResY: {play_res[1]}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{style.font_size},{primary},&H000000FF,{outline},&H80000000,-1,0,0,0,100,100,0,0,1,{style.outline},0,2,50,50,{style.margin_v},1
Style: Active,{font},{style.font_size},{highlight},&H000000FF,{outline},&H80000000,-1,0,0,0,100,100,0,0,1,{style.outline},0,2,50,50,{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    group: list[WordStamp] = []
    for stamp in stamps:
        group.append(stamp)
        if len(group) >= 6:
            lines.extend(_group_events(group, primary_ov, highlight_ov))
            group = []
    if group:
        lines.extend(_group_events(group, primary_ov, highlight_ov))
    dest.write_text("".join(lines), encoding="utf-8")
    return dest


def _group_events(group: list[WordStamp], primary_ov: str, highlight_ov: str) -> list[str]:
    events = []
    for i, stamp in enumerate(group):
        rendered = []
        for j, word in enumerate(group):
            token = word.word.replace("{", "").replace("}", "")
            if j == i:
                rendered.append(r"{\c" + highlight_ov + "}" + token + r"{\c" + primary_ov + "}")
            else:
                rendered.append(token)
        text = " ".join(rendered)
        events.append(
            f"Dialogue: 0,{_ass_time(stamp.start)},{_ass_time(stamp.end)},Default,,0,0,0,,{text}\n"
        )
    return events
