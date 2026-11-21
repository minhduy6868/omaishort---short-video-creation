"""Secure REST + JWT client for omaishort Cloudflare Worker (/v1/*).

When CLOUD_API_URL is configured (and raw D1_WORKER_KEY is absent), the desktop
app authenticates users, checks/holds credits, and syncs job metadata, small
attachments (<=600KB), and reverse-engineered templates to Cloudflare D1 via JWT.
Video MP4 files and FFmpeg rendering always stay local on the user's machine.
"""

from __future__ import annotations

from contextvars import ContextVar
import os
import threading
import time
from typing import Any

import certifi
from fastapi import HTTPException
import httpx

from omaishort import config

_req_token: ContextVar[str | None] = ContextVar("omaishort_cloud_token", default=None)
_job_tokens: dict[str, str] = {}
_me_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_lock = threading.Lock()
_ME_TTL_SEC = 8.0


def cloud_api_url() -> str:
    env_url = os.environ.get("CLOUD_API_URL", "").strip()
    configured = (getattr(config, "CLOUD_API_URL", "") or "").strip()
    return (env_url or configured).rstrip("/")


def cloud_mode_enabled() -> bool:
    url = cloud_api_url()
    if not url:
        return False
    # If operator explicitly configured raw D1_WORKER_KEY without forcing cloud mode, keep direct D1.
    force = os.environ.get("OMAISHORT_CLOUD_MODE", "").strip().lower() in {"1", "true", "yes", "on"}
    if force:
        return True
    has_raw_key = bool(os.environ.get("D1_WORKER_KEY", "").strip() or getattr(config, "D1_WORKER_KEY", ""))
    return not has_raw_key


def set_request_token(token: str | None) -> None:
    _req_token.set(token or None)


def get_request_token() -> str | None:
    return _req_token.get()


def bind_job_token(job_id: str, token: str | None = None) -> None:
    tok = token or get_request_token()
    if tok:
        with _lock:
            _job_tokens[job_id] = tok


def token_for_job(job_id: str) -> str | None:
    tok = get_request_token()
    if tok:
        return tok
    with _lock:
        return _job_tokens.get(job_id)


def invalidate_me_cache(token: str | None = None) -> None:
    with _lock:
        if token:
            _me_cache.pop(token, None)
        else:
            _me_cache.clear()


def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> tuple[int, Any]:
    base = cloud_api_url()
    if not base:
        raise HTTPException(503, "CLOUD_API_URL is not configured")
    url = f"{base}{path}"
    headers = {"user-agent": "omaishort-desktop/0.1"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=timeout, verify=certifi.where()) as client:
            resp = client.request(method, url, headers=headers, json=json_body, params=params)
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"Không kết nối được Cloudflare Cloud API: {exc}") from exc

    if resp.status_code == 204:
        return 204, None
    try:
        payload = resp.json()
    except Exception:
        payload = {"detail": resp.text[:300] or f"Cloud API error ({resp.status_code})"}
    if resp.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else str(payload)
        if resp.status_code == 402:
            from omaishort.billing import CreditsExhausted

            billing = payload.get("billing") if isinstance(payload, dict) else None
            raise CreditsExhausted(str(detail or "credits exhausted"), billing)
        raise HTTPException(resp.status_code, str(detail or f"Cloud error {resp.status_code}"))
    return resp.status_code, payload


# ---- Auth ----
def auth_register(email: str, password: str, display_name: str | None, user_agent: str | None = None) -> dict[str, Any]:
    del user_agent
    _, data = _request(
        "POST",
        "/v1/auth/register",
        json_body={"email": email, "password": password, "display_name": display_name},
    )
    return dict(data)


def auth_login(email: str, password: str, user_agent: str | None = None) -> dict[str, Any]:
    del user_agent
    _, data = _request("POST", "/v1/auth/login", json_body={"email": email, "password": password})
    return dict(data)


