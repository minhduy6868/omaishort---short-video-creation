from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from omaishort import config
from omaishort.engine.fallback import fallback_analyze, fallback_plan
from omaishort.engine.kenburns import ffmpeg_path
from omaishort.engine.video_reverse import (
    apply_blueprint_to_storyboard,
    apply_blueprint_to_structure,
    delete_blueprint,
    list_blueprints,
    load_blueprint,
    merge_template_brief,
    reverse_engineer_video,
)
from omaishort_schema.models import Camera, Genre, StoryInput, StoryMode, VideoKind


def _make_sample_video(dest: Path) -> Path:
    """Create a tiny 6-second 3-shot synthetic MP4 (dark red -> bright blue -> dark green) + tone audio."""
    cmd = [
        ffmpeg_path(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "color=c=#220505:s=180x320:d=2:r=15",
        "-f",
        "lavfi",
        "-i",
        "color=c=#1e90ff:s=180x320:d=2:r=15",
        "-f",
        "lavfi",
        "-i",
        "color=c=#083010:s=180x320:d=2:r=15",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=6",
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map",
        "[v]",
        "-map",
        "3:a",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(dest),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"ffmpeg failed: {res.stderr}"
    return dest


def test_reverse_engineer_video_extracts_shots_and_video_md(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    sample = _make_sample_video(tmp_path / "sample.mp4")

    bp = asyncio.run(
        reverse_engineer_video(
            sample,
            owner_id="user_test",
            name="Viral Sample",
            language="vi",
            use_vlm=False,
            transcribe=False,
        )
    )

    assert bp.id.startswith("tpl_")
    assert bp.name == "Viral Sample"
    assert bp.width == 180 and bp.height == 320
    assert bp.aspect_ratio == "9:16"
    assert bp.duration_sec >= 5.5
    assert bp.has_audio is True
    assert bp.speech_ratio > 0.5
    assert len(bp.shots) >= 3
    assert all(shot.frame_rel for shot in bp.shots)
    assert "# VIDEO.md — Viral Sample" in bp.video_md
    assert "Beat timing target:" in bp.script_brief
    assert set(bp.beat_durations.keys()) == {"hook", "conflict", "rising_action", "twist", "ending"}

    # Persistence round-trip
    loaded = load_blueprint("user_test", bp.id)
    assert loaded is not None
    assert loaded.id == bp.id
    listed = list_blueprints("user_test")
    assert any(item.id == bp.id for item in listed)
    assert delete_blueprint("user_test", bp.id) is True
    assert load_blueprint("user_test", bp.id) is None


def test_apply_blueprint_respects_editorial_and_drama_invariants(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    sample = _make_sample_video(tmp_path / "sample.mp4")
    bp = asyncio.run(reverse_engineer_video(sample, owner_id="cli", use_vlm=False, transcribe=False))
    # Force a close_up lens in the blueprint to verify editorial clamping.
    bp.beat_lenses["hook"] = [
        {"camera": "close_up", "motion": "zoom_in"},
        {"camera": "close_up", "motion": "pan_right"},
    ]

    news_story = StoryInput(
        mode=StoryMode.script,
        kind=VideoKind.news,
        genre=Genre.news,
        text=(
            "Giá xăng tăng mạnh đầu tuần.\n\n"
            "Nhiều doanh nghiệp vận tải lo ngại chi phí.\n\n"
            "Bộ Công Thương công bố mức điều chỉnh mới.\n\n"
            "Chuyên gia chỉ ra nguồn cung quốc tế biến động.\n\n"
            "Người tiêu dùng được khuyến nghị theo dõi kỳ điều hành tới."
        ),
        target_seconds=60,
        language="vi",
        reference_template_id=bp.id,
    )
    bible, structure = fallback_analyze(news_story)
    scaled_struct = apply_blueprint_to_structure(structure, bp, 60.0)
    total_beats = (
        scaled_struct.hook_sec
        + scaled_struct.conflict_sec
        + scaled_struct.rising_sec
        + scaled_struct.twist_sec
        + scaled_struct.ending_sec
    )
    assert abs(total_beats - 60.0) < 0.25

    board = fallback_plan(news_story, bible, scaled_struct)
    apply_blueprint_to_storyboard(board, bp)
    # Editorial news MUST NEVER receive close_up shots, and every shot must share its scene still_id.
    for scene in board.scenes:
        assert all(shot.still_id == scene.still_id for shot in scene.shots)
        assert all(shot.camera != Camera.close_up for shot in scene.shots)

    merged = merge_template_brief("Giữ giọng sắc sảo", bp)
    assert "Giữ giọng sắc sảo" in merged
    assert bp.name in merged
    assert len(merged) <= 2000


def test_templates_api_reverse_list_read_delete(tmp_path: Path, monkeypatch) -> None:
    db_url = f"sqlite:///{(tmp_path / 'omaishort.db').as_posix()}"
    monkeypatch.setenv("AUTH_SECRET", "unit-test-secret-unit-test-secret")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "DATABASE_URL", db_url)
    monkeypatch.setattr(config, "D1_WORKER_URL", "")

    from omaishort import db
    from omaishort.main import app

    db.init_db()
    sample = _make_sample_video(tmp_path / "api_sample.mp4")

    with TestClient(app) as client:
        reg = client.post(
            "/auth/register",
            json={"email": "rev@example.com", "password": "password123", "display_name": "Rev"},
        )
        assert reg.status_code in (200, 201), reg.text
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        with sample.open("rb") as fh:
            resp = client.post(
                "/templates/reverse?name=DemoTpl&language=vi&use_vlm=false&transcribe=false",
                headers=headers,
                files={"file": ("api_sample.mp4", fh, "video/mp4")},
            )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        tid = data["id"]
        assert data["name"] == "DemoTpl"
        assert len(data["shots"]) >= 3

        # Keyframe image is served via authenticated /files/templates/...
        frame_rel = data["shots"][0]["frame_rel"]
        assert frame_rel
        img_resp = client.get(f"/files/{frame_rel}", headers=headers)
        assert img_resp.status_code == 200
        assert len(img_resp.content) > 100

        listed = client.get("/templates", headers=headers)
        assert listed.status_code == 200
        assert any(row["id"] == tid for row in listed.json()["templates"])

        got = client.get(f"/templates/{tid}", headers=headers)
        assert got.status_code == 200
        assert got.json()["id"] == tid

        deleted = client.delete(f"/templates/{tid}", headers=headers)
        assert deleted.status_code == 204

        missing = client.get(f"/templates/{tid}", headers=headers)
        assert missing.status_code == 404
