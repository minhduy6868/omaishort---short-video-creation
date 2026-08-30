from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WordStamp:
    word: str
    start: float
    end: float


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


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:d}:{m:02d}:{s:05.2f}"


def words_to_ass(stamps: list[WordStamp], dest: Path, play_res: tuple[int, int] = (1080, 1920)) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    header = f"""[Script Info]
Title: omaishort
ScriptType: v4.00+
PlayResX: {play_res[0]}
PlayResY: {play_res[1]}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,5,0,2,50,50,120,1
Style: Active,Arial,64,&H0000E0FF,&H000000FF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,5,0,2,50,50,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # Karaoke-lite: current word highlighted by overlapping events in groups of 6
    lines = [header]
    group: list[WordStamp] = []
    for stamp in stamps:
        group.append(stamp)
        if len(group) >= 6:
            lines.extend(_group_events(group))
            group = []
    if group:
        lines.extend(_group_events(group))
    dest.write_text("".join(lines), encoding="utf-8")
    return dest


def _group_events(group: list[WordStamp]) -> list[str]:
    events = []
    for i, stamp in enumerate(group):
        rendered = []
        for j, word in enumerate(group):
            token = word.word.replace("{", "").replace("}", "")
            if j == i:
                rendered.append(r"{\c&H00E0FF&}" + token + r"{\c&HFFFFFF&}")
            else:
                rendered.append(token)
        text = " ".join(rendered)
        events.append(
            f"Dialogue: 0,{_ass_time(stamp.start)},{_ass_time(stamp.end)},Default,,0,0,0,,{text}\n"
        )
    return events
