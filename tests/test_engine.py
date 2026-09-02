from pathlib import Path

from omaishort.engine.captions import clamp_word_stamps, edge_ticks_to_seconds, even_split, hex_to_ass, words_to_ass
from omaishort.engine.fallback import bind_scene_assets, beat_shots, fallback_analyze, fallback_plan, pick_location
from omaishort.engine.image_prompts import build_scene_prompt
from omaishort.engine.kenburns import zoompan_expr
from omaishort.engine.motion_prompt import motion_prompt
from omaishort.engine.rescale import rescale_to_audio
from omaishort_schema.models import Camera, Genre, Motion, Shot, StoryInput, StoryMode, SubtitleStyle

ROOT = Path(__file__).resolve().parents[1]


def _story(text: str | None = None) -> StoryInput:
    return StoryInput(
        mode=StoryMode.script,
        text=text
        or (
            "I found his phone at 2 a.m. The messages were not ours. "
            "Her name was Mara. He said don't worry. I put the phone back. "
            "In the morning he kissed my forehead. I changed the locks. "
            "He called from the airport. I let it ring."
        ),
        target_seconds=60,
        genre=Genre.confession,
        language="en",
    )


def _assert_board(board, min_scenes: int = 2) -> None:
    assert len(board.scenes) >= min_scenes
    stills = [s.still_id for s in board.scenes]
    assert len(stills) == len(set(stills))
    for scene in board.scenes:
        assert len(scene.shots) >= 1
        assert all(shot.still_id == scene.still_id for shot in scene.shots)
        assert scene.duration_sec > 0
        assert scene.characters
        assert scene.location_id
        assert abs(scene.shots[0].t_start) < 1e-6
        assert abs(scene.shots[-1].t_end - scene.duration_sec) < 0.05
        for prev, nxt in zip(scene.shots, scene.shots[1:]):
            assert abs(prev.t_end - nxt.t_start) < 0.05
    shot_n = sum(len(s.shots) for s in board.scenes)
    assert shot_n >= len(board.scenes)


def test_fallback_plan_one_still_many_shots():
    story = _story()
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    _assert_board(board, min_scenes=2)


def test_fallback_sample_script_has_enough_scenes():
    text = (ROOT / "samples" / "confession-60s.md").read_text(encoding="utf-8")
    story = _story(text)
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    _assert_board(board, min_scenes=8)
    assert len(board.scenes) <= 15
    ids = {c.id for c in bible.characters}
    assert "wife" in ids
    assert "husband" in ids


def test_rescale_matches_audio():
    story = _story()
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    scaled = rescale_to_audio(board, 40.0)
    total = sum(s.duration_sec for s in scaled.scenes)
    assert abs(total - 40.0) < 0.02
    for scene in scaled.scenes:
        assert abs(scene.shots[-1].t_end - scene.duration_sec) < 0.05


def test_even_split_covers_duration():
    stamps = even_split("one two three four", 8.0)
    assert len(stamps) == 4
    assert stamps[0].start == 0.0
    assert abs(stamps[-1].end - 8.0) < 1e-6


def test_edge_ticks_to_seconds():
    assert abs(edge_ticks_to_seconds(10_000_000) - 1.0) < 1e-9
    assert abs(edge_ticks_to_seconds(5_000_000) - 0.5) < 1e-9
    assert abs(edge_ticks_to_seconds(0) - 0.0) < 1e-9


def test_words_to_ass_uses_font_size(tmp_path: Path):
    stamps = even_split("one two three four", 4.0)
    dest = tmp_path / "captions.ass"
    words_to_ass(stamps, dest, style=SubtitleStyle(font="Georgia", font_size=72, primary_hex="#FFFFFF"))
    text = dest.read_text(encoding="utf-8")
    assert "Georgia,72," in text
    assert hex_to_ass("#FFFFFF") in text


def test_fallback_reuses_location_id_for_same_place():
    story = _story(
        "I stood in the kitchen at night and opened every drawer with both hands shaking hard. "
        "He was still asleep down the hall and did not hear me. "
        "Then I went back to the kitchen at night and put his phone on the counter again. "
        "I did not make a sound until morning came."
    )
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    kitchen_ids = [s.location_id for s in board.scenes if s.location_id == "kitchen" or "kitchen" in s.location.lower()]
    assert kitchen_ids
    assert len(set(kitchen_ids)) == 1
    board.scenes[0].location = "kitchen at night"
    board.scenes[0].location_id = None
    if len(board.scenes) > 1:
        board.scenes[1].location = "kitchen at night"
        board.scenes[1].location_id = None
        bind_scene_assets(board, bible)
        assert board.scenes[0].location_id == board.scenes[1].location_id


def test_lock_screen_is_insert_not_front_door():
    story = _story("The lock screen was a photo of us. The messages were not ours.")
    bible, structure = fallback_analyze(story)
    loc = pick_location("The lock screen was a photo of us. The messages were not.", 1, bible.locations)
    assert loc.id != "door"
    board = fallback_plan(story, bible, structure)
    assert all(scene.location_id != "door" for scene in board.scenes)


def test_changed_the_locks_is_door():
    story = _story("At noon I packed a bag. At twelve-oh-two I changed the locks and left.")
    bible, structure = fallback_analyze(story)
    loc = pick_location("At twelve-oh-two I changed the locks.", 2, bible.locations)
    assert loc.id == "door"


