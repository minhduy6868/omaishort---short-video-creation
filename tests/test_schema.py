import json

import pytest
from pydantic import ValidationError

from omaishort.db import artifacts_of, public_job
from omaishort_schema.models import AssetRef, Character, CharacterBible, StoryInput, VideoKind


def test_story_input_rejects_tiny_text():
    with pytest.raises(ValidationError):
        StoryInput(text="hi")


def test_story_input_accepts_news_kind():
    story = StoryInput(text="hello world this is a news brief", kind=VideoKind.news)
    assert story.kind == VideoKind.news
    legacy = StoryInput(text="hello world this is a news brief", kind=VideoKind.brief)
    assert legacy.kind == VideoKind.news
    knowledge = StoryInput(text="hello world this is a knowledge brief", kind=VideoKind.knowledge)
    assert knowledge.kind == VideoKind.knowledge
    assert knowledge.genre.value == "knowledge"


def test_storyboard_legacy_brief_kind_becomes_news():
    from omaishort_schema.models import Scene, Shot, Storyboard

    board = Storyboard(
        title="A news short title here",
        target_seconds=60,
        language="vi",
        kind="brief",
        scenes=[
            Scene(
                index=1,
                duration_sec=8,
                location="studio",
                location_id="studio",
                characters=[],
                emotion="hook",
                action="uninhabited desk",
                dialogue_or_vo="Một bản tin ngắn về hạ tầng năm G.",
                lighting="broadcast",
                mood="hook",
                still_id="still_01",
                use_face_ref=False,
                shots=[Shot(camera="medium", motion="zoom_in", t_start=0, t_end=8, still_id="still_01")],
            )
        ],
    )
    assert board.kind == VideoKind.news


def test_story_input_blank_source_url_becomes_none():
    story = StoryInput(text="hello world this is a news brief", source_url="  ")
    assert story.source_url is None


def test_story_input_blank_voice_id_becomes_none():
    story = StoryInput(text="hello world this is a news brief", voice_id="  ")
    assert story.voice_id is None
    picked = StoryInput(text="hello world this is a news brief", language="vi", voice_id="vi-male")
    assert picked.voice_id == "vi-male"


def test_story_input_script_brief_optional():
    story = StoryInput(text="hello world this is a knowledge brief", kind=VideoKind.knowledge, script_brief="  ")
    assert story.script_brief is None
    noted = StoryInput(
        text="hello world this is a knowledge brief",
        kind=VideoKind.knowledge,
        script_brief="  giọng tài liệu, nhấn trận  ",
    )
    assert noted.script_brief == "giọng tài liệu, nhấn trận"
    with pytest.raises(ValidationError):
        StoryInput(text="hello world this is a knowledge brief", script_brief="x" * 2001)


def test_grok_web_sso_cookie_names():
    from omaishort.providers.grok_web import cookies_have_sso

    assert cookies_have_sso([{"name": "sso", "domain": ".grok.com"}])
    assert not cookies_have_sso([{"name": "session", "domain": ".grok.com"}])


def test_grok_web_is_authed_needs_cookie_db(tmp_path, monkeypatch):
    from omaishort.providers import grok_web

    monkeypatch.setattr(grok_web, "DATA_DIR", tmp_path)
    monkeypatch.setattr(grok_web, "GROK_WEB_ENABLED", True)
    assert not grok_web.is_authed()
    grok_web.save_authed()
    assert not grok_web.is_authed()
    cookies = tmp_path / "grok-web" / "profile" / "Default" / "Cookies"
    cookies.parent.mkdir(parents=True)
    cookies.write_bytes(b"x" * 200)
    assert grok_web.is_authed()
    grok_web.clear_authed()
    assert not grok_web.is_authed()


def test_story_input_drama_shape_defaults_to_infer():
    from omaishort_schema.models import DramaShape

    story = StoryInput(text="hello world this is a long enough paste")
    assert story.drama_shape == DramaShape.infer
    custom = StoryInput(text="hello world this is a long enough paste", drama_shape="custom")
    assert custom.drama_shape == DramaShape.custom
    viral = StoryInput(text="hello world this is a long enough paste", drama_shape=DramaShape.default)
    assert viral.drama_shape == DramaShape.default


def test_character_bible_roundtrip():
    bible = CharacterBible(
        characters=[
            Character(
                id="wife",
                appearance="dark hair, tired eyes",
                clothing="black silk robe",
            )
        ],
        locations=[
            AssetRef(id="kitchen", description="kitchen at night", appearance="white cabinets"),
        ],
        props=[
            AssetRef(id="phone", description="smartphone", appearance="black glass"),
        ],
    )
    again = CharacterBible.model_validate_json(bible.model_dump_json())
    assert again.characters[0].id == "wife"
    assert again.locations[0].id == "kitchen"
    assert again.props[0].id == "phone"


def test_public_job_parses_nested_json():
    row = {
        "id": "abc",
        "status": "done",
        "stage": "done",
        "input_json": json.dumps({"text": "hello world story"}),
        "artifacts_json": json.dumps({"mp4": "/tmp/short.mp4"}),
        "bible_json": None,
    }
    payload = public_job(row)
    assert payload["input"]["text"].startswith("hello")
    assert payload["artifacts"]["mp4"].endswith("short.mp4")
    assert "input_json" not in payload
    assert artifacts_of(row)["mp4"].endswith("short.mp4")
