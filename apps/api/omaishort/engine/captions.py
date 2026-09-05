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


_BARE_WORD = re.compile(r"[^\wÀ-ỹ]+", re.I)
_PUNCT_SUFFIX = re.compile(r"([,.;:!?…]+[\"'»”’]*)\s*$")
_SENT_END = re.compile(r"[.!?…][\"'»”’]*$")
_CLAUSE_END = re.compile(r"[,;:][\"'»”’]*$")


def _bare_word(token: str) -> str:
    return _BARE_WORD.sub("", token or "").lower()


def _merge_punct(spoken: str, script: str) -> str:
    spoken = (spoken or "").strip()
    if not spoken:
        return (script or "").strip()
    if _PUNCT_SUFFIX.search(spoken):
        return spoken
    match = _PUNCT_SUFFIX.search(script or "")
    if match:
        return spoken + match.group(1)
    return spoken


def restore_script_punct(stamps: list[WordStamp], script: str) -> list[WordStamp]:
    """Copy , . ? ! from the spoken script onto TTS/Whisper tokens that dropped them."""
    tokens = [tok for tok in re.findall(r"\S+", script or "") if tok]
    if not stamps or not tokens:
        return stamps
    cursor = 0
    out: list[WordStamp] = []
    for stamp in stamps:
        bare = _bare_word(stamp.word)
        if not bare:
            out.append(stamp)
            continue
        found: int | None = None
        for look in range(cursor, min(cursor + 5, len(tokens))):
            other = _bare_word(tokens[look])
            if not other:
                continue
            if other == bare or other.startswith(bare) or bare.startswith(other):
                found = look
                break
        if found is None:
            out.append(stamp)
            continue
        out.append(
            WordStamp(word=_merge_punct(stamp.word, tokens[found]), start=stamp.start, end=stamp.end)
        )
        cursor = found + 1
    return out


def caption_groups(
    stamps: list[WordStamp],
    *,
    max_words: int = 5,
    max_chars: int = 34,
    pause_sec: float = 0.32,
) -> list[list[WordStamp]]:
    """Break karaoke lines on sentence stops, commas, and spoken pauses — not a fixed 6-word window."""
    groups: list[list[WordStamp]] = []
    current: list[WordStamp] = []

    def width(items: list[WordStamp]) -> int:
        return sum(len(item.word) for item in items) + max(0, len(items) - 1)

    def flush() -> None:
        nonlocal current
        if current:
            groups.append(current)
            current = []

    for stamp in stamps:
        if current:
            gap = stamp.start - current[-1].end
            overflow = len(current) >= max_words or width(current) + 1 + len(stamp.word) > max_chars
            if gap >= pause_sec or overflow:
                flush()
        current.append(stamp)
        if _SENT_END.search(stamp.word):
            flush()
        elif _CLAUSE_END.search(stamp.word) and (len(current) >= 3 or width(current) >= 16):
            flush()
    flush()
    merged: list[list[WordStamp]] = []
    for group in groups:
        if merged and len(group) == 1 and not _SENT_END.search(merged[-1][-1].word):
            if _SENT_END.search(group[0].word) or len(merged[-1]) < max_words:
                merged[-1] = merged[-1] + group
                continue
        merged.append(group)
    return merged


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
            return restore_script_punct(clamped, script), "edge-tts"
    stamps, src = transcribe_words(audio_path, script, duration, whisper_model)
    restored = restore_script_punct(clamp_word_stamps(stamps, duration) or even_split(script, duration), script)
    return restored, src


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
    for group in caption_groups(stamps):
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
        end = stamp.end
        if i + 1 < len(group):
            end = max(end, min(group[i + 1].start, stamp.end + 0.08))
        elif _SENT_END.search(stamp.word):
            end = stamp.end + 0.16
        events.append(
            f"Dialogue: 0,{_ass_time(stamp.start)},{_ass_time(end)},Default,,0,0,0,,{text}\n"
        )
    return events