def auth_refresh(refresh_token: str) -> dict[str, Any]:
    _, data = _request("POST", "/v1/auth/refresh", json_body={"refresh_token": refresh_token})
    return dict(data)


def auth_logout(refresh_token: str | None) -> None:
    if not refresh_token:
        return
    try:
        _request("POST", "/v1/auth/logout", json_body={"refresh_token": refresh_token})
    except HTTPException:
        pass
    invalidate_me_cache()


def auth_me(token: str, *, use_cache: bool = True) -> dict[str, Any]:
    now = time.monotonic()
    if use_cache:
        with _lock:
            hit = _me_cache.get(token)
            if hit and hit[0] > now:
                return dict(hit[1])
    _, data = _request("GET", "/v1/auth/me", token=token)
    user = dict(data)
    with _lock:
        _me_cache[token] = (now + _ME_TTL_SEC, user)
    return user


# ---- Site theme ----
def site_theme_get() -> dict[str, Any]:
    _, data = _request("GET", "/v1/site/theme")
    return dict(data)


def site_theme_put(theme: str, token: str | None = None) -> dict[str, Any]:
    _, data = _request("PUT", "/v1/site/theme", token=token or get_request_token(), json_body={"theme": theme})
    return dict(data)


# ---- Billing ----
def billing_plans() -> dict[str, Any]:
    _, data = _request("GET", "/v1/billing/plans")
    return dict(data)


def billing_me(token: str | None = None) -> dict[str, Any]:
    _, data = _request("GET", "/v1/billing/me", token=token or get_request_token())
    return dict(data)


def billing_checkout(plan_code: str, token: str | None = None) -> dict[str, Any]:
    _, data = _request(
        "POST",
        "/v1/billing/checkout",
        token=token or get_request_token(),
        json_body={"plan_code": plan_code},
    )
    return dict(data)


def billing_hold(job_id: str, token: str | None = None) -> dict[str, Any]:
    tok = token or token_for_job(job_id)
    _, data = _request("POST", "/v1/billing/hold", token=tok, json_body={"job_id": job_id})
    invalidate_me_cache(tok)
    return dict(data)


def billing_refund(job_id: str, token: str | None = None) -> None:
    tok = token or token_for_job(job_id)
    if not tok:
        return
    try:
        _request("POST", "/v1/billing/refund", token=tok, json_body={"job_id": job_id})
        invalidate_me_cache(tok)
    except HTTPException:
        pass


# ---- Jobs ----
def jobs_list(limit: int = 20, token: str | None = None) -> list[dict[str, Any]]:
    _, data = _request("GET", "/v1/jobs", token=token or get_request_token(), params={"limit": limit})
    return list(data.get("jobs") or [])


def jobs_create(job_id: str, input_json: str, token: str | None = None) -> dict[str, Any]:
    tok = token or token_for_job(job_id)
    bind_job_token(job_id, tok)
    _, data = _request(
        "POST",
        "/v1/jobs",
        token=tok,
        json_body={"id": job_id, "input_json": input_json, "status": "queued", "stage": "queued"},
    )
    return dict(data.get("job") or {})


def jobs_get(job_id: str, token: str | None = None) -> dict[str, Any] | None:
    try:
        _, data = _request("GET", f"/v1/jobs/{job_id}", token=token or token_for_job(job_id))
        return dict(data.get("job") or {})
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise


def sync_job_fields(job_id: str, fields: dict[str, Any]) -> None:
    """Best-effort metadata sync from local pipeline to Cloudflare D1 (never blocks local render)."""
    if not cloud_mode_enabled() or not fields:
        return
    tok = token_for_job(job_id)
    if not tok:
        return
    try:
        _request("PATCH", f"/v1/jobs/{job_id}", token=tok, json_body=fields, timeout=12.0)
    except Exception:
        pass


def sync_job_delete(job_id: str) -> None:
    if not cloud_mode_enabled():
        return
    tok = token_for_job(job_id)
    if not tok:
        return
    try:
        _request("DELETE", f"/v1/jobs/{job_id}", token=tok, timeout=12.0)
    except Exception:
        pass


