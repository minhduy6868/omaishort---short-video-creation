import asyncio
import json
import os
from pathlib import Path

from PIL import Image

from omaishort.engine.captions import even_split, words_to_ass
from omaishort.engine.compose import compose_short
from omaishort.engine.kenburns import conform_clip, has_audio_stream, probe_duration, probe_video_size, render_shot_clip
from omaishort.providers.tts import silence_audio
from omaishort_schema.models import Camera, MixSettings, Motion, Scene, Shot, Storyboard


def _still(path: Path) -> Path:
    Image.new("RGB", (1080, 1920), (32, 24, 18)).save(path)
    return path


def test_kenburns_clip_is_vertical(tmp_path: Path):
    still = _still(tmp_path / "still.png")
    dest = tmp_path / "clip.mp4"
    shot = Shot(camera=Camera.medium, motion=Motion.zoom_in, t_start=0, t_end=0.5, still_id="still_01")
    asyncio.run(render_shot_clip(still, shot, dest))
    assert dest.exists() and dest.stat().st_size > 0
    assert probe_video_size(dest) == (1080, 1920)


def test_conform_clip_is_vertical_and_timed(tmp_path: Path):
    still = _still(tmp_path / "still.png")
    src = tmp_path / "src.mp4"
    shot = Shot(camera=Camera.medium, motion=Motion.hold, t_start=0, t_end=0.4, still_id="still_01")
    asyncio.run(render_shot_clip(still, shot, src))
    dest = tmp_path / "fit.mp4"
    asyncio.run(conform_clip(src, dest, 0.8))
    assert dest.exists() and dest.stat().st_size > 0
    assert probe_video_size(dest) == (1080, 1920)
    assert abs(probe_duration(dest) - 0.8) < 0.12


def test_extract_last_frame_writes_png(tmp_path: Path):
    from omaishort.engine.kenburns import extract_last_frame

    still = _still(tmp_path / "still.png")
    src = tmp_path / "src.mp4"
    shot = Shot(camera=Camera.medium, motion=Motion.hold, t_start=0, t_end=0.4, still_id="still_01")
    asyncio.run(render_shot_clip(still, shot, src))
    dest = tmp_path / "last.png"
    asyncio.run(extract_last_frame(src, dest))
    assert dest.exists() and dest.stat().st_size > 0
    img = Image.open(dest)
    assert img.size[0] > 0 and img.size[1] > 0


def test_generate_clip_skips_without_public_still_url(tmp_path: Path):
    from omaishort.providers.video import generate_clip

    still = _still(tmp_path / "still.png")
    dest = tmp_path / "i2v.mp4"
    result = asyncio.run(generate_clip("slow push in", dest, still, duration=5.0))
    assert result is None
    assert not dest.exists()


def test_pollinations_duration_clamps_veo():
    from omaishort.providers.video import pollinations_duration_sec, pollinations_video_params

    assert pollinations_duration_sec("wan-fast", 4.0) == 5
    assert pollinations_duration_sec("veo", 3.2) == 4
    assert pollinations_duration_sec("veo", 5.0) == 6
    assert pollinations_duration_sec("veo", 7.9) == 8
    assert pollinations_duration_sec("seedance-2.5", 6.0) == 4
    wan = pollinations_video_params(
        "wan-fast", "https://img.example/start.png", 5.0, end_image_url="https://img.example/end.png"
    )
    assert "imageEnd" not in wan
    veo = pollinations_video_params(
        "veo", "https://img.example/start.png", 5.0, end_image_url="https://img.example/end.png"
    )
    assert veo["image"] == "https://img.example/start.png"
    assert veo["imageEnd"] == "https://img.example/end.png"
    assert veo["duration"] == "6"


def test_wavespeed_duration_and_output_url():
    from omaishort.providers.video import (
        wavespeed_duration_sec,
        wavespeed_output_url,
        wavespeed_submit_body,
    )

    assert wavespeed_duration_sec(4.0) == 5
    assert wavespeed_duration_sec(6.9) == 5
    assert wavespeed_duration_sec(7.0) == 8
    start_only = wavespeed_submit_body(
        "slow push",
        "https://img.example/start.png",
        5.0,
        "wavespeed-ai/wan-2.2/i2v-480p-ultra-fast",
        end_image_url="https://img.example/end.png",
    )
    assert "last_image" not in start_only
    frames = wavespeed_submit_body(
        "slow push",
        "https://img.example/start.png",
        8.0,
        "wavespeed-ai/wan-2.2/flf2v-720p",
        end_image_url="https://img.example/end.png",
    )
    assert frames["last_image"] == "https://img.example/end.png"
    assert frames["duration"] == 8
    assert (
        wavespeed_output_url({"data": {"outputs": ["https://cdn.example/a.mp4"]}})
        == "https://cdn.example/a.mp4"
    )
    assert (
        wavespeed_output_url({"outputs": [{"url": "https://cdn.example/b.mp4"}]})
        == "https://cdn.example/b.mp4"
    )
    assert wavespeed_output_url({"data": {"outputs": []}}) is None
    assert wavespeed_output_url({"message": "success"}) is None


