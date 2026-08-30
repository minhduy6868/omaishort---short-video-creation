from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_BASE_URL = _env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_IMAGE_MODEL = _env("OPENAI_IMAGE_MODEL", "dall-e-3")
COMFYUI_URL = _env("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
ELEVENLABS_API_KEY = _env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = _env("ELEVENLABS_VOICE_ID")
WHISPER_MODEL = _env("WHISPER_MODEL", "tiny")
API_HOST = _env("API_HOST", "127.0.0.1")
API_PORT = int(_env("API_PORT", "8765") or "8765")
DATA_DIR = Path(_env("DATA_DIR") or (ROOT / "data"))
PROMPTS_DIR = ROOT / "prompts"
ASSETS_DIR = ROOT / "assets"
SAMPLES_DIR = ROOT / "samples"

DATA_DIR.mkdir(parents=True, exist_ok=True)
