"""Trial, credits hold/refund, checkout, and admin grant."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


async def _skip_run_job(_job_id: str) -> None:
    return None


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "unit-test-secret-unit-test-secret")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'omaishort.db').as_posix()}")
    import omaishort.config as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cfg, "DATABASE_URL", os.environ["DATABASE_URL"])
    from omaishort.main import app

    monkeypatch.setattr("omaishort.main.run_job", _skip_run_job)
    with TestClient(app) as test_client:
        yield test_client


def _register(client: TestClient, email: str, password: str = "password1") -> dict:
    res = client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )
    assert res.status_code == 201, res.text
    return res.json()


def _auth(payload: dict) -> dict[str, str]:
    return {"Authorization": f"Bearer {payload['access_token']}"}


def test_creator_register_gets_trial(client: TestClient):
    _register(client, "admin@example.com")
    creator = _register(client, "creator@example.com")
    billing = creator["user"]["billing"]
    assert billing is not None
    assert billing["plan_code"] == "trial"
    assert billing["status"] == "trial"
    assert billing["credits_remaining"] == 3
    ends = datetime.fromisoformat(billing["ends_at"])
    if ends.tzinfo is None:
        ends = ends.replace(tzinfo=timezone.utc)
    assert ends > datetime.now(timezone.utc) + timedelta(days=13)


def test_operator_jobs_bypass_credits(client: TestClient):
    operator = _register(client, "admin@example.com")
    assert operator["user"]["role"] == "operator"
    res = client.post(
        "/jobs",
        json={"text": "hello world this is a drama story for operator", "kind": "drama"},
        headers=_auth(operator),
    )
    assert res.status_code == 200, res.text
    me = client.get("/auth/me", headers=_auth(operator))
    assert me.status_code == 200
    # Operator may have null billing; still not blocked.
    assert me.json()["role"] == "operator"


def test_hold_and_refund_on_failed_job(client: TestClient):
    from omaishort import db
    from omaishort.billing import refund_job_credit

    _register(client, "admin@example.com")
    creator = _register(client, "creator@example.com")
    headers = _auth(creator)
    before = client.get("/billing/me", headers=headers).json()["billing"]["credits_remaining"]
    assert before == 3

    created = client.post(
        "/jobs",
        json={"text": "hello world this is a drama story for credit hold", "kind": "drama"},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    job_id = created.json()["id"]
    after_hold = client.get("/billing/me", headers=headers).json()["billing"]["credits_remaining"]
    assert after_hold == 2

    refund_job_credit(creator["user"]["id"], job_id)
    db.update_job(job_id, status="failed", progress="failed", error="test fail")
    restored = client.get("/billing/me", headers=headers).json()["billing"]["credits_remaining"]
    assert restored == 3

    # Second refund is a no-op
    refund_job_credit(creator["user"]["id"], job_id)
    assert client.get("/billing/me", headers=headers).json()["billing"]["credits_remaining"] == 3


def test_exhausted_credits_return_402_then_grant(client: TestClient):
    admin = _register(client, "admin@example.com")
    creator = _register(client, "creator@example.com")
    headers = _auth(creator)

    for i in range(3):
        res = client.post(
            "/jobs",
            json={"text": f"hello world drama story number {i} for exhausting credits", "kind": "drama"},
            headers=headers,
        )
        assert res.status_code == 200, res.text

    blocked = client.post(
        "/jobs",
        json={"text": "hello world drama story that should be blocked by credits", "kind": "drama"},
        headers=headers,
    )
    assert blocked.status_code == 402, blocked.text
    body = blocked.json()
    assert body["detail"] == "credits exhausted"
    assert body["billing"]["credits_remaining"] == 0

    grant = client.post(
        f"/admin/billing/users/{creator['user']['id']}/grant",
        json={"credits": 2, "note": "test grant", "extend_days": 7},
        headers=_auth(admin),
    )
    assert grant.status_code == 200, grant.text
    assert grant.json()["billing"]["credits_remaining"] == 2

    again = client.post(
        "/jobs",
        json={"text": "hello world drama story after admin grant should work", "kind": "drama"},
        headers=headers,
    )
    assert again.status_code == 200, again.text


def test_checkout_and_admin_paid_activates_starter(client: TestClient):
    _register(client, "admin@example.com")
    admin = client.post("/auth/login", json={"email": "admin@example.com", "password": "password1"}).json()
    creator = _register(client, "creator@example.com")
    headers = _auth(creator)

    checkout = client.post("/billing/checkout", json={"plan_code": "starter"}, headers=headers)
    assert checkout.status_code == 201, checkout.text
    order = checkout.json()["order"]
    assert order["status"] == "pending"
    assert order["plan_code"] == "starter"
    assert order["amount_vnd"] == 199000

    conflict = client.post("/billing/checkout", json={"plan_code": "pro"}, headers=headers)
    assert conflict.status_code == 409

    paid = client.patch(
        f"/admin/billing/orders/{order['id']}",
        json={"status": "paid"},
        headers=_auth(admin),
    )
    assert paid.status_code == 200, paid.text
    billing = paid.json()["billing"]
    assert billing["plan_code"] == "starter"
    assert billing["status"] == "active"
    assert billing["credits_remaining"] == 20


def test_trial_only_once(client: TestClient):
    from omaishort.billing import ensure_trial

    _register(client, "admin@example.com")
    creator = _register(client, "creator@example.com")
    uid = creator["user"]["id"]
    assert ensure_trial(uid) is None
    me = client.get("/billing/me", headers=_auth(creator)).json()
    assert me["billing"]["plan_code"] == "trial"
    assert me["billing"]["credits_remaining"] == 3