def test_xai_video_body_is_vertical_i2v():
    from omaishort.providers.xai_video import xai_video_body, xai_video_duration_sec

    assert xai_video_duration_sec(4.2) == 4
    assert xai_video_duration_sec(0) == 8
    assert xai_video_duration_sec(20) == 15
    body = xai_video_body(
        "slow punch-in, keep the wife",
        "grok-imagine-video-1.5",
        "data:image/png;base64,abc",
        5.4,
        resolution="720p",
    )
    assert body["aspect_ratio"] == "9:16"
    assert body["duration"] == 5
    assert body["image"]["url"].startswith("data:image/png")
    assert body["resolution"] == "720p"
    assert "wife" in body["prompt"]


def test_i2v_providers_prefer_last_frame_adapters_when_bridging(monkeypatch):
    from omaishort.providers import grok_web, video as video_mod
    from omaishort.providers.video import i2v_providers, i2v_used_end_frame

    monkeypatch.setattr(video_mod, "XAI_API_KEY", "")
    monkeypatch.setattr(video_mod, "XAI_VIDEO_ENABLED", False)
    monkeypatch.setattr(grok_web, "is_authed", lambda: False)
    start_only = [p.name for p in i2v_providers(wants_end_frame=False)]
    bridged = [p.name for p in i2v_providers(wants_end_frame=True)]
    assert start_only[0] == "hf_space_wan"
    assert bridged[0] == "hf_space_ltx"
    assert bridged[-2] == "hf_space_wan"
    assert i2v_used_end_frame("hf_space_ltx") is True
    assert i2v_used_end_frame("hf_space_wan") is False
    assert i2v_used_end_frame("xai_video") is False
    monkeypatch.setattr(video_mod, "XAI_API_KEY", "xai-test")
    monkeypatch.setattr(video_mod, "XAI_VIDEO_ENABLED", True)
    grok_first = [p.name for p in i2v_providers(wants_end_frame=False)]
    assert grok_first[0] == "xai_video"


def test_i2v_providers_prefer_grok_hub_when_authed(monkeypatch):
    from omaishort.providers import grok_web, video as video_mod
    from omaishort.providers.video import i2v_providers

    monkeypatch.setattr(video_mod, "XAI_API_KEY", "")
    monkeypatch.setattr(video_mod, "XAI_VIDEO_ENABLED", False)
    monkeypatch.setattr(video_mod, "GROK_WEB_VIDEO_ENABLED", True)
    monkeypatch.setattr(grok_web, "is_authed", lambda: True)
    names = [p.name for p in i2v_providers(wants_end_frame=False)]
    assert names[0] == "grok_hub_video"


def test_grok_hub_video_payload_is_vertical():
    from omaishort.providers.grok_hub_video import grok_hub_duration_sec, stream_video_url, video_conversation_body

    assert grok_hub_duration_sec(5) == 6
    assert grok_hub_duration_sec(9) == 10
    body = video_conversation_body("slow push in on lan", "post-1", 8, "https://assets.grok.com/x")
    assert body["modelName"] == "imagine-video-gen"
    config = body["responseMetadata"]["modelConfigOverride"]["modelMap"]["videoGenModelConfig"]
    assert config["aspectRatio"] == "9:16"
    assert config["videoLength"] == 10
    frame = {
        "result": {
            "response": {
                "streamingVideoGenerationResponse": {"progress": 100, "videoUrl": "/vid/a.mp4"}
            }
        }
    }
    raw = "data: " + json.dumps(frame)
    assert stream_video_url(raw).endswith("/vid/a.mp4")
    from omaishort.providers.grok_hub_video import media_post_id

    assert media_post_id({"id": "root", "post": {"id": "post-real", "meta": {"id": "nested"}}}) == "post-real"


def test_i2v_ready_includes_grok_hub(monkeypatch):
    from omaishort.engine import compose

    monkeypatch.setattr(compose, "XAI_API_KEY", "")
    monkeypatch.setattr(compose, "XAI_VIDEO_ENABLED", False)
    monkeypatch.setattr(compose, "POLLINATIONS_KEY", "")
    monkeypatch.setattr(compose, "HF_TOKEN", "")
    monkeypatch.setattr(compose, "WAVESPEED_API_KEY", "")
    monkeypatch.setattr(compose, "GROK_WEB_ENABLED", True)
    monkeypatch.setattr(compose, "GROK_WEB_VIDEO_ENABLED", True)
    monkeypatch.setattr("omaishort.providers.grok_web.is_authed", lambda: True)
    assert compose.i2v_ready() is True
    monkeypatch.setattr("omaishort.providers.grok_web.is_authed", lambda: False)
    assert compose.i2v_ready() is False


