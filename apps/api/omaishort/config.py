from __future__ import annotations

from pathlib import Path
import os

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = True) -> bool:
    raw = _env(name, "1" if default else "0").lower()
    if not raw:
        return default
    return raw not in ("0", "false", "no", "off")


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)) or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)) or default)
    except ValueError:
        return default


OPENAI_API_KEY = _env("OPENAI_API_KEY")
OPENAI_BASE_URL = _env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = _env("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_IMAGE_MODEL = _env("OPENAI_IMAGE_MODEL", "dall-e-3")
CHATGPT_WEB_ENABLED = _env_bool("CHATGPT_WEB_ENABLED", True)
CHATGPT_WEB_HEADED = _env_bool("CHATGPT_WEB_HEADED", False)
CHATGPT_WEB_MODEL = _env("CHATGPT_WEB_MODEL")
CHATGPT_WEB_TIMEOUT_MIN = _env_int("CHATGPT_WEB_TIMEOUT_MIN", 8)
GEMINI_API_KEY = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
GEMINI_IMAGE_MODEL = _env("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image") or "gemini-2.5-flash-image"
COMFYUI_URL = _env("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
POLLINATIONS_ENABLED = _env_bool("POLLINATIONS_ENABLED", True)
POLLINATIONS_URL = _env("POLLINATIONS_URL", "https://image.pollinations.ai").rstrip("/")
POLLINATIONS_MODEL = _env("POLLINATIONS_MODEL", "turbo") or "turbo"
POLLINATIONS_KEY = _env("POLLINATIONS_KEY")
POLLINATIONS_VIDEO_ENABLED = _env_bool("POLLINATIONS_VIDEO_ENABLED", True)
POLLINATIONS_VIDEO_URL = _env("POLLINATIONS_VIDEO_URL", "https://gen.pollinations.ai").rstrip("/")
POLLINATIONS_VIDEO_MODEL = _env("POLLINATIONS_VIDEO_MODEL", "wan-fast") or "wan-fast"
WAVESPEED_API_KEY = _env("WAVESPEED_API_KEY")
WAVESPEED_ENABLED = _env_bool("WAVESPEED_ENABLED", True)
WAVESPEED_URL = _env("WAVESPEED_URL", "https://api.wavespeed.ai/api/v3").rstrip("/")
WAVESPEED_MODEL = _env("WAVESPEED_MODEL", "wavespeed-ai/wan-2.2/i2v-480p-ultra-fast") or (
    "wavespeed-ai/wan-2.2/i2v-480p-ultra-fast"
)
HF_I2V_ENABLED = _env_bool("HF_I2V_ENABLED", True)
HF_I2V_SPACE_URL = _env("HF_I2V_SPACE_URL", "https://lightricks-ltx-video-distilled.hf.space").rstrip("/")
HF_I2V_WAN_URL = _env("HF_I2V_WAN_URL", "https://multimodalart-wan2-1-fast.hf.space").rstrip("/")
HF_TOKEN = _env("HF_TOKEN") or _env("HUGGINGFACE_HUB_TOKEN")
ELEVENLABS_API_KEY = _env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = _env("ELEVENLABS_VOICE_ID")
WHISPER_MODEL = _env("WHISPER_MODEL", "tiny")
API_HOST = _env("API_HOST", "127.0.0.1")
API_PORT = int(_env("API_PORT", "8765") or "8765")
_raw_data = _env("DATA_DIR")
DATA_DIR = Path(_raw_data) if _raw_data else (ROOT / "data")
if not DATA_DIR.is_absolute():
    DATA_DIR = (ROOT / DATA_DIR).resolve()
PROMPTS_DIR = ROOT / "prompts"
ASSETS_DIR = ROOT / "assets"
SAMPLES_DIR = ROOT / "samples"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def default_subtitle_style():
    from omaishort_schema.models import SubtitleStyle

    return SubtitleStyle(
        font=_env("SUBTITLE_FONT", "Arial") or "Arial",
        font_size=min(120, max(24, _env_int("SUBTITLE_SIZE", 64))),
        primary_hex=_env("SUBTITLE_PRIMARY", "#FFFFFF") or "#FFFFFF",
        highlight_hex=_env("SUBTITLE_HIGHLIGHT", "#FFE000") or "#FFE000",
        outline_hex=_env("SUBTITLE_OUTLINE", "#101010") or "#101010",
        outline=min(12, max(0, _env_int("SUBTITLE_OUTLINE_W", 5))),
        margin_v=min(400, max(20, _env_int("SUBTITLE_MARGIN_V", 120))),
    )


def default_mix_settings():
    from omaishort_schema.models import MixSettings

    return MixSettings(
        bgm_enabled=_env_bool("BGM_ENABLED", True),
        bgm_volume=min(1.0, max(0.0, _env_float("BGM_VOLUME", 0.14))),
        duck=_env_bool("BGM_DUCK", True),
        logo_enabled=_env_bool("LOGO_ENABLED", False),
    )
