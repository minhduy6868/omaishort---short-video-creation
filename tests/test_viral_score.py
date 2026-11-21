from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from omaishort.engine.viral_score import CAPTION_PRESETS, VIRAL_PRESETS, evaluate_viral_script
from omaishort_schema.models import SubtitleStyle


def test_viral_score_penalizes_weak_cliche_and_rewards_curiosity_gap() -> None:
    weak = evaluate_viral_script(
        "Xin chào các bạn, hôm nay chúng ta sẽ tìm hiểu về chủ đề này. Đó là nội dung chính.",
        kind="knowledge",
        language="vi",
        target_seconds=60,
    )
    strong = evaluate_viral_script(
        "",
        structure={
            "hook": "90% người gửi tiết kiệm đang mất 8% sức mua mỗi năm mà không hề biết vì sao.",
            "conflict": "Giá thực phẩm và tiền thuê nhà tăng nhanh gấp đôi lãi suất ngân hàng khiến tiền nhàn rỗi bốc hơi từng tháng.",
            "rising_action": "Khi ngân hàng trung ương bơm thêm tiền ra thị trường, dòng tiền đổ vào nhà đất và chợ thực phẩm đẩy giá leo thang từng bước. Nhưng điều ít ai để ý là hóa đơn siêu thị mới là thước đo thật.",
            "twist": "Sự thật trái ngược là giảm phát kéo dài còn nguy hiểm hơn lạm phát vì doanh nghiệp ngừng đầu tư và người lao động mất việc.",
            "ending": "Hãy giữ 3 tháng chi phí trong tiền mặt và phân bổ phần dư vào tài sản sinh lời để bảo vệ sức mua bền vững.",
        },
        kind="knowledge",
        language="vi",
        target_seconds=45,
    )

    assert strong["score"] > weak["score"] + 25
    assert strong["grade"] in {"S", "A"}
    assert weak["grade"] in {"B", "C"}
    assert len(weak["tips"]) >= 2
    assert set(strong["metrics"].keys()) == {"hook", "curiosity", "pacing", "value", "visual"}


def test_presets_are_valid_subtitle_styles_and_cover_all_three_kinds() -> None:
    assert set(VIRAL_PRESETS.keys()) == {"drama", "knowledge", "news"}
    for kind, items in VIRAL_PRESETS.items():
        assert len(items) >= 2, kind
        for item in items:
            assert item["brief"].strip()

    assert len(CAPTION_PRESETS) >= 4
    for preset in CAPTION_PRESETS:
        parsed = SubtitleStyle.model_validate(preset["subtitle"])
        assert 24 <= parsed.font_size <= 120


def test_viral_score_and_presets_api(tmp_path: Path, monkeypatch) -> None:
    import omaishort.config as cfg
    from omaishort import db

    db_url = f"sqlite:///{(tmp_path / 'omaishort.db').as_posix()}"
    monkeypatch.setenv("AUTH_SECRET", "unit-test-secret-unit-test-secret")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(cfg, "DATABASE_URL", db_url)
    monkeypatch.setattr(cfg, "CLOUD_API_URL", "")
    monkeypatch.setattr(cfg, "D1_WORKER_URL", "")
    monkeypatch.setattr(cfg, "D1_WORKER_KEY", "")
    db.init_db()

    from omaishort.main import app

    with TestClient(app) as client:
        presets = client.get("/scripts/presets")
        assert presets.status_code == 200
        body = presets.json()
        assert "viral_presets" in body and "caption_presets" in body

        reg = client.post("/auth/register", json={"email": "viral@test.com", "password": "password123"})
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        scored = client.post(
            "/scripts/viral-score",
            json={
                "kind": "drama",
                "language": "vi",
                "target_seconds": 30,
                "text": "2 giờ sáng tôi nhặt điện thoại anh trên bàn bếp. Màn hình khóa là ảnh cưới nhưng tin nhắn lại của người lạ.",
            },
            headers=headers,
        )
        assert scored.status_code == 200
        sdata = scored.json()
        assert 0 <= sdata["score"] <= 100
        assert sdata["word_count"] > 10


def test_offline_viral_boost_never_injects_directive_and_empty_is_zero(monkeypatch) -> None:
    import asyncio
    from omaishort.engine.fallback import fallback_analyze
    from omaishort.engine.viral_score import boost_viral_script
    from omaishort_schema.models import Genre, StoryInput, StoryMode, VideoKind

    # Empty script must score 0 (not 1).
    assert evaluate_viral_script("")["score"] == 0

    # Force offline fallback in complete_json_result.
    async def _offline(*args, **kwargs):
        return None, None, "offline"

    monkeypatch.setattr("omaishort.engine.analyzer.complete_json_result", _offline)

    raw = (
        "Xin chào các bạn, hôm nay chúng ta sẽ xem chuyện ở sảnh công ty. "
        "Người bảo vệ cũ bị sỉ nhục trước đám đông. Nhưng 5 phút sau chủ tịch bước xuống cúi chào. Đó là nội dung chính."
    )
    res = asyncio.run(
        boost_viral_script(
            text=raw,
            kind="drama",
            language="vi",
            target_seconds=30,
            instruction="Tối ưu kịch bản theo chuẩn viral short-video",
        )
    )
    assert res["provider"] == "local-polish"
    assert res["note"]
    assert "Tối ưu kịch bản" not in res["text"]
    assert "Khắc phục các điểm yếu" not in res["text"]
    assert "Xin chào các bạn" not in res["text"]
    assert len(res["text"]) <= len(raw) + 40

    # Regression P0-8: Vietnamese corporate story must not get English cheating-wife silk robe or kitchen.
    story = StoryInput(
        mode=StoryMode.script,
        kind=VideoKind.drama,
        genre=Genre.drama,
        text=(
            "Tại sảnh công ty lúc 8 giờ sáng, nhân viên mới bị quản lý đuổi ra ngoài vì mặc áo cũ. "
            "Cả sảnh cười ồ lên, nhưng đúng lúc đó thang máy mở ra và chủ tịch tập đoàn bước tới cúi đầu chào."
        ),
        target_seconds=30,
        language="vi",
    )
    bible, structure = fallback_analyze(story)
    assert "silk robe" not in bible.characters[0].clothing.lower()
    assert "wedding band" not in bible.characters[0].clothing.lower()
    assert any(loc.id == "office" for loc in bible.locations)
    # Short 2-sentence story should split clauses across beats instead of duplicating 1 sentence 4 times.
    unique_beats = {structure.hook, structure.conflict, structure.rising_action, structure.twist, structure.ending}
    assert len(unique_beats) >= 3
