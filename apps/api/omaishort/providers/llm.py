from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from omaishort.config import (
    CHATGPT_WEB_ENABLED,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    PROMPTS_DIR,
)
from omaishort.providers import chatgpt_web

_OPENAI_CLOUD = {"https://api.openai.com/v1", "https://api.openai.com"}
_WEB2API_BASE = "http://127.0.0.1:8080/v1"
_web2api_up: bool | None = None


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _openai_cloud() -> bool:
    return OPENAI_BASE_URL.rstrip("/") in _OPENAI_CLOUD


def llm_base_url() -> str:
    if _openai_cloud() and not OPENAI_API_KEY:
        return _WEB2API_BASE
    return OPENAI_BASE_URL.rstrip("/")


def llm_model(base: str | None = None) -> str:
    model = OPENAI_MODEL or "gpt-4o-mini"
    host = (base or llm_base_url()).lower()
    if "127.0.0.1:8080" in host or "localhost:8080" in host:
        if model in {"", "gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-4"}:
            return "auto"
    return model


def _probe_url(url: str, timeout: float = 1.5) -> bool:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            client.get(url)
        return True
    except Exception:
        return False


def _probe_web2api() -> bool:
    global _web2api_up
    if _web2api_up is not None:
        return _web2api_up
    _web2api_up = _probe_url("http://127.0.0.1:8080/", 1.2)
    return _web2api_up


def llm_http_available() -> bool:
    if _openai_cloud() and OPENAI_API_KEY:
        return True
    if _openai_cloud() and not OPENAI_API_KEY:
        return _probe_web2api()
    return _probe_url(llm_base_url().rstrip("/") + "/models") or _probe_url(OPENAI_BASE_URL)


def llm_status() -> dict[str, object]:
    return {
        "http": llm_http_available(),
        "chatgpt_web": bool(CHATGPT_WEB_ENABLED and chatgpt_web.playwright_ok()),
        "chatgpt_web_authed": chatgpt_web.is_authed(),
        "chatgpt_web_profile": str(chatgpt_web.profile_dir()),
        "chatgpt_web_chat": (chatgpt_web.load_daily_chat() or {}).get("url") or "",
    }


def llm_skip_reason() -> str:
    bits: list[str] = []
    if not OPENAI_API_KEY:
        bits.append("no OPENAI_API_KEY")
    if _openai_cloud() and not _probe_web2api():
        bits.append("ChatGPT-Web2API http://127.0.0.1:8080 is down")
    if not chatgpt_web.playwright_ok():
        bits.append("playwright missing (pip install playwright && python -m playwright install chromium)")
    elif not chatgpt_web.is_authed():
        bits.append("ChatGPT web not logged in (python -m omaishort --chatgpt-login)")
    return "; ".join(bits) or "LLM returned no JSON"


def llm_configured() -> bool:
    return llm_http_available() or (CHATGPT_WEB_ENABLED and chatgpt_web.playwright_ok() and chatgpt_web.is_authed())


def parse_llm_json(content: str) -> dict[str, Any] | None:
    blob = (content or "").strip()
    if not blob:
        return None
    blob = re.sub(r"\n*CONVERSATION_URL:.*$", "", blob, flags=re.I | re.M).strip()
    if blob.startswith("```"):
        blob = re.sub(r"^```(?:json)?\s*", "", blob, flags=re.I)
        blob = re.sub(r"\s*```\s*$", "", blob)
    try:
        data = json.loads(blob)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", blob, flags=re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


async def _complete_http(system: str, user: str) -> tuple[dict[str, Any] | None, str]:
    base = llm_base_url()
    headers = {"Content-Type": "application/json"}
    if OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {OPENAI_API_KEY}"
    payload: dict[str, Any] = {
        "model": llm_model(base),
        "temperature": 0.4,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if "api.openai.com" in base and OPENAI_API_KEY:
        payload["response_format"] = {"type": "json_object"}
    url = f"{base}/chat/completions"
    timeout = 300.0 if ":8080" in base else 180.0
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code == 429:
            wait = min(20.0, float(response.headers.get("Retry-After") or 8))
            await asyncio.sleep(wait)
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400 and "response_format" in payload:
            payload.pop("response_format", None)
            response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = parse_llm_json(content if isinstance(content, str) else json.dumps(content))
        return parsed, "llm"


async def _complete_chatgpt_web(system: str, user: str) -> tuple[dict[str, Any] | None, str]:
    try:
        text = await chatgpt_web.complete_json_prompt(system, user)
    except Exception as exc:
        return None, str(exc)[:240]
    parsed = parse_llm_json(text)
    if not parsed:
        return None, "ChatGPT web returned non-JSON"
    return parsed, "chatgpt-web"


async def complete_json_result(system: str, user: str) -> tuple[dict[str, Any] | None, str, str]:
    """Return (json, provider, error). provider is llm | chatgpt-web | empty."""
    cli_err = ""
    if CHATGPT_WEB_ENABLED and chatgpt_web.playwright_ok() and chatgpt_web.is_authed():
        parsed, src = await _complete_chatgpt_web(system, user)
        if parsed:
            return parsed, src, ""
        cli_err = src
    elif CHATGPT_WEB_ENABLED and chatgpt_web.playwright_ok() and not chatgpt_web.is_authed():
        cli_err = "ChatGPT web not logged in (python -m omaishort --chatgpt-login)"
    if llm_http_available():
        try:
            parsed, src = await _complete_http(system, user)
            if parsed:
                return parsed, src, ""
        except Exception as exc:
            http_err = f"HTTP LLM failed: {type(exc).__name__}"
        else:
            http_err = "HTTP LLM returned no JSON"
    else:
        http_err = ""
    return None, "", cli_err or http_err or llm_skip_reason()


async def complete_json(system: str, user: str) -> dict[str, Any] | None:
    data, _src, _err = await complete_json_result(system, user)
    return data
