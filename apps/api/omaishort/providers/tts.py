from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from omaishort.config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID
from omaishort.engine.captions import WordStamp, edge_ticks_to_seconds
from omaishort.engine.kenburns import probe_duration as probe_duration


class TTSProvider(Protocol):
    name: str

    async def synthesize(
        self, text: str, dest: Path, language: str = "en", voice: str | None = None
    ) -> TTSResult | None:
        ...


@dataclass
class TTSResult:
    path: Path
    provider: str
    words: list[WordStamp] | None = None


EDGE_VOICES = {
    "en": "en-US-JennyNeural",
    "vi": "vi-VN-HoaiMyNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
}

# Curated edge-tts voices. Microsoft has hundreds; we expose nam/nữ + a few locales.
VOICE_CATALOG: list[dict[str, str]] = [
    {"id": "vi-female", "language": "vi", "gender": "female", "region": "VN", "edge": "vi-VN-HoaiMyNeural", "label": "Nữ — Việt Nam"},
    {"id": "vi-male", "language": "vi", "gender": "male", "region": "VN", "edge": "vi-VN-NamMinhNeural", "label": "Nam — Việt Nam"},
    {"id": "en-female-us", "language": "en", "gender": "female", "region": "US", "edge": "en-US-JennyNeural", "label": "Female — US"},
    {"id": "en-male-us", "language": "en", "gender": "male", "region": "US", "edge": "en-US-GuyNeural", "label": "Male — US"},
    {"id": "en-female-uk", "language": "en", "gender": "female", "region": "UK", "edge": "en-GB-SoniaNeural", "label": "Female — UK"},
    {"id": "en-male-uk", "language": "en", "gender": "male", "region": "UK", "edge": "en-GB-RyanNeural", "label": "Male — UK"},
    {"id": "en-female-au", "language": "en", "gender": "female", "region": "AU", "edge": "en-AU-NatashaNeural", "label": "Female — Australia"},
    {"id": "en-male-au", "language": "en", "gender": "male", "region": "AU", "edge": "en-AU-WilliamNeural", "label": "Male — Australia"},
]


def list_voices(language: str | None = None) -> list[dict[str, str]]:
    lang = (language or "").strip().lower()[:2]
    if not lang:
        return list(VOICE_CATALOG)
    return [row for row in VOICE_CATALOG if row["language"] == lang]


def resolve_edge_voice(language: str = "en", voice_id: str | None = None) -> str:
    if voice_id:
        for row in VOICE_CATALOG:
            if row["id"] == voice_id:
                return row["edge"]
        for row in VOICE_CATALOG:
            if row["edge"] == voice_id:
                return row["edge"]
    return EDGE_VOICES.get((language or "en")[:2], EDGE_VOICES["en"])


class EdgeTTSProvider:
    name = "edge-tts"

    async def synthesize(
        self, text: str, dest: Path, language: str = "en", voice: str | None = None
    ) -> TTSResult | None:
        try:
            import edge_tts
        except ImportError:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        voice = voice or EDGE_VOICES.get(language[:2], EDGE_VOICES["en"])
        words: list[WordStamp] = []
        try:
            communicate = edge_tts.Communicate(text, voice, boundary="WordBoundary")
            audio = bytearray()
            async for chunk in communicate.stream():
                kind = chunk.get("type")
                if kind == "audio":
                    audio.extend(chunk["data"])
                elif kind == "WordBoundary":
                    start = edge_ticks_to_seconds(chunk["offset"])
                    end = start + edge_ticks_to_seconds(chunk["duration"])
                    token = (chunk.get("text") or "").strip()
                    if token:
                        words.append(WordStamp(word=token, start=start, end=end))
            if audio:
                dest.write_bytes(bytes(audio))
                if dest.exists() and dest.stat().st_size > 0:
                    return TTSResult(path=dest, provider=self.name, words=words or None)
        except Exception:
            words = []
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(dest))
            if dest.exists() and dest.stat().st_size > 0:
                return TTSResult(path=dest, provider=self.name, words=None)
        except Exception:
            return None
        return None


