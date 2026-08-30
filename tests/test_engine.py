from pathlib import Path

from omaishort.engine.captions import even_split
from omaishort.engine.fallback import fallback_analyze, fallback_plan
from omaishort.engine.rescale import rescale_to_audio
from omaishort_schema.models import Genre, StoryInput, StoryMode

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
    _assert_board(board, min_scenes=6)
    assert len(board.scenes) <= 15


def test_rescale_matches_audio():
    story = _story()
    bible, structure = fallback_analyze(story)
    board = fallback_plan(story, bible, structure)
    scaled = rescale_to_audio(board, 40.0)
    total = sum(s.duration_sec for s in scaled.scenes)
    assert abs(total - 40.0) < 0.2
    for scene in scaled.scenes:
        assert abs(scene.shots[-1].t_end - scene.duration_sec) < 0.05


def test_even_split_covers_duration():
    stamps = even_split("one two three four", 8.0)
    assert len(stamps) == 4
    assert stamps[0].start == 0.0
    assert abs(stamps[-1].end - 8.0) < 1e-6