# ---- Attachments ----
def attachments_list(token: str | None = None) -> list[dict[str, Any]]:
    _, data = _request("GET", "/v1/attachments", token=token or get_request_token())
    return list(data.get("attachments") or [])


def attachments_create(row: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    _, data = _request("POST", "/v1/attachments", token=token or get_request_token(), json_body=row)
    return dict(data.get("attachment") or row)


def attachments_get(attachment_id: str, token: str | None = None) -> dict[str, Any] | None:
    try:
        _, data = _request("GET", f"/v1/attachments/{attachment_id}", token=token or get_request_token())
        return dict(data.get("attachment") or {})
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise


def attachments_delete(attachment_id: str, token: str | None = None) -> None:
    try:
        _request("DELETE", f"/v1/attachments/{attachment_id}", token=token or get_request_token())
    except HTTPException:
        pass


# ---- Reverse-Engineered Templates ----
def templates_list(token: str | None = None) -> list[dict[str, Any]]:
    _, data = _request("GET", "/v1/templates", token=token or get_request_token())
    return list(data.get("templates") or [])


def templates_create(blueprint_dict: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    _, data = _request("POST", "/v1/templates", token=token or get_request_token(), json_body=blueprint_dict)
    return dict(data.get("template") or blueprint_dict)


def templates_get(template_id: str, token: str | None = None) -> dict[str, Any] | None:
    try:
        _, data = _request("GET", f"/v1/templates/{template_id}", token=token or get_request_token())
        return dict(data.get("template") or {})
    except HTTPException as exc:
        if exc.status_code == 404:
            return None
        raise


def templates_delete(template_id: str, token: str | None = None) -> bool:
    try:
        _request("DELETE", f"/v1/templates/{template_id}", token=token or get_request_token())
        return True
    except HTTPException as exc:
        if exc.status_code == 404:
            return False
        raise


# ---- Admin ----
def admin_overview(token: str | None = None) -> dict[str, Any]:
    _, data = _request("GET", "/v1/admin/overview", token=token or get_request_token())
    return dict(data)


def admin_settings(payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    _, data = _request("PUT", "/v1/admin/settings", token=token or get_request_token(), json_body=payload)
    return dict(data)


def admin_users_list(token: str | None = None) -> dict[str, Any]:
    _, data = _request("GET", "/v1/admin/users", token=token or get_request_token())
    return dict(data)


def admin_users_patch(user_id: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    _, data = _request("PATCH", f"/v1/admin/users/{user_id}", token=token or get_request_token(), json_body=payload)
    return dict(data)


def admin_jobs_list(params: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    _, data = _request("GET", "/v1/admin/jobs", token=token or get_request_token(), params=params)
    return dict(data)


def admin_billing_overview(token: str | None = None) -> dict[str, Any]:
    _, data = _request("GET", "/v1/admin/billing/overview", token=token or get_request_token())
    return dict(data)


def admin_billing_orders(params: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    _, data = _request("GET", "/v1/admin/billing/orders", token=token or get_request_token(), params=params)
    return dict(data)


def admin_billing_order_patch(order_id: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    _, data = _request(
        "PATCH",
        f"/v1/admin/billing/orders/{order_id}",
        token=token or get_request_token(),
        json_body=payload,
    )
    return dict(data)


def admin_billing_grant(user_id: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    _, data = _request(
        "POST",
        f"/v1/admin/billing/users/{user_id}/grant",
        token=token or get_request_token(),
        json_body=payload,
    )
    return dict(data)


def admin_billing_plan_patch(code: str, payload: dict[str, Any], token: str | None = None) -> dict[str, Any]:
    _, data = _request(
        "PATCH",
        f"/v1/admin/billing/plans/{code}",
        token=token or get_request_token(),
        json_body=payload,
    )
    return dict(data)