class ElevenLabsTTSProvider:
    name = "elevenlabs"

    async def synthesize(
        self, text: str, dest: Path, language: str = "en", voice: str | None = None
    ) -> TTSResult | None:
        if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.7},
        }
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                dest.write_bytes(response.content)
                return TTSResult(path=dest, provider=self.name, words=None)
        except Exception:
            return None


def join_scene_narration(lines: list[str]) -> str:
    """Stage [5]: join scene VO with sentence stops so edge-tts pauses between scenes."""
    parts: list[str] = []
    for raw in lines:
        text = (raw or "").strip()
        if not text:
            continue
        if not re.search(r"[.!?…][\"'»”’]*$", text):
            text = text.rstrip() + "."
        parts.append(text)
    return " ".join(parts)


def split_tts_chunks(text: str, limit: int = 900) -> list[str]:
    """Edge-tts often fails on a long ChatGPT script; speak in sentence packs."""
    blob = re.sub(r"\s+", " ", (text or "").strip())
    if not blob:
        return []
    if len(blob) <= limit:
        return [blob]
    sentences = re.split(r"(?<=[.!?…])\s+", blob)
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        piece = sent.strip()
        if not piece:
            continue
        if current and len(current) + 1 + len(piece) > limit:
            chunks.append(current)
            current = piece
        else:
            current = f"{current} {piece}".strip() if current else piece
    if current:
        chunks.append(current)
    return chunks or [blob[:limit]]


async def _concat_mp3(parts: list[Path], dest: Path) -> Path:
    from omaishort.engine.kenburns import ffmpeg_path

    dest.parent.mkdir(parents=True, exist_ok=True)
    listing = dest.parent / f"{dest.stem}.concat.txt"
    listing.write_text(
        "".join(f"file '{p.resolve().as_posix()}'\n" for p in parts),
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
        *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()
    if proc.returncode != 0 or not dest.exists() or dest.stat().st_size <= 0:
        raise RuntimeError("failed to concat TTS chunks")
    return dest


async def synthesize_speech(
    text: str, dest: Path, language: str = "en", voice_id: str | None = None
) -> TTSResult:
    edge_voice = resolve_edge_voice(language, voice_id)
    providers: list[TTSProvider] = []
    if ELEVENLABS_API_KEY and not voice_id:
        providers.append(ElevenLabsTTSProvider())
    providers.append(EdgeTTSProvider())
    chunks = split_tts_chunks(text)
    if len(chunks) <= 1:
        for provider in providers:
            result = await provider.synthesize(text, dest, language, voice=edge_voice)
            if result is not None:
                return result
        raise RuntimeError("no TTS provider produced audio")
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error = RuntimeError("no TTS provider produced audio")
    for provider in providers:
        parts: list[Path] = []
        words: list[WordStamp] = []
        offset = 0.0
        try:
            for i, chunk in enumerate(chunks):
                part = dest.parent / f"{dest.stem}.part{i:02d}.mp3"
                result = None
                for attempt in range(3):
                    result = await provider.synthesize(chunk, part, language, voice=edge_voice)
                    if result is not None and part.exists() and part.stat().st_size > 0:
                        break
                    await asyncio.sleep(1.5 * (attempt + 1))
                if result is None or not part.exists() or part.stat().st_size <= 0:
                    raise RuntimeError(f"{provider.name} failed chunk {i}")
                if result.words:
                    for stamp in result.words:
                        words.append(
                            WordStamp(word=stamp.word, start=stamp.start + offset, end=stamp.end + offset)
                        )
                offset += probe_duration(part) or 0.0
                parts.append(part)
            await _concat_mp3(parts, dest)
            if dest.exists() and dest.stat().st_size > 0:
                return TTSResult(path=dest, provider=provider.name, words=words or None)
        except Exception as exc:
            last_error = exc
            continue
    raise last_error


async def silence_audio(dest: Path, seconds: float) -> Path:
    from omaishort.engine.kenburns import ffmpeg_path

    dest = dest.with_suffix(".wav")
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_path(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=44100:cl=stereo",
        "-t",
        f"{seconds:.3f}",
        str(dest),
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
    await proc.wait()
    if proc.returncode != 0 or not dest.exists():
        raise RuntimeError("failed to write silence audio")
    return dest
