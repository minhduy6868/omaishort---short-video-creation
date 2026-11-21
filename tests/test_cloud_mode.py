"""Tests for FastAPI running in secure CLOUD_API_URL mode (REST + JWT, zero D1_WORKER_KEY)."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

import omaishort.config as cfg
from omaishort import cloud_client


class _FakeCloudBackend:
    """In-memory fake of Cloudflare Worker /v1/* validating Bearer JWTs and rejecting raw SQL keys."""

    def __init__(self) -> None:
        self.users: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, str] = {}
        self.refreshes: dict[str, str] = {}
        self.jobs: dict[str, dict[str, Any]] = {}
        self.attachments: dict[str, dict[str, Any]] = {}
        self.templates: dict[str, dict[str, Any]] = {}
        self.orders: dict[str, dict[str, Any]] = {}
        self.theme = "brutal"
        self.seen_raw_keys: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("x-omaishort-key"):
            self.seen_raw_keys.append(request.headers["x-omaishort-key"])
        path = request.url.path
        method = request.method.upper()
        body = json.loads(request.content.decode("utf-8")) if request.content else {}

        if method == "GET" and path == "/v1/site/theme":
            return httpx.Response(200, json={"theme": self.theme, "themes": ["brutal", "soft"]})

        if method == "GET" and path == "/v1/billing/plans":
            return httpx.Response(
                200,
                json={
                    "plans": [{"code": "starter", "name": "Starter", "credits": 20, "period_days": 30, "price_vnd": 199000, "active": True}],
                    "transfer_note": "OMAI test note",
                },
            )

        if method == "POST" and path == "/v1/auth/register":
            uid = f"u_{len(self.users) + 1}"
            role = "operator" if not self.users else "creator"
            billing = (
                {"plan_code": "trial", "status": "trial", "credits_remaining": 2, "credits_total": 2, "ends_at": "2099-01-01T00:00:00Z"}
                if role == "creator"
                else None
            )
            user = {
                "id": uid,
                "email": body["email"].lower(),
                "display_name": body.get("display_name") or "User",
                "role": role,
                "billing": billing,
            }
            self.users[uid] = user
            tok = f"jwt_{uid}"
            ref = f"rt_{uid}"
            self.tokens[tok] = uid
            self.refreshes[ref] = uid
            return httpx.Response(
                201,
                json={"user": user, "access_token": tok, "token_type": "bearer", "expires_in": 900, "refresh_token": ref},
            )

        if method == "POST" and path == "/v1/auth/login":
            user = next((u for u in self.users.values() if u["email"] == body["email"].lower()), None)
            if not user:
                return httpx.Response(401, json={"detail": "invalid email or password"})
            tok = f"jwt_{user['id']}"
            ref = f"rt_{user['id']}_2"
            self.tokens[tok] = user["id"]
            self.refreshes[ref] = user["id"]
            return httpx.Response(
                200,
                json={"user": user, "access_token": tok, "token_type": "bearer", "expires_in": 900, "refresh_token": ref},
            )

        if method == "POST" and path == "/v1/auth/refresh":
            uid = self.refreshes.get(body.get("refresh_token", ""))
            if not uid:
                return httpx.Response(401, json={"detail": "not authenticated"})
            user = self.users[uid]
            new_ref = f"rt_{uid}_rot"
            self.refreshes[new_ref] = uid
            return httpx.Response(
                200,
                json={"user": user, "access_token": f"jwt_{uid}", "token_type": "bearer", "expires_in": 900, "refresh_token": new_ref},
            )

        if method == "POST" and path == "/v1/auth/logout":
            return httpx.Response(204)

        auth = request.headers.get("authorization", "")
        tok = auth[7:] if auth.lower().startswith("bearer ") else ""
        uid = self.tokens.get(tok)
        if not uid:
            return httpx.Response(401, json={"detail": "not authenticated"})
        user = self.users[uid]

        if method == "GET" and path == "/v1/auth/me":
            return httpx.Response(200, json=user)

        if method == "GET" and path == "/v1/billing/me":
            return httpx.Response(200, json={"billing": user["billing"], "ledger": [], "pending_order": None, "transfer_note": "OMAI"})

        if method == "POST" and path == "/v1/billing/hold":
            if user["role"] == "operator":
                return httpx.Response(200, json={"ok": True, "billing": None})
            b = user["billing"]
            if not b or b["credits_remaining"] <= 0:
                return httpx.Response(402, json={"detail": "credits exhausted", "billing": b})
            b["credits_remaining"] -= 1
            return httpx.Response(200, json={"ok": True, "billing": b})

        if method == "POST" and path == "/v1/billing/refund":
            return httpx.Response(200, json={"ok": True})

        if method == "POST" and path == "/v1/jobs":
            jid = body["id"]
            self.jobs[jid] = {
                "id": jid,
                "user_id": uid,
                "status": body.get("status", "queued"),
                "stage": body.get("stage", "queued"),
                "input": json.loads(body["input_json"]),
                "artifacts": {},
                "storage": {},
            }
            return httpx.Response(201, json={"job": self.jobs[jid]})

        if method == "GET" and path == "/v1/jobs":
            mine = [j for j in self.jobs.values() if j["user_id"] == uid]
            return httpx.Response(200, json={"jobs": mine})

        if path.startswith("/v1/jobs/"):
            jid = path.split("/")[-1]
            job = self.jobs.get(jid)
            if not job or (job["user_id"] != uid and user["role"] != "operator"):
                return httpx.Response(404, json={"detail": "job not found"})
            if method == "GET":
                return httpx.Response(200, json={"job": job})
            if method == "PATCH":
                for k in ("status", "stage", "progress", "error"):
                    if k in body:
                        job[k] = body[k]
                return httpx.Response(200, json={"job": job})
            if method == "DELETE":
                del self.jobs[jid]
                return httpx.Response(204)

        if method == "POST" and path == "/v1/attachments":
            self.attachments[body["id"]] = dict(body)
            return httpx.Response(201, json={"attachment": body})

        if method == "GET" and path == "/v1/attachments":
            mine = [a for a in self.attachments.values() if a["user_id"] == uid]
            return httpx.Response(200, json={"attachments": mine})

        if method == "POST" and path == "/v1/templates":
            self.templates[body["id"]] = {**body, "_user_id": uid}
            return httpx.Response(201, json={"template": body})

        if method == "GET" and path == "/v1/templates":
            mine = [{k: v for k, v in t.items() if k != "_user_id"} for t in self.templates.values() if t["_user_id"] == uid]
            return httpx.Response(200, json={"templates": mine})

        return httpx.Response(404, json={"detail": "not found"})


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 32), (120, 40, 200)).save(buf, "PNG")
    return buf.getvalue()


def test_cloud_mode_auth_billing_jobs_attachments_and_zero_sql_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCloudBackend()
    transport = httpx.MockTransport(fake.handle)
    real_client = httpx.Client

    def _mock_client(*args, **kwargs):
        kwargs.pop("verify", None)
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    db_url = f"sqlite:///{(tmp_path / 'local-cache.db').as_posix()}"
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("CLOUD_API_URL", "https://cloud.test")
    monkeypatch.delenv("D1_WORKER_KEY", raising=False)
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cfg, "DATABASE_URL", db_url)
    monkeypatch.setattr(cfg, "CLOUD_API_URL", "https://cloud.test")
    monkeypatch.setattr(cfg, "D1_WORKER_KEY", "")
    monkeypatch.setattr(cloud_client.httpx, "Client", _mock_client)
    cloud_client.invalidate_me_cache()

    async def _noop_run(job_id: str) -> None:
        from omaishort import db

        db.update_job(job_id, status="done", stage="done", progress="done")

    monkeypatch.setattr("omaishort.main.run_job", _noop_run)

    from omaishort.main import app

    assert cloud_client.cloud_mode_enabled() is True

    with TestClient(app) as client:
        # 1. Register operator + creator via Cloudflare Worker REST API
        op = client.post("/auth/register", json={"email": "op@test.com", "password": "password123"})
        assert op.status_code == 201
        assert op.json()["user"]["role"] == "operator"

        c1 = client.post("/auth/register", json={"email": "user1@test.com", "password": "password123"})
        assert c1.status_code == 201
        c1_data = c1.json()
        assert c1_data["user"]["role"] == "creator"
        assert c1_data["user"]["billing"]["credits_remaining"] == 2
        headers = {"Authorization": f"Bearer {c1_data['access_token']}"}

        # 2. Upload attachment -> saved locally AND synced to cloud D1 with content_b64
        att = client.post("/attachments?kind=face", files={"file": ("face.png", _png_bytes(), "image/png")}, headers=headers)
        assert att.status_code == 201
        assert len(fake.attachments) == 1
        assert next(iter(fake.attachments.values()))["content_b64"]

        # 3. Create job -> credit held on cloud, job metadata synced to cloud, background update_job synced to cloud
        job_res = client.post(
            "/jobs",
            json={
                "mode": "script",
                "kind": "drama",
                "text": "Một câu chuyện kịch tính ngắn kiểm tra đồng bộ đám mây.",
                "target_seconds": 30,
                "language": "vi",
            },
            headers=headers,
        )
        assert job_res.status_code == 200, job_res.text
        job_id = job_res.json()["id"]
        assert job_id in fake.jobs
        assert fake.jobs[job_id]["status"] == "done"

        # 4. Listing jobs returns cloud job + local storage status (mp4_ready=False since noop)
        listed = client.get("/jobs", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["jobs"][0]["id"] == job_id
        assert listed.json()["jobs"][0]["storage"]["mp4_ready"] is False

        # 5. Credits exhausted returns 402 from cloud enforcement
        client.post(
            "/jobs",
            json={"mode": "script", "kind": "drama", "text": "Câu chuyện thứ hai tiêu nốt credit cuối.", "target_seconds": 30, "language": "vi"},
            headers=headers,
        )
        exhausted = client.post(
            "/jobs",
            json={"mode": "script", "kind": "drama", "text": "Câu chuyện thứ ba phải bị chặn 402.", "target_seconds": 30, "language": "vi"},
            headers=headers,
        )
        assert exhausted.status_code == 402

        # 6. Verify ZERO raw SQL admin key was ever transmitted
        assert fake.seen_raw_keys == []
