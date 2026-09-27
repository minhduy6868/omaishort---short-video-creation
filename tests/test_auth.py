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


def test_gmail_dots_are_one_account(client: TestClient):
    first = _register(client, "Foo.Bar+tag@gmail.com")
    assert first["user"]["email"] == "foobar@gmail.com"
    again = client.post(
        "/auth/register",
        json={"email": "foo.bar@gmail.com", "password": "password1", "display_name": "again"},
    )
    assert again.status_code == 409
    assert "đã có tài khoản" in again.json()["detail"]
    logged = client.post("/auth/login", json={"email": "foobar@gmail.com", "password": "password1"})
    assert logged.status_code == 200
    assert logged.json()["user"]["id"] == first["user"]["id"]


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
    from datetime import datetime, timedelta, timezone

    from omaishort import db
    from omaishort.auth import hash_refresh

    payload = _register(client, "op@example.com")
    old = payload["refresh_token"]
    again = client.post("/auth/refresh", json={"refresh_token": old})
    assert again.status_code == 200
    new = again.json()["refresh_token"]
    assert new != old
    # A second caller still holding the old cookie must not kill the new session.
    reused = client.post("/auth/refresh", json={"refresh_token": old})
    assert reused.status_code == 401
    kept = client.post("/auth/refresh", json={"refresh_token": new})
    assert kept.status_code == 200
    newest = kept.json()["refresh_token"]
    row = db.get_refresh_by_hash(hash_refresh(new))
    assert row
    stale = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
    with db._lock:
        conn = db.connect()
        try:
            conn.execute("UPDATE refresh_tokens SET revoked_at = ? WHERE id = ?", (stale, row["id"]))
            conn.commit()
        finally:
            conn.close()
    stolen = client.post("/auth/refresh", json={"refresh_token": new})
    assert stolen.status_code == 401
    family = client.post("/auth/refresh", json={"refresh_token": newest})
    assert family.status_code == 200


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


def test_chatgpt_login_requires_account(client: TestClient):
    assert client.post("/providers/chatgpt-login").status_code == 401


def test_chatgpt_open_requires_account(client: TestClient):
    assert client.post("/providers/chatgpt-open").status_code == 401


def test_chatgpt_open_needs_saved_session(client: TestClient, monkeypatch):
    from omaishort.providers import chatgpt_web

    monkeypatch.setattr(chatgpt_web, "is_authed", lambda: False)
    _register(client, "chatgpt@example.com")
    res = client.post("/providers/chatgpt-open")
    assert res.status_code == 409


def test_elevenlabs_hub_requires_account(client: TestClient):
    assert client.get("/providers/elevenlabs").status_code == 401
    assert client.put("/providers/elevenlabs", json={"enabled": False}).status_code == 401


def test_elevenlabs_hub_masks_key_and_drives_tts(client: TestClient, monkeypatch):
    from omaishort.providers import elevenlabs_hub
    from omaishort.providers.tts import tts_providers

    secret = "sk_test_secret_key_value"

    def fake_voices(key: str):
        assert key == secret
        return [{"id": "voice1", "name": "Narrator"}]

    monkeypatch.setattr(elevenlabs_hub, "fetch_voices", fake_voices)
    _register(client, "hub@example.com")
    saved = client.put(
        "/providers/elevenlabs",
        json={"api_key": secret, "voice_id": "voice1", "enabled": True},
    )
    assert saved.status_code == 200, saved.text
    assert secret not in saved.text
    body = saved.json()
    assert body["enabled"] is True
    assert body["voice_id"] == "voice1"
    assert body["key_hint"] == "…alue"
    assert "api_key" not in body
    assert [item.name for item in tts_providers("vi-female")][0] == "elevenlabs"

    cleared = client.put("/providers/elevenlabs", json={"api_key": ""})
    assert cleared.status_code == 200
    assert cleared.json()["configured"] is False
    assert elevenlabs_hub.api_key() == ""
    assert [item.name for item in tts_providers("vi-female")] == ["edge-tts"]

    anon = client.put(
        "/providers/elevenlabs",
        json={"mode": "anonymous", "enabled": True, "voice_id": "aN7cv9yXNrfIR87bDmyD"},
    )
    assert anon.status_code == 200, anon.text
    assert anon.json()["mode"] == "anonymous"
    assert anon.json()["enabled"] is True
    assert len(anon.json()["voices"]) > 1
    assert any(item["name"].startswith("Rachel") for item in anon.json()["voices"])
    assert "api_key" not in anon.text
    assert [item.name for item in tts_providers("vi-female")][0] == "elevenlabs"


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
