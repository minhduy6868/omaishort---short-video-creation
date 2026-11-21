"""Optional multimodal VLM adapter for shot-by-shot video reverse engineering.

Supports:
1. REA_VLM_BASE_URL + REA_VLM_API_KEY (OpenAI-compatible vision endpoint, e.g. Doubao, Qwen-VL, OpenRouter)
2. GEMINI_API_KEY (Gemini generateContent REST with inline JPEG keyframes)
3. OPENAI_API_KEY / OPENAI_BASE_URL (OpenAI-compatible multimodal chat completions)

Falls back cleanly to None when offline or unkeyed so FFmpeg/Pillow forensics still succeed.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import httpx

from omaishort import config
from omaishort.providers.llm import llm_model, parse_llm_json

_SYSTEM_PROMPT = """You are a short-video director and reverse-engineering analyst (rea-video style).
You receive sampled JPEG keyframes from shots of a reference video, along with shot timing metadata and optional transcript.
Your job is to extract a REUSABLE production blueprint — NEVER copy copyrighted people, faces, brands, or raw dialogue verbatim into new prompts.

Return STRICT JSON with this exact shape:
{
  "hook_style": "1 short sentence describing how the first 3-5s hooks attention (pattern, tension, visual trick)",
  "visual_style": "1 short sentence describing lighting, color grade, composition, and production polish",
  "template_brief": "Concise 2-4 sentence Vietnamese/English production brief (<= 450 chars) instructing a writer/director how to replicate this pacing, hook structure, visual rhythm, and tone for a NEW story/topic.",
  "shots": [
    {
      "index": 1,
      "production_type": "live_action | ai_video | motion_graphic | screen_recording | avatar | hybrid",
      "camera": "wide | medium | close_up",
      "motion": "hold | zoom_in | zoom_out | pan_left | pan_right",
      "visual_summary": "short description of framing, subject role, lighting, and graphic/text overlay",
      "prompt_hint": "reusable cinematography/lighting/composition cue (no copied faces or text)"
    }
  ]
}
"""


def _b64_jpeg(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _build_user_text(shot_table: str, transcript: str, language: str) -> str:
    parts = [
        f"Target brief language: {language}",
        "SHOTS TIMING & LOCAL FORENSICS:",
        shot_table,
    ]
    if transcript.strip():
        parts.append(f"REFERENCE TRANSCRIPT (analyze hook/pacing structure only):\n{transcript.strip()[:2500]}")
    parts.append("Analyze each provided keyframe in order and return strict JSON.")
    return "\n\n".join(parts)


async def _call_openai_compat(
    base_url: str,
    api_key: str,
    model: str,
    user_text: str,
    frames: list[tuple[int, Path]],
) -> dict[str, Any] | None:
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for shot_idx, frame_path in frames:
        if not frame_path.is_file():
            continue
        content.append({"type": "text", "text": f"Keyframe for shot #{shot_idx}:"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{_b64_jpeg(frame_path)}", "detail": "low"},
            }
        )
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload: dict[str, Any] = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
    }
    url = f"{base_url.rstrip('/')}/chat/completions"
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        body = resp.json()
        raw = body["choices"][0]["message"]["content"]
        return parse_llm_json(raw if isinstance(raw, str) else "")


async def _call_gemini(
    api_key: str,
    model: str,
    user_text: str,
    frames: list[tuple[int, Path]],
) -> dict[str, Any] | None:
    parts: list[dict[str, Any]] = [{"text": f"{_SYSTEM_PROMPT}\n\n{user_text}"}]
    for shot_idx, frame_path in frames:
        if not frame_path.is_file():
            continue
        parts.append({"text": f"Keyframe for shot #{shot_idx}:"})
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": _b64_jpeg(frame_path)}})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        out_parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "\n".join(str(p.get("text") or "") for p in out_parts if isinstance(p, dict))
        return parse_llm_json(text)


def _cfg(name: str, default: str = "") -> str:
    return str(getattr(config, name, default) or default).strip()


def vision_configured() -> bool:
    return bool(
        (_cfg("REA_VLM_BASE_URL") and _cfg("REA_VLM_API_KEY"))
        or _cfg("GEMINI_API_KEY")
        or _cfg("OPENAI_API_KEY")
    )


async def analyze_keyframes_vlm(
    *,
    shot_table: str,
    frames: list[tuple[int, Path]],
    transcript: str = "",
    language: str = "vi",
    max_frames: int = 10,
) -> tuple[dict[str, Any] | None, str]:
    """Send sampled shot keyframes to a configured VLM. Returns (json_or_none, provider_name)."""
    if not frames:
        return None, "ffmpeg"
    # Evenly sample up to max_frames so long videos stay within multimodal budgets.
    if len(frames) > max_frames:
        step = (len(frames) - 1) / max(1, max_frames - 1)
        sampled = [frames[int(round(i * step))] for i in range(max_frames)]
    else:
        sampled = list(frames)

    user_text = _build_user_text(shot_table, transcript, language)

    rea_url = _cfg("REA_VLM_BASE_URL")
    rea_key = _cfg("REA_VLM_API_KEY")
    if rea_url and rea_key:
        try:
            model = _cfg("REA_VLM_MODEL", "gpt-4o-mini")
            parsed = await _call_openai_compat(rea_url, rea_key, model, user_text, sampled)
            if parsed:
                return parsed, "rea-vlm"
        except Exception:
            pass

    gemini_key = _cfg("GEMINI_API_KEY")
    if gemini_key:
        try:
            gemini_model = _cfg("GEMINI_VISION_MODEL", "gemini-2.0-flash")
            parsed = await _call_gemini(gemini_key, gemini_model, user_text, sampled)
            if parsed:
                return parsed, "gemini-vlm"
        except Exception:
            pass

    openai_key = _cfg("OPENAI_API_KEY")
    if openai_key:
        try:
            openai_url = _cfg("OPENAI_BASE_URL", "https://api.openai.com/v1")
            parsed = await _call_openai_compat(openai_url, openai_key, llm_model(openai_url), user_text, sampled)
            if parsed:
                return parsed, "openai-vlm"
        except Exception:
            pass

    return None, "ffmpeg"
