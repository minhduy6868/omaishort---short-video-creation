"""Local-first HTTP auth: scrypt passwords, HS256 access JWT, rotating refresh.

See docs/AUTH.md. Planner never imports this module.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Cookie, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from omaishort import db
from omaishort.config import (
    AUTH_ACCESS_TTL_SEC,
    AUTH_COOKIE_SECURE,
    AUTH_REFRESH_TTL_SEC,
    AUTH_SECRET,
)
from omaishort import config

ACCESS_COOKIE = "omaishort_at"
REFRESH_COOKIE = "omaishort_rt"
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DUMMY_HASH = ""
_unknown_fails: dict[str, tuple[int, float]] = {}


class RegisterBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class RefreshBody(BaseModel):
    refresh_token: str | None = None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def auth_secret() -> str:
    env = os.environ.get("AUTH_SECRET", "").strip() or (AUTH_SECRET or "").strip()
    if env:
        return env
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = config.DATA_DIR / ".auth_secret"
    if path.is_file():
        stored = path.read_text(encoding="utf-8").strip()
        if stored:
            return stored
    secret = secrets.token_urlsafe(48)
    path.write_text(secret, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return secret


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_hex, dk_hex = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(dk_hex)
    got = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=len(expected))
    return hmac.compare_digest(got, expected)


def dummy_hash() -> str:
    global _DUMMY_HASH
    if not _DUMMY_HASH:
        _DUMMY_HASH = hash_password("omaishort-dummy-lock-not-a-user")
    return _DUMMY_HASH


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email)) and ".." not in email


def encode_access(user: dict[str, Any]) -> str:
    now = int(time.time())
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "typ": "access",
        "iat": now,
        "exp": now + AUTH_ACCESS_TTL_SEC,
    }
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = hmac.new(auth_secret().encode("utf-8"), f"{header}.{body}".encode("ascii"), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64url(sig)}"


def decode_access(token: str) -> dict[str, Any]:
    try:
        header_b64, body_b64, sig_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        if header.get("alg") != "HS256":
            raise ValueError("alg")
        expected = hmac.new(
            auth_secret().encode("utf-8"),
            f"{header_b64}.{body_b64}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
            raise ValueError("sig")
        payload = json.loads(_b64url_decode(body_b64))
        if payload.get("typ") != "access":
            raise ValueError("typ")
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("exp")
        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, binascii.Error):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated") from None


def hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=AUTH_ACCESS_TTL_SEC,
        httponly=True,
        samesite="lax",
        secure=AUTH_COOKIE_SECURE,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=AUTH_REFRESH_TTL_SEC,
        httponly=True,
        samesite="lax",
        secure=AUTH_COOKIE_SECURE,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.set_cookie(
            name,
            "",
            max_age=0,
            expires=0,
            httponly=True,
            samesite="lax",
            secure=AUTH_COOKIE_SECURE,
            path="/",
        )


def token_payload(user: dict[str, Any], refresh: str) -> dict[str, Any]:
    access = encode_access(user)
    return {
        "user": db.public_user(user),
        "access_token": access,
        "token_type": "bearer",
        "expires_in": AUTH_ACCESS_TTL_SEC,
        "refresh_token": refresh,
    }


def issue_refresh(user_id: str, user_agent: str | None) -> str:
    raw = new_refresh_token()
    expires = datetime.now(timezone.utc) + timedelta(seconds=AUTH_REFRESH_TTL_SEC)
    db.insert_refresh(
        secrets.token_hex(8),
        user_id,
        hash_refresh(raw),
        expires.isoformat(),
        (user_agent or "")[:200] or None,
    )
    return raw


def rotate_refresh(raw: str, user_agent: str | None) -> tuple[dict[str, Any], str]:
    row = db.get_refresh_by_hash(hash_refresh(raw))
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    if row.get("revoked_at"):
        db.revoke_user_refresh(row["user_id"])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    expires = datetime.fromisoformat(row["expires_at"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        db.revoke_refresh(row["id"])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    user = db.get_user_by_id(row["user_id"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    db.revoke_refresh(row["id"])
    return user, issue_refresh(user["id"], user_agent)


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value


def register_user(body: RegisterBody) -> dict[str, Any]:
    email = normalize_email(body.email)
    if not valid_email(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid email")
    if db.count_users() == 0:
        role = "operator"
    else:
        raw = os.environ.get("AUTH_SIGNUP", "1" if config.AUTH_SIGNUP else "0").strip().lower()
        if raw in ("0", "false", "no", "off"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "signup closed")
        role = "creator"
    name = (body.display_name or "").strip() or email.split("@", 1)[0]
    try:
        return db.create_user(secrets.token_hex(6), email, hash_password(body.password), name, role)
    except ValueError:
        raise HTTPException(status.HTTP_409_CONFLICT, "email taken") from None


def authenticate(body: LoginBody) -> dict[str, Any]:
    email = normalize_email(body.email)
    user = db.get_user_by_email(email) if valid_email(email) else None
    now = datetime.now(timezone.utc)
    if user:
        locked = _parse_iso(user.get("locked_until"))
        if locked and locked > now:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "account locked")
        if verify_password(body.password, user["password_hash"]):
            db.update_user(user["id"], failed_logins=0, locked_until=None)
            fresh = db.get_user_by_id(user["id"])
            assert fresh
            return fresh
        fails = int(user.get("failed_logins") or 0) + 1
        lock = (now + timedelta(minutes=15)).isoformat() if fails >= 8 else None
        db.update_user(user["id"], failed_logins=fails, locked_until=lock)
        if lock:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "account locked")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")
    verify_password(body.password, dummy_hash())
    key = hashlib.sha256(email.encode()).hexdigest()
    count, until = _unknown_fails.get(key, (0, 0.0))
    if until > time.time():
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "account locked")
    count += 1
    lock_until = time.time() + 15 * 60 if count >= 8 else 0.0
    _unknown_fails[key] = (count if lock_until == 0 else 0, lock_until)
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid email or password")


def session_from_user(user: dict[str, Any], response: Response, user_agent: str | None) -> dict[str, Any]:
    refresh = issue_refresh(user["id"], user_agent)
    payload = token_payload(user, refresh)
    set_auth_cookies(response, payload["access_token"], refresh)
    return payload


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    omaishort_at: Annotated[str | None, Cookie()] = None,
) -> dict[str, Any]:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif omaishort_at:
        token = omaishort_at
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    payload = decode_access(token)
    user = db.get_user_by_id(str(payload.get("sub") or ""))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    locked = _parse_iso(user.get("locked_until"))
    if locked and locked > datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not authenticated")
    return user


CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def can_read_job(row: dict[str, Any], user: dict[str, Any]) -> bool:
    owner = row.get("user_id")
    if owner and owner == user["id"]:
        return True
    if not owner and user.get("role") == "operator":
        return True
    return False


def require_job(job_id: str, user: dict[str, Any]) -> dict[str, Any]:
    row = db.get_job(job_id)
    if not row or not can_read_job(row, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return row
