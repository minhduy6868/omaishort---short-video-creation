from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

import httpx

from omaishort.config import ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID


class TTSProvider(Protocol):
    name: str

    async def synthesize(self, text: str, dest: Path, language: str = "en") -> Path | None:
        ...


EDGE_VOICES = {
    "en": "en-US-JennyNeural",
    "vi": "vi-VN-HoaiMyNeural",
}


class EdgeTTSProvider:
    name = "edge-tts"

    async def synthesize(self, text: str, dest: Path, language: str = "en") -> Path | None:
        try:
            import edge_tts
        except ImportError:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        voice = EDGE_VOICES.get(language[:2], EDGE_VOICES["en"])
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(str(dest))
            if dest.exists() and dest.stat().st_size > 0:
                return dest
        except Exception:
            return None
        return None


class ElevenLabsTTSProvider:
    name = "elevenlabs"

    async def synthesize(self, text: str, dest: Path, language: str = "en") -> Path | None:
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
                return dest
        except Exception:
            return None


async def synthesize_speech(text: str, dest: Path, language: str = "en") -> tuple[Path, str]:
    providers: list[TTSProvider] = []
    if ELEVENLABS_API_KEY:
        providers.append(ElevenLabsTTSProvider())
    providers.append(EdgeTTSProvider())
    for provider in providers:
        result = await provider.synthesize(text, dest, language)
        if result is not None:
            return result, provider.name
    raise RuntimeError("no TTS provider produced audio")


def probe_duration(path: Path) -> float:
    import re
    import subprocess

    from omaishort.engine.kenburns import ffmpeg_path

    cmd = [ffmpeg_path(), "-i", str(path)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", result.stderr or "")
    if not match:
        return 0.0
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


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
