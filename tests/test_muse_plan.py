"""Muse shot planning + provider readiness (no live Hatch)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from omaishort.providers.muse_plan import (
    muse_clip_prompt,
    muse_scene_count_for_duration,
    muse_scene_draft_prompt,
    normalize_muse_duration,
    parse_muse_scenes,
)
from omaishort.providers.muse_video import MuseVideoProvider
from omaishort.providers.muse_web import bootstrap_has_gateway, url_is_challenge, url_is_login


def test_normalize_muse_duration():
    assert normalize_muse_duration(30) == 30
    assert normalize_muse_duration(25) == 30
    assert normalize_muse_duration("40") == 40


def test_scene_count_caps_at_two():
    assert muse_scene_count_for_duration(8) == 1
    assert muse_scene_count_for_duration(10) == 1
    assert muse_scene_count_for_duration(12) == 2
    assert muse_scene_count_for_duration(55) == 2
    assert muse_scene_count_for_duration(120) == 2


def test_parse_muse_scenes_headings():
    text = "\n".join(
        [
            "### SHOT 1",
            "Wide push-in on the kitchen.",
            "### SHOT 2",
            "Tight reaction on her face.",
            "### SHOT 3",
            "Pull-out as he leaves.",
        ]
    )
    scenes = parse_muse_scenes(text, 3)
    assert scenes is not None
    assert len(scenes) == 3
    assert "kitchen" in scenes[0].lower()


def test_parse_muse_scenes_json():
    text = '["first take", "second take"]'
    assert parse_muse_scenes(text, 2) == ["first take", "second take"]
    assert parse_muse_scenes(text, 3) is None


def test_clip_prompt_continuity_flag():
    with_cont = muse_clip_prompt("Walk to the door.", has_continuity_frame=True)
    without = muse_clip_prompt("Walk to the door.", has_continuity_frame=False)
    assert "previous-scene final frame" in with_cont
    assert "previous-scene final frame" not in without
    assert "Walk to the door." in with_cont


def test_draft_prompt_mentions_shot_count():
    prompt = muse_scene_draft_prompt("She finds the phone.", 3)
    assert "EXACTLY 3 shots" in prompt
    assert "She finds the phone." in prompt


def test_muse_hub_url_and_gateway_helpers():
    assert url_is_challenge("https://auth.meta.com/checkpoints/123")
    assert url_is_login("https://muse.ai/login")
    assert not bootstrap_has_gateway('"gatewayUrl":null,"vmName":null')
    assert bootstrap_has_gateway('"gatewayUrl":"https://abc.metaaivm.com","vmName":"abc"')


def test_muse_provider_skips_when_not_authed(tmp_path: Path):
    still = tmp_path / "still.png"
    still.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
    )
    dest = tmp_path / "out.mp4"
    result = asyncio.run(
        MuseVideoProvider().generate(
            "camera push in",
            dest,
            image_url=None,
            duration=10,
            still=still,
        )
    )
    assert result is None
