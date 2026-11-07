"""Full-flow E2E tests: Login -> Admin Console -> Cloudflare D1 persistence -> 7-stage Pipeline -> 1080x1920 MP4 -> Local Video Storage."""

from __future__ import annotations

from io import BytesIO
import os
import shutil
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from omaishort.engine.kenburns import ffmpeg_path, has_audio_stream, probe_video_size


def _make_png(color: tuple[int, int, int] = (210, 65, 40), size: tuple[int, int] = (128, 128)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_SECRET", "full-flow-test-secret-key-32bytes")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'omaishort.db').as_posix()}")
    monkeypatch.setenv("HF_I2V_ENABLED", "0")
    monkeypatch.setenv("POLLINATIONS_VIDEO_ENABLED", "0")
    monkeypatch.setenv("WAVESPEED_ENABLED", "0")
    import omaishort.config as cfg

    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path)
    monkeypatch.setattr(cfg, "DATABASE_URL", os.environ["DATABASE_URL"])
    monkeypatch.setattr(cfg, "POLLINATIONS_ENABLED", False)
    monkeypatch.setattr(cfg, "GROK_WEB_ENABLED", False)
    monkeypatch.setattr(cfg, "CHATGPT_WEB_ENABLED", False)
    import omaishort.providers.chatgpt_web as cweb
    import omaishort.providers.grok_web as gweb
    import omaishort.providers.llm as llm_mod

    monkeypatch.setattr(cweb, "CHATGPT_WEB_ENABLED", False)
    monkeypatch.setattr(gweb, "GROK_WEB_ENABLED", False)
    monkeypatch.setattr(llm_mod, "CHATGPT_WEB_ENABLED", False)
    monkeypatch.setattr(llm_mod, "GROK_WEB_ENABLED", False)
    from omaishort.main import app

    with TestClient(app) as test_client:
        yield test_client


