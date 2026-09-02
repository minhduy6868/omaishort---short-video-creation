import json

import pytest
from pydantic import ValidationError

from omaishort.db import artifacts_of, public_job
from omaishort_schema.models import AssetRef, Character, CharacterBible, StoryInput


def test_story_input_rejects_tiny_text():
    with pytest.raises(ValidationError):
        StoryInput(text="hi")


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
