from __future__ import annotations

import asyncio
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
            if row["id"] == voice_id or row["edge"] == voice_id:
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


async def synthesize_speech(
    text: str, dest: Path, language: str = "en", voice_id: str | None = None
) -> TTSResult:
    edge_voice = resolve_edge_voice(language, voice_id)
    providers: list[TTSProvider] = []
    if ELEVENLABS_API_KEY and not voice_id:
        providers.append(ElevenLabsTTSProvider())
    providers.append(EdgeTTSProvider())
    for provider in providers:
        result = await provider.synthesize(text, dest, language, voice=edge_voice)
        if result is not None:
            return result
    raise RuntimeError("no TTS provider produced audio")


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