def test_lock_screen_insert_keeps_prior_kitchen():
    story = _story(
        "I found his phone on the counter at two in the morning while the house stayed quiet. "
        "The lock screen was a photo of us."
    )
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    kitchen = [s for s in board.scenes if s.location_id == "kitchen"]
    assert kitchen
    inserts = [s for s in board.scenes if "lock screen" in s.dialogue_or_vo.lower()]
    assert inserts
    assert inserts[0].location_id == "kitchen"
    assert inserts[0].use_location_ref is False


def test_unspecified_place_keeps_previous_location():
    story = _story(
        "I found his phone on the kitchen counter at two in the morning while the house stayed quiet. "
        "I did not make a sound until I put it down again beside the keys."
    )
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    assert board.scenes[0].location_id == "kitchen"
    assert "street" not in {scene.location_id for scene in board.scenes}


def test_clamp_word_stamps_fits_duration():
    raw = even_split("one two three", 10.0)
    raw[-1].end = 12.0
    clamped = clamp_word_stamps(raw, 4.0)
    assert clamped
    assert clamped[-1].end <= 4.0 + 1e-9
    assert clamped[0].start >= 0.0


def test_scene_prompt_asks_for_face_ref_before_images_exist():
    story = _story()
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    face = next(s for s in board.scenes if s.use_face_ref)
    prompt = build_scene_prompt(face, bible)
    assert "identity lock" in prompt
    assert "On camera ONLY:" in prompt
    assert "No extra people" in prompt


def test_husband_only_when_on_camera():
    text = (ROOT / "samples" / "confession-60s.md").read_text(encoding="utf-8")
    story = _story(text)
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    said = [s for s in board.scenes if "he said" in s.dialogue_or_vo.lower()]
    assert said
    assert all("husband" not in s.characters for s in said)
    kissed = [s for s in board.scenes if "kissed" in s.dialogue_or_vo.lower()]
    assert kissed
    assert "husband" in kissed[0].characters


def test_dialogue_script_is_speech_not_narration():
    story = _story(
        "Vợ: Anh về muộn thế?\n"
        "Chồng: Công ty họp đến giờ này.\n"
        "Vợ: Điện thoại anh sáng suốt đêm.\n"
        "Chồng: Đừng lo. Em không bao giờ kiểm tra.\n"
        "Vợ: Mara nhắn tin lúc hai giờ sáng.\n"
        "Chồng: Đó là khách hàng.\n"
        "Vợ: Khách hàng không gọi anh là honey.\n"
        "Chồng: Em hiểu lầm rồi.\n"
    )
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    ids = {c.id for c in bible.characters}
    assert "wife" in ids
    assert "husband" in ids
    assert board.scenes[0].speaker_id == "wife"
    assert board.scenes[0].dialogue_or_vo == "Anh về muộn thế?"
    assert board.scenes[1].speaker_id == "husband"
    assert all(":" not in scene.dialogue_or_vo for scene in board.scenes)
    assert all(scene.characters[0] == scene.speaker_id for scene in board.scenes)
    spoken = " ".join(s.dialogue_or_vo for s in board.scenes)
    assert "he said" not in spoken.lower()
    assert "I found" not in spoken


def test_motion_prompt_is_camera_and_action_not_bible_dump():
    story = _story()
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    scene = board.scenes[0]
    scene.action = "unlocks the phone on the counter"
    scene.dialogue_or_vo = "UNIQUE_VO_PHRASE_SHOULD_NOT_ENTER_I2V"
    prompt = motion_prompt(scene)
    assert "start frame" in prompt
    assert "unlocks the phone" in prompt
    assert "UNIQUE_VO_PHRASE" not in prompt
    assert "Appearance lock" not in prompt
    assert "9:16" in prompt


def test_beat_shots_follow_drama_lenses():
    hook = beat_shots("still_01", 6.0, "hook")
    assert hook[0].motion == Motion.zoom_in
    assert hook[0].camera == Camera.medium
    ending = beat_shots("still_10", 6.0, "ending")
    assert ending[-1].motion == Motion.zoom_out
    assert ending[-1].camera == Camera.wide


def test_fallback_ends_on_pull_out():
    story = _story()
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    assert board.scenes[0].shots[0].motion == Motion.zoom_in
    assert board.scenes[-1].shots[-1].motion == Motion.zoom_out


def test_normalize_applies_beat_lenses_to_llm_shots():
    from omaishort.engine.fallback import apply_beat_lenses, infer_beat
    from omaishort_schema.models import Scene, Shot, Storyboard

    story = _story()
    bible, _structure = fallback_analyze(story)
    scene = Scene(
        index=1,
        duration_sec=6.0,
        location="kitchen at night",
        location_id="kitchen",
        characters=["wife"],
        emotion="hook",
        action="picks up the phone",
        dialogue_or_vo="I found his phone on the counter.",
        lighting="warm",
        mood="tense",
        still_id="still_01",
        shots=[Shot(camera=Camera.wide, motion=Motion.hold, t_start=0, t_end=6.0, still_id="still_01")],
    )
    board = Storyboard(title="t", target_seconds=6, language="en", scenes=[scene])
    apply_beat_lenses(board)
    assert infer_beat(scene, 0, 1) == "hook"
    assert board.scenes[0].shots[0].motion == Motion.zoom_in
    assert board.scenes[0].shots[0].camera == Camera.medium


def test_zoompan_works_at_2x_with_easing():
    shot = Shot(camera=Camera.close_up, motion=Motion.zoom_in, t_start=0, t_end=2, still_id="still_01")
    expr = zoompan_expr(shot, 60)
    assert "2160:3840" in expr
    assert "cos(PI*on" in expr
    assert "s=1080x1920" in expr
    assert "1350:2400" not in expr