def _register(client: TestClient, email: str, password: str = "password123") -> dict:
    res = client.post(
        "/auth/register",
        json={"email": email, "password": password, "display_name": email.split("@")[0]},
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_admin_console_roles_lockout_and_cloudflare_settings(client: TestClient):
    op_session = _register(client, "admin@example.com")
    op_headers = {"Authorization": f"Bearer {op_session['access_token']}"}
    assert op_session["user"]["role"] == "operator"

    creator_session = _register(client, "creator@example.com")
    creator_headers = {"Authorization": f"Bearer {creator_session['access_token']}"}
    assert creator_session["user"]["role"] == "creator"
    client.cookies.clear()

    # Creator is forbidden from all admin endpoints
    for path in ("/admin/overview", "/admin/users", "/admin/jobs", "/admin/storage"):
        assert client.get(path, headers=creator_headers).status_code == 403, path
    assert client.put("/admin/settings", json={"signup_enabled": False}, headers=creator_headers).status_code == 403

    # Operator reads overview & users
    overview = client.get("/admin/overview", headers=op_headers)
    assert overview.status_code == 200
    ov_body = overview.json()
    assert ov_body["stats"]["users_total"] == 2
    assert ov_body["stats"]["operators_total"] == 1
    assert ov_body["settings"]["signup_enabled"] is True

    users_res = client.get("/admin/users", headers=op_headers)
    assert users_res.status_code == 200
    users_list = users_res.json()["users"]
    assert len(users_list) == 2
    assert all("password_hash" not in u for u in users_list)

    # Cannot demote the last operator or lock self
    op_id = op_session["user"]["id"]
    creator_id = creator_session["user"]["id"]
    assert client.patch(f"/admin/users/{op_id}", json={"role": "creator"}, headers=op_headers).status_code == 400
    assert client.patch(f"/admin/users/{op_id}", json={"locked": True}, headers=op_headers).status_code == 400

    # Close signup via D1 settings table and verify registration is blocked
    closed = client.put("/admin/settings", json={"signup_enabled": False, "site_theme": "soft"}, headers=op_headers)
    assert closed.status_code == 200
    assert closed.json()["signup_enabled"] is False
    assert closed.json()["site_theme"] == "soft"
    assert client.get("/site/theme").json()["theme"] == "soft"

    blocked_reg = client.post(
        "/auth/register",
        json={"email": "newuser@example.com", "password": "password123"},
    )
    assert blocked_reg.status_code == 403

    # Re-open signup and register third user
    reopened = client.put("/admin/settings", json={"signup_enabled": True, "site_theme": "brutal"}, headers=op_headers)
    assert reopened.status_code == 200
    assert reopened.json()["signup_enabled"] is True
    third = _register(client, "newuser@example.com")
    assert third["user"]["role"] == "creator"
    client.cookies.clear()

    # Lock creator account from Admin Console
    locked = client.patch(f"/admin/users/{creator_id}", json={"locked": True}, headers=op_headers)
    assert locked.status_code == 200
    assert locked.json()["user"]["locked"] is True
    assert client.get("/auth/me", headers=creator_headers).status_code == 401
    assert client.post("/auth/login", json={"email": "creator@example.com", "password": "password123"}).status_code == 429

    # Unlock creator account
    unlocked = client.patch(f"/admin/users/{creator_id}", json={"locked": False}, headers=op_headers)
    assert unlocked.status_code == 200
    assert unlocked.json()["user"]["locked"] is False
    assert client.get("/auth/me", headers=creator_headers).status_code == 200


def test_cloudflare_d1_attachment_persistence_and_restore(client: TestClient, tmp_path: Path):
    from omaishort import db

    session = _register(client, "admin@example.com")
    headers = {"Authorization": f"Bearer {session['access_token']}"}
    png_bytes = _make_png((40, 120, 220), (64, 64))

    up = client.post(
        "/attachments?kind=face",
        files={"file": ("protagonist.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert up.status_code == 201, up.text
    att = up.json()
    assert "content_b64" not in att

    # Verify Cloudflare D1 row holds the base64 backup
    raw_row = db.get_attachment(att["id"])
    assert raw_row is not None
    assert raw_row.get("content_b64")

    # Simulate fresh local disk by deleting the local attachment file
    local_file = tmp_path / str(raw_row["rel_path"])
    assert local_file.is_file()
    local_file.unlink()
    assert not local_file.is_file()

    # Downloading or resolving the file automatically restores it from D1 content_b64
    dl = client.get(f"/attachments/{att['id']}/file", headers=headers)
    assert dl.status_code == 200
    assert dl.content == png_bytes
    assert local_file.is_file()


def _has_ffmpeg() -> bool:
    try:
        return bool(ffmpeg_path())
    except Exception:
        return False


@pytest.mark.skipif(not _has_ffmpeg(), reason="ffmpeg is required for full MP4 render test")
def test_full_flow_login_to_rendered_mp4_and_local_storage_management(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from omaishort.engine.fallback import fallback_analyze, fallback_plan
    from omaishort.engine.image_prompts import fill_image_prompts
    from omaishort.providers.image import PlaceholderImageProvider
    from omaishort.providers.tts import TTSResult, silence_audio

    # Keep the full pipeline 100% deterministic & offline while running real FFmpeg 1080x1920 render
    async def _fast_analyze(story):
        bible, structure = fallback_analyze(story)
        return bible, structure, "fallback"

    async def _fast_plan(story, bible, structure):
        board = fallback_plan(story, bible, structure)
        fill_image_prompts(board, bible)
        return board, "fallback"

    async def _fast_image(prompt: str, dest: Path, reference_images=None, *, skip_remote: bool = False, photo: bool = False):
        out = await PlaceholderImageProvider().generate(prompt, dest, reference_images)
        return out or dest, "placeholder"

    async def _fast_tts(text: str, dest: Path, language: str = "vi", voice_id: str | None = None):
        path = await silence_audio(dest, 3.0)
        return TTSResult(path=path, provider="silence", words=None)

    async def _fast_topic(text: str, language: str = "vi"):
        from omaishort.engine.brief_media import ArticlePage

        return ArticlePage(
            url="https://vi.wikipedia.org/wiki/Lam_phat",
            title="Lạm phát",
            text=(
                "Lạm phát là sự tăng mức giá chung một cách liên tục của hàng hóa và dịch vụ theo thời gian. "
                "Khi mức giá chung tăng cao, một đơn vị tiền tệ sẽ mua được ít hàng hóa và dịch vụ hơn so với trước đây. "
                "Ngân hàng trung ương thường điều hành chính sách tiền tệ và lãi suất để kiểm soát lạm phát. "
                "Nhiều người lầm tưởng giảm phát luôn tốt hơn lạm phát, nhưng giảm phát kéo dài có thể làm đình trệ nền kinh tế. "
                "Quản lý tài chính cá nhân và đa dạng hóa tài sản giúp bảo vệ sức mua trước biến động giá cả."
            ),
            image_urls=[],
        )

    monkeypatch.setattr("omaishort.pipeline.analyze_story", _fast_analyze)
    monkeypatch.setattr("omaishort.pipeline.plan_scenes", _fast_plan)
    monkeypatch.setattr("omaishort.pipeline.generate_image", _fast_image)
    monkeypatch.setattr("omaishort.providers.smart_image_search.generate_image", _fast_image)
    monkeypatch.setattr("omaishort.pipeline._remote_search_enabled", lambda: False)
    monkeypatch.setattr("omaishort.pipeline.synthesize_speech", _fast_tts)
    monkeypatch.setattr("omaishort.engine.compose.i2v_ready", lambda: False)
    monkeypatch.setattr("omaishort.providers.llm.llm_http_available", lambda: False)
    monkeypatch.setattr("omaishort.engine.brief_media.fetch_knowledge_topic", _fast_topic)

    # 1. Register / Login
    op = _register(client, "studio-admin@example.com")
    headers = {"Authorization": f"Bearer {op['access_token']}"}

    # 2. Upload face & logo attachments
    face_res = client.post(
        "/attachments?kind=face",
        files={"file": ("linh.png", _make_png((200, 90, 70)), "image/png")},
        headers=headers,
    )
    assert face_res.status_code == 201
    face_id = face_res.json()["id"]

    logo_res = client.post(
        "/attachments?kind=logo",
        files={"file": ("brand.png", _make_png((20, 20, 20), (64, 64)), "image/png")},
        headers=headers,
    )
    assert logo_res.status_code == 201
    logo_id = logo_res.json()["id"]

    # 3. Create Job via POST /jobs (runs full 7-stage pipeline in TestClient BackgroundTasks)
    create_res = client.post(
        "/jobs",
        json={
            "mode": "script",
            "kind": "drama",
            "text": (
                "Linh bị giám đốc chê bai giữa sảnh khách sạn sang trọng. "
                "Ông ta lớn tiếng đuổi cô ra ngoài trước mặt toàn bộ nhân viên. "
                "Nhưng đúng lúc đó đoàn xe hộ tống của tập đoàn dừng trước cửa chính. "
                "Tổng thư ký cúi đầu trao chiếc thẻ đen quyền lực cho Linh. "
                "Vị giám đốc tái mặt nhận ra người mình vừa sỉ nhục chính là chủ tịch mới."
            ),
            "target_seconds": 15,
            "genre": "drama",
            "drama_shape": "default",
            "language": "vi",
            "attachments": [
                {"id": face_id, "bind": "linh"},
                {"id": logo_id},
            ],
            "mix": {"bgm_enabled": False, "logo_enabled": True},
        },
        headers=headers,
    )
    assert create_res.status_code == 200, create_res.text
    job_id = create_res.json()["id"]

    # 4. Read completed job & verify all 7 stages + artifacts + storage metadata
    job_res = client.get(f"/jobs/{job_id}", headers=headers)
    assert job_res.status_code == 200
    job = job_res.json()
    assert job["status"] == "done", job.get("error")
    assert job["stage"] == "done"
    assert job["progress"] == "done"
    assert len(job["storyboard"]["scenes"]) == 5
    assert job["storage"]["mp4_ready"] is True
    assert job["storage"]["mp4_bytes"] > 1000
    assert job["storage"]["width"] == 1080
    assert job["storage"]["height"] == 1920

    # 5. Download MP4 & verify video/audio streams with ffprobe
    dl_res = client.get(f"/jobs/{job_id}/download", headers=headers)
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"].startswith("video/mp4")
    mp4_on_disk = tmp_path / "jobs" / job_id / "render" / "short.mp4"
    assert mp4_on_disk.is_file()
    assert probe_video_size(mp4_on_disk) == (1080, 1920)
    assert has_audio_stream(mp4_on_disk) is True

    # 5b. Test 5-Beat Content Drafting & Full Project Editing (Meta, Structure, AI Rewrite, Scene, Upload Still)
    draft_res = client.post(
        "/scripts/draft",
        json={
            "kind": "knowledge",
            "text": "Lạm phát và cách nó vận hành trong nền kinh tế",
            "language": "vi",
            "target_seconds": 90,
        },
        headers=headers,
    )
    assert draft_res.status_code == 200
    draft_data = draft_res.json()
    assert "structure" in draft_data
    assert all(k in draft_data["structure"] for k in ("hook", "conflict", "rising_action", "twist", "ending"))

    patch_meta_res = client.patch(
        f"/jobs/{job_id}",
        json={"title": "Chủ tịch ẩn danh tại khách sạn", "target_seconds": 30},
        headers=headers,
    )
    assert patch_meta_res.status_code == 200
    assert patch_meta_res.json()["storyboard"]["title"] == "Chủ tịch ẩn danh tại khách sạn"

    patch_struct_res = client.patch(
        f"/jobs/{job_id}/structure",
        json={
            "hook": "Mở màn gây sốc giữa sảnh khách sạn năm sao lúc nửa đêm.",
            "sync_scenes": True,
        },
        headers=headers,
    )
    assert patch_struct_res.status_code == 200
    assert "Mở màn gây sốc" in patch_struct_res.json()["structure"]["hook"]
    assert "Mở màn gây sốc" in patch_struct_res.json()["storyboard"]["scenes"][0]["dialogue_or_vo"]

    ai_rw_res = client.post(
        f"/jobs/{job_id}/ai-rewrite",
        json={"beat": "hook", "instruction": "Thêm chi tiết chiếc thẻ đen quyền lực", "sync_scenes": True},
        headers=headers,
    )
    assert ai_rw_res.status_code == 200
    assert "thẻ đen" in ai_rw_res.json()["structure"]["hook"].lower()

    patch_scene_res = client.patch(
        f"/jobs/{job_id}/scenes/2",
        json={
            "dialogue_or_vo": "Giám đốc sững sờ khi thấy đoàn xe hộ tống dừng trước sảnh.",
            "image_prompt": "Custom cinematic lobby shot with black limousine convoy outside",
            "camera": "close_up",
            "motion": "zoom_in",
            "duration_sec": 6.5,
        },
        headers=headers,
    )
    assert patch_scene_res.status_code == 200
    sc2 = patch_scene_res.json()["storyboard"]["scenes"][1]
    assert "sững sờ" in sc2["dialogue_or_vo"]
    assert sc2["image_prompt"] == "Custom cinematic lobby shot with black limousine convoy outside"
    assert sc2["shots"][0]["camera"] == "close_up"

    bad_still_res = client.post(
        f"/jobs/{job_id}/scenes/2/upload-still",
        files={"file": ("not_an_image.png", b"not-a-valid-image", "image/png")},
        headers=headers,
    )
    assert bad_still_res.status_code in (400, 415)

    up_still_res = client.post(
        f"/jobs/{job_id}/scenes/2/upload-still",
        files={"file": ("custom_scene2.png", _make_png((40, 120, 200), (600, 900)), "image/png")},
        headers=headers,
    )
    assert up_still_res.status_code == 200
    assert "still_02" in up_still_res.json()["artifacts"]

    # 5c. Test Pause, Regenerate Scene Still from Grok / ChatGPT, Fill Missing Stills, and Resume
    pause_res = client.post(f"/jobs/{job_id}/pause", headers=headers)
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "paused"

    grok_still_res = client.post(
        f"/jobs/{job_id}/scenes/1/regenerate-still",
        json={"prompt": "Luxury hotel lobby chandelier", "source": "grok"},
        headers=headers,
    )
    assert grok_still_res.status_code == 200
    assert "still_01" in grok_still_res.json()["artifacts"]

    chatgpt_still_res = client.post(
        f"/jobs/{job_id}/scenes/3/regenerate-still",
        json={"prompt": "Black VIP limousine convoy arriving at hotel", "source": "chatgpt"},
        headers=headers,
    )
    assert chatgpt_still_res.status_code == 200
    assert "still_03" in chatgpt_still_res.json()["artifacts"]

    fill_res = client.post(
        f"/jobs/{job_id}/fill-stills",
        json={"source": "grok", "force_all": False},
        headers=headers,
    )
    assert fill_res.status_code == 200

    resume_res = client.post(
        f"/jobs/{job_id}/resume",
        json={"regenerate_stills": False},
        headers=headers,
    )
    assert resume_res.status_code == 200
    resumed_job = client.get(f"/jobs/{job_id}", headers=headers).json()
    assert resumed_job["status"] == "done"
    assert mp4_on_disk.is_file()

    # 6. Verify Local Video Storage API & compaction
    videos_res = client.get("/storage/videos", headers=headers)
    assert videos_res.status_code == 200
    videos = videos_res.json()["videos"]
    assert any(v["id"] == job_id and v["storage"]["mp4_ready"] is True for v in videos)

    # Add dummy intermediate files and test compacting
    sourced_dir = tmp_path / "jobs" / job_id / "stills" / "sourced"
    sourced_dir.mkdir(parents=True, exist_ok=True)
    (sourced_dir / "raw_photo.jpg").write_bytes(b"x" * 20480)
    (tmp_path / "jobs" / job_id / "render" / "temp_scene.mp4").write_bytes(b"y" * 10240)

    compact_res = client.post(f"/jobs/{job_id}/compact", headers=headers)
    assert compact_res.status_code == 200
    compacted = compact_res.json()
    assert compacted["compacted"] is True
    assert compacted["freed_bytes"] >= 30720
    assert compacted["mp4_ready"] is True
    assert mp4_on_disk.is_file()

    # 7. Test orphan directory detection & cleanup via Admin Storage API
    orphan_dir = tmp_path / "jobs" / "orphan123456"
    orphan_dir.mkdir(parents=True, exist_ok=True)
    (orphan_dir / "leftover.bin").write_bytes(b"z" * 8192)

    st_before = client.get("/admin/storage", headers=headers).json()
    assert "orphan123456" in st_before["summary"]["orphan_job_ids"]

    clean_res = client.post(
        "/admin/storage/cleanup",
        json={"remove_orphans": True, "compact_done": True},
        headers=headers,
    )
    assert clean_res.status_code == 200
    clean_body = clean_res.json()
    assert "orphan123456" in clean_body["removed_orphans"]
    assert not orphan_dir.exists()
    assert mp4_on_disk.is_file()

    # 8. Delete local video files while keeping D1 history (keep_db=true), then delete DB record
    del_local = client.delete(f"/admin/jobs/{job_id}?keep_db=true", headers=headers)
    assert del_local.status_code == 200
    assert del_local.json()["deleted_local"] is True
    assert del_local.json()["deleted_db"] is False
    assert not mp4_on_disk.exists()
    assert client.get(f"/jobs/{job_id}", headers=headers).status_code == 200

    del_all = client.delete(f"/admin/jobs/{job_id}", headers=headers)
    assert del_all.status_code == 200
    assert del_all.json()["deleted_db"] is True
    assert client.get(f"/jobs/{job_id}", headers=headers).status_code == 404
