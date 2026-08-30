from __future__ import annotations

import json
from typing import Any

import httpx

from omaishort.config import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, PROMPTS_DIR


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def llm_configured() -> bool:
    if OPENAI_BASE_URL.rstrip("/") in {"https://api.openai.com/v1", "https://api.openai.com"}:
        return bool(OPENAI_API_KEY)
    return True


async def complete_json(system: str, user: str) -> dict[str, Any] | None:
    if not llm_configured():
        return None
    headers = {"Content-Type": "application/json"}
    if OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    url = f"{OPENAI_BASE_URL}/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code >= 400:
                payload.pop("response_format", None)
                response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception:
        return None
