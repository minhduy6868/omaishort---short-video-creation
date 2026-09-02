from __future__ import annotations

from omaishort.engine.fallback import fallback_plan, is_dialogue_script, normalize_storyboard
from omaishort.engine.image_prompts import fill_image_prompts
from omaishort.providers.llm import complete_json, load_prompt
from omaishort_schema.models import Camera, CharacterBible, Motion, Storyboard, StoryInput, StoryStructure


def _coerce_storyboard(raw: dict, story: StoryInput) -> dict:
    scenes = raw.get("scenes") or []
    cleaned = []
    for i, scene in enumerate(scenes, start=1):
        still_id = f"still_{i:02d}"
        duration = float(scene.get("duration_sec") or 4)
        shots = scene.get("shots") or []
        if not shots:
            shots = [
                {
                    "camera": "medium",
                    "motion": "zoom_in",
                    "t_start": 0,
                    "t_end": duration,
                    "still_id": still_id,
                }
            ]
        for shot in shots:
            shot["still_id"] = still_id
            shot["camera"] = shot.get("camera") or "medium"
            shot["motion"] = shot.get("motion") or "hold"
            if shot["camera"] not in Camera._value2member_map_:
                shot["camera"] = "medium"
            if shot["motion"] not in Motion._value2member_map_:
                shot["motion"] = "hold"
            try:
                start = float(shot.get("t_start") if shot.get("t_start") is not None else 0)
                end = float(shot.get("t_end") if shot.get("t_end") is not None else duration)
            except (TypeError, ValueError):
                start, end = 0.0, duration
            if end <= start:
                end = start + 0.2
            shot["t_start"] = start
            shot["t_end"] = end
        scene["index"] = i
        scene["still_id"] = still_id
        scene["shots"] = shots
        scene["duration_sec"] = duration
        scene.setdefault("characters", [])
        scene.setdefault("prop_ids", [])
        scene.setdefault("location_id", None)
        scene.setdefault("consistency_notes", "")
        scene.setdefault("image_prompt", "")
        scene.setdefault("use_face_ref", True)
        scene.setdefault("use_location_ref", True)
        scene.setdefault("speaker_id", None)
        cleaned.append(scene)
    cleaned = cleaned[:15]
    raw["scenes"] = cleaned
    raw.setdefault("title", "Untitled short")
    raw["target_seconds"] = float(raw.get("target_seconds") or story.target_seconds)
    raw.setdefault("language", story.language)
    return raw


async def plan_scenes(
    story: StoryInput,
    bible: CharacterBible,
    structure: StoryStructure,
) -> tuple[Storyboard, str]:
    system = load_prompt("planner.txt")
    user = (
        f"target_seconds={story.target_seconds}\nlanguage={story.language}\ngenre={story.genre.value}\n\n"
        f"BIBLE:\n{bible.model_dump_json(indent=2)}\n\n"
        f"STRUCTURE:\n{structure.model_dump_json(indent=2)}\n\n"
        f"STORY:\n{story.text}"
    )
    raw = await complete_json(system, user)
    if raw:
        try:
            board = Storyboard.model_validate(_coerce_storyboard(raw, story))
            if story.target_seconds >= 45 and len(board.scenes) < 6:
                raise ValueError("llm storyboard too thin")
            if is_dialogue_script(story.text) and not any(scene.speaker_id for scene in board.scenes):
                raise ValueError("llm dropped dialogue speakers")
            normalize_storyboard(board, bible)
            fill_image_prompts(board, bible)
            return board, "llm"
        except Exception:
            pass
    board = fallback_plan(story, bible, structure)
    fill_image_prompts(board, bible)
    return board, "fallback"