def test_hf_sse_extracts_video_url():
    from omaishort.providers.video import _file_data_from_upload, _video_url_from_sse

    raw = json.dumps([{"url": "https://example.com/clip.mp4", "orig_name": "out.mp4"}])
    assert _video_url_from_sse(raw, "https://space.example") == "https://example.com/clip.mp4"
    nested = json.dumps(
        [{"video": {"url": "https://example.com/out.mp4", "path": "/tmp/out.mp4"}, "subtitles": None}, 42]
    )
    assert _video_url_from_sse(nested, "https://space.example") == "https://example.com/out.mp4"
    uploaded = _file_data_from_upload(["/tmp/gradio/a/still.png"], "still.png", "https://space.example")
    assert uploaded is not None
    assert uploaded["url"] == "https://space.example/gradio_api/file=/tmp/gradio/a/still.png"
    public = _file_data_from_upload(
        [{"path": "https://example.com/bus.png", "url": "https://example.com/bus.png", "orig_name": "bus.png"}],
        "still.png",
        "https://space.example",
    )
    assert public is not None
    assert public["path"] == "https://example.com/bus.png"


def test_compose_writes_1080x1920_with_audio(tmp_path: Path):
    still = _still(tmp_path / "still.png")
    board = Storyboard(
        title="core smoke",
        target_seconds=1.0,
        language="en",
        scenes=[
            Scene(
                index=1,
                duration_sec=1.0,
                location="kitchen at night",
                location_id="kitchen",
                characters=["wife"],
                emotion="tense",
                action="stands still",
                dialogue_or_vo="one two three four",
                lighting="warm",
                mood="tense",
                still_id="still_01",
                shots=[
                    Shot(camera=Camera.wide, motion=Motion.hold, t_start=0, t_end=0.45, still_id="still_01"),
                    Shot(camera=Camera.close_up, motion=Motion.zoom_in, t_start=0.45, t_end=1.0, still_id="still_01"),
                ],
            )
        ],
    )
    work = tmp_path / "render"
    audio = asyncio.run(silence_audio(tmp_path / "vo.wav", 1.0))
    ass = words_to_ass(even_split("one two three four", 1.0), work / "captions.ass")
    dest = work / "short.mp4"
    asyncio.run(
        compose_short(
            board,
            {"still_01": still},
            audio,
            ass,
            dest,
            work,
            mix=MixSettings(bgm_enabled=False),
        )
    )
    assert dest.exists() and dest.stat().st_size > 0
    assert probe_video_size(dest) == (1080, 1920)
    assert has_audio_stream(dest)
    motion = json.loads((work / "motion.json").read_text(encoding="utf-8"))
    assert motion["mode"] == "kenburns"
    assert motion["i2v_still_ids"] == []
    assert motion["merge"] == "concat"
    assert motion["frames"] == []


def test_compose_overlays_logo_when_enabled(tmp_path: Path):
    still = _still(tmp_path / "still.png")
    logo = tmp_path / "mark.png"
    Image.new("RGBA", (64, 64), (220, 90, 40, 255)).save(logo)
    board = Storyboard(
        title="logo smoke",
        target_seconds=1.0,
        language="en",
        scenes=[
            Scene(
                index=1,
                duration_sec=1.0,
                location="kitchen at night",
                location_id="kitchen",
                characters=["wife"],
                emotion="tense",
                action="stands still",
                dialogue_or_vo="one two three four.",
                lighting="warm",
                mood="tense",
                still_id="still_01",
                shots=[
                    Shot(camera=Camera.wide, motion=Motion.hold, t_start=0, t_end=1.0, still_id="still_01"),
                ],
            )
        ],
    )
    work = tmp_path / "render"
    audio = asyncio.run(silence_audio(tmp_path / "vo.wav", 1.0))
    ass = words_to_ass(even_split("one two three four.", 1.0), work / "captions.ass")
    dest = work / "short.mp4"
    asyncio.run(
        compose_short(
            board,
            {"still_01": still},
            audio,
            ass,
            dest,
            work,
            mix=MixSettings(bgm_enabled=False, logo_enabled=True, logo_path=str(logo)),
        )
    )
    assert dest.exists() and dest.stat().st_size > 0
    assert probe_video_size(dest) == (1080, 1920)


