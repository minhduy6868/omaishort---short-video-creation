from io import BytesIO

import os
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from omaishort_schema.models import AttachmentKind, AttachmentLink, StoryInput


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (48, 48), (180, 50, 30)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "unit-test-secret-unit-test-secret")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'omaishort.db').as_posix()}")
    import omaishort.config as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cfg, "DATABASE_URL", os.environ["DATABASE_URL"])
    from omaishort.main import app

    with TestClient(app) as test_client:
        yield test_client


def _register(client: TestClient, email: str, password: str = "password1") -> dict:
    res = client.post("/auth/register", json={"email": email, "password": password, "display_name": email.split("@")[0]})
    assert res.status_code == 201, res.text
    return res.json()


def test_health_is_public(client: TestClient):
    from omaishort import db

    assert client.get("/health").json()["status"] == "ok"
    assert not db.is_postgres()


def test_providers_is_public(client: TestClient):
    res = client.get("/providers")
    assert res.status_code == 200
    body = res.json()
    assert "drama_motion" in body
    assert "image" in body
    assert "video" in body
    assert body["drama_motion"] in {"kenburns", "grok", "grok_hub", "hf", "wavespeed", "pollinations"}


def test_jobs_require_auth(client: TestClient):
    res = client.post(
        "/jobs",
        json={"text": "hello world this is a drama story", "kind": "drama"},
    )
    assert res.status_code == 401


def test_register_login_me_cookie(client: TestClient):
    payload = _register(client, "Op@example.com")
    assert payload["user"]["email"] == "op@example.com"
    assert payload["user"]["role"] == "operator"
    assert payload["token_type"] == "bearer"
    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == payload["user"]["id"]


def test_second_user_is_creator_and_cannot_read_foreign_job(client: TestClient, monkeypatch):
    first = _register(client, "op@example.com")
    client.post("/auth/logout")
    second = _register(client, "creator@example.com")
    assert second["user"]["role"] == "creator"

    async def _skip(job_id: str) -> None:
        return None

    monkeypatch.setattr("omaishort.main.run_job", _skip)
    created = client.post(
        "/jobs",
        json={"text": "hello world this is a drama story", "kind": "drama"},
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )
    assert created.status_code == 200
    job_id = created.json()["id"]
    denied = client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {second['access_token']}"})
    assert denied.status_code == 404
    allowed = client.get(f"/jobs/{job_id}", headers={"Authorization": f"Bearer {first['access_token']}"})
    assert allowed.status_code == 200
    assert allowed.json()["user_id"] == first["user"]["id"]
    assert "input_json" not in allowed.json()


def test_refresh_rotates_and_reuse_revokes(client: TestClient):
    payload = _register(client, "op@example.com")
    old = payload["refresh_token"]
    again = client.post("/auth/refresh", json={"refresh_token": old})
    assert again.status_code == 200
    new = again.json()["refresh_token"]
    assert new != old
    reused = client.post("/auth/refresh", json={"refresh_token": old})
    assert reused.status_code == 401
    family = client.post("/auth/refresh", json={"refresh_token": new})
    assert family.status_code == 401


def test_logout_revokes_refresh(client: TestClient):
    payload = _register(client, "op@example.com")
    gone = client.post("/auth/logout", json={"refresh_token": payload["refresh_token"]})
    assert gone.status_code == 204
    cookies = gone.headers.get("set-cookie", "").lower()
    assert "omaishort_at" in cookies
    assert "omaishort_rt" in cookies
    refresh = client.post("/auth/refresh", json={"refresh_token": payload["refresh_token"]})
    assert refresh.status_code == 401
    still = client.get("/auth/me", headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert still.status_code == 200


def test_files_hide_db_and_secret(client: TestClient, tmp_path):
    _register(client, "op@example.com")
    (tmp_path / ".auth_secret").write_text("nope", encoding="utf-8")
    assert client.get("/files/omaishort.db").status_code == 404
    assert client.get("/files/.auth_secret").status_code == 404


def test_operator_can_read_cli_job(client: TestClient):
    from omaishort import db

    payload = _register(client, "op@example.com")
    db.create_job("clidryrun01", StoryInput(text="hello world this is a drama story").model_dump_json())
    res = client.get("/jobs/clidryrun01", headers={"Authorization": f"Bearer {payload['access_token']}"})
    assert res.status_code == 200


def test_upload_png_and_reject_svg(client: TestClient):
    _register(client, "op@example.com")
    ok = client.post(
        "/attachments?kind=face",
        files={"file": ("wife.png", _png(), "image/png")},
    )
    assert ok.status_code == 201
    body = ok.json()
    assert body["kind"] == AttachmentKind.face.value
    assert "sha256" in body
    listed = client.get("/attachments")
    assert listed.status_code == 200
    assert listed.json()["attachments"][0]["id"] == body["id"]
    bad = client.post(
        "/attachments?kind=face",
        files={"file": ("x.svg", b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "image/svg+xml")},
    )
    assert bad.status_code == 400


def test_story_input_attachments_unique():
    with pytest.raises(Exception):
        StoryInput(
            text="hello world this is a drama story",
            attachments=[
                AttachmentLink(id="abcdefghijkl"),
                AttachmentLink(id="abcdefghijkl"),
            ],
        )


def test_unknown_login_is_generic(client: TestClient):
    res = client.post("/auth/login", json={"email": "nobody@example.com", "password": "password1"})
    assert res.status_code == 401
    assert res.json()["detail"] == "invalid email or password"


def test_malformed_bearer_is_401_not_500(client: TestClient):
    _register(client, "op@example.com")
    for token in ("not-a-jwt", "a.b", "a.b.c", "%%%.%%%.%%%"):
        res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401, token


def test_locked_user_cannot_use_existing_jwt(client: TestClient):
    from datetime import datetime, timedelta, timezone

    from omaishort import db

    payload = _register(client, "op@example.com")
    token = payload["access_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    db.update_user(payload["user"]["id"], failed_logins=5, locked_until=future)

    blocked = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert blocked.status_code == 401
