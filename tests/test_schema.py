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