def test_placeholder_still_is_pictorial_not_prompt_dump():
    from omaishort.providers.placeholder import paint_placeholder_still

    prompt = (
        "Cinematic still, 9:16 vertical, photoreal short-drama frame. "
        "Location: kitchen at night (kitchen)\nCamera: medium\n"
        "- wife: 29 female. Appearance lock: dark hair.\n"
        "- husband: 32 male."
    )
    img = paint_placeholder_still(prompt)
    assert img.size == (1080, 1920)
    extrema = img.getextrema()
    # not a wall of near-white prompt glyphs
    assert all(channel[1] > 40 for channel in extrema)


def test_pollinations_seed_stable_for_same_character():
    from omaishort.providers.pollinations import compact_image_prompt, identity_seed

    a = "Portrait / passport still of wife, 29 year old female.\nAppearance lock: dark hair."
    b = "Portrait / passport still of wife, 29 year old female.\nAppearance lock: dark hair, tired eyes."
    assert identity_seed(a) == identity_seed(b)
    assert identity_seed(a) <= 2_147_483_647
    kitchen = identity_seed("Id: kitchen\nDescription: kitchen at night")
    assert kitchen != identity_seed(a)
    compact = compact_image_prompt(a + "\nUse attached character reference images as identity lock.")
    assert "Use attached" not in compact
    assert "9:16" in compact
    assert "wearing" in compact.lower() or "passport" in compact.lower()
    assert len(compact) < 400


def test_compact_scene_prompt_keeps_only_cast_and_wardrobe():
    from omaishort.engine.fallback import fallback_analyze, fallback_plan
    from omaishort.engine.image_prompts import build_scene_prompt
    from omaishort.providers.pollinations import compact_image_prompt, identity_seed
    from omaishort_schema.models import Genre, StoryInput, StoryMode

    story = StoryInput(
        mode=StoryMode.script,
        text=(
            "I found his phone at 2 a.m. The messages were not ours. "
            "Her name was Mara. He said don't worry. I put the phone back. "
            "In the morning he kissed my forehead. I changed the locks. "
            "He called from the airport. I let it ring."
        ),
        target_seconds=60,
        genre=Genre.confession,
        language="en",
    )
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    wife_only = next(s for s in board.scenes if s.characters == ["wife"] and s.use_face_ref)
    prompt = build_scene_prompt(wife_only, bible)
    compact = compact_image_prompt(prompt)
    assert "ONLY wife" in compact
    assert "no extra people" in compact
    assert "He said" not in compact
    assert "silk" in compact.lower() or "robe" in compact.lower() or "tank" in compact.lower()
    assert "Appearance lock" not in compact
    insert = next((s for s in board.scenes if not s.use_face_ref), None)
    if insert:
        ic = compact_image_prompt(build_scene_prompt(insert, bible))
        assert "no full-body" in ic or "insert" in ic.lower()
        assert "no standing people" in ic
    same_cast = [
        s
        for s in board.scenes
        if s.location_id == "kitchen" and s.characters == ["wife"] and s.use_face_ref
    ]
    if len(same_cast) >= 2:
        pa = build_scene_prompt(same_cast[0], bible)
        pb = build_scene_prompt(same_cast[1], bible)
        assert identity_seed(pa) == identity_seed(pb)


def test_looks_like_photo_rejects_placeholder(tmp_path: Path):
    from omaishort.providers.placeholder import paint_placeholder_still
    from omaishort.providers.pollinations import looks_like_photo

    dest = tmp_path / "geom.png"
    paint_placeholder_still("kitchen at night wife dark hair").save(dest, "PNG")
    assert not looks_like_photo(dest)
    noise = tmp_path / "photo.png"
    Image.frombytes("RGB", (128, 128), os.urandom(128 * 128 * 3)).save(noise, "PNG")
    assert looks_like_photo(noise)


def test_kontext_url_uses_character_passport_not_location(tmp_path: Path):
    import json

    from omaishort.providers.pollinations import build_pollinations_url, pick_kontext_url

    refs = tmp_path / "refs"
    locs = refs / "locations"
    refs.mkdir()
    locs.mkdir()
    wife = refs / "wife.png"
    wife.write_bytes(b"x")
    (wife.with_suffix(".pollinations.json")).write_text(
        json.dumps({"url": "https://image.pollinations.ai/prompt/wife-passport"}),
        encoding="utf-8",
    )
    kitchen = locs / "kitchen.png"
    kitchen.write_bytes(b"x")
    (kitchen.with_suffix(".pollinations.json")).write_text(
        json.dumps({"url": "https://image.pollinations.ai/prompt/kitchen-set"}),
        encoding="utf-8",
    )
    picked = pick_kontext_url([kitchen, wife])
    assert picked == "https://image.pollinations.ai/prompt/wife-passport"
    url = build_pollinations_url("kitchen night same wife", 1, image_url=picked)
    assert "model=kontext" in url
    assert "image=" in url
    assert "wife-passport" in url
