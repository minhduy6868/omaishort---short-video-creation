"""Local ElevenLabs hub: API key and voice live under data/, not in git."""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import BaseModel, Field

from omaishort import config
from omaishort.providers.elevenlabs_anonymous import DEFAULT_MODEL, DEFAULT_VOICE, MODELS, PUBLIC_VOICES

_VOICES = "https://api.elevenlabs.io/v1/voices"


class ElevenLabsHubBody(BaseModel):
    api_key: str | None = None
    voice_id: str | None = Field(default=None, max_length=80)
    enabled: bool | None = None
    mode: str | None = None
    model_id: str | None = Field(default=None, max_length=40)


def hub_path():
    return config.DATA_DIR / "elevenlabs-hub.json"


def _read_file() -> dict[str, Any]:
    path = hub_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_file(data: dict[str, Any]) -> None:
    path = hub_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def api_key() -> str:
    data = _read_file()
    saved = str(data.get("api_key") or "").strip()
    if saved:
        return saved
    if data.get("cleared"):
        return ""
    return (config.ELEVENLABS_API_KEY or "").strip()


def mode() -> str:
    data = _read_file()
    raw = str(data.get("mode") or "").strip()
    if raw in {"anonymous", "api"}:
        return raw
    if str(data.get("api_key") or "").strip() or (config.ELEVENLABS_API_KEY or "").strip():
        return "api"
    return "anonymous"


def voice_id() -> str:
    data = _read_file()
    saved = str(data.get("voice_id") or "").strip()
    if saved:
        return saved
    if data.get("cleared") and mode() != "anonymous":
        return ""
    if mode() == "anonymous":
        return DEFAULT_VOICE
    return (config.ELEVENLABS_VOICE_ID or "").strip()


def enabled() -> bool:
    data = _read_file()
    if mode() == "anonymous":
        return bool(data.get("enabled")) and bool(voice_id())
    if "enabled" in data:
        return bool(data.get("enabled")) and bool(api_key()) and bool(voice_id())
    return bool(api_key()) and bool(voice_id())


def uses_anonymous() -> bool:
    return enabled() and mode() == "anonymous"


def model_id() -> str:
    saved = str(_read_file().get("model_id") or "").strip()
    if saved in MODELS:
        return saved
    return DEFAULT_MODEL


def public_catalog(selected: str) -> list[dict[str, str]]:
    rows = [{"id": row["id"], "name": row["name"]} for row in PUBLIC_VOICES]
    if selected and not any(row["id"] == selected for row in rows):
        rows.append({"id": selected, "name": selected})
    return rows


def key_hint(key: str) -> str:
    raw = (key or "").strip()
    if len(raw) < 8:
        return ""
    return f"…{raw[-4:]}"


def fetch_voices(key: str) -> list[dict[str, str]]:
    token = (key or "").strip()
    if not token:
        return []
    try:
        response = httpx.get(
            _VOICES,
            headers={"xi-api-key": token},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError("ElevenLabs không phản hồi") from exc
    if response.status_code in {401, 403}:
        raise ValueError("Khóa ElevenLabs không hợp lệ")
    if response.status_code >= 400:
        raise RuntimeError(f"ElevenLabs trả về {response.status_code}")
    payload = response.json()
    rows = payload.get("voices") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    voices: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        vid = str(row.get("voice_id") or "").strip()
        name = str(row.get("name") or vid).strip()
        if not vid:
            continue
        voices.append({"id": vid, "name": name})
    return voices


def public_status(*, voices: list[dict[str, str]] | None = None, error: str = "") -> dict[str, Any]:
    key = api_key()
    selected = voice_id()
    current = mode()
    if current == "anonymous":
        catalog = public_catalog(selected)
    else:
        catalog = voices if voices is not None else list(_read_file().get("voices") or [])
    name = ""
    for row in catalog:
        if isinstance(row, dict) and row.get("id") == selected:
            name = str(row.get("name") or "")
            break
    return {
        "enabled": enabled(),
        "configured": bool(key),
        "mode": current,
        "model_id": model_id(),
        "voice_id": selected,
        "voice_name": name or ("Default" if selected == DEFAULT_VOICE else ""),
        "key_hint": key_hint(key),
        "voices": catalog,
        "error": error,
    }


def update(body: ElevenLabsHubBody) -> dict[str, Any]:
    data = _read_file()
    voices: list[dict[str, str]] | None = None
    if body.mode in {"anonymous", "api"}:
        data["mode"] = body.mode
    if body.api_key is not None:
        key = body.api_key.strip()
        if key:
            voices = fetch_voices(key)
            data["api_key"] = key
            data["cleared"] = False
            data["mode"] = "api"
            data["voices"] = voices
        else:
            data["api_key"] = ""
            data["cleared"] = True
            data["voices"] = []
            if data.get("mode") != "anonymous":
                data["enabled"] = False
                data["voice_id"] = ""
    if body.voice_id is not None:
        data["voice_id"] = body.voice_id.strip()
    if body.model_id is not None and body.model_id.strip() in MODELS:
        data["model_id"] = body.model_id.strip()
    if body.enabled is not None:
        data["enabled"] = bool(body.enabled)
    chosen = str(data.get("mode") or mode())
    if chosen == "anonymous" and not str(data.get("voice_id") or "").strip():
        data["voice_id"] = DEFAULT_VOICE
    if data.get("enabled") and chosen == "api" and not (str(data.get("api_key") or "").strip() or api_key()):
        data["enabled"] = False
    _write_file(data)
    return public_status(voices=voices)


def load_status() -> dict[str, Any]:
    key = api_key()
    if mode() == "anonymous" or not key:
        return public_status()
    try:
        voices = fetch_voices(key)
    except ValueError as exc:
        return public_status(error=str(exc))
    except RuntimeError as exc:
        cached = public_status(error=str(exc))
        return cached
    data = _read_file()
    data["voices"] = voices
    if data.get("api_key") or data.get("voice_id") or "enabled" in data:
        _write_file({**data, "voices": voices})
    return public_status(voices=voices)
