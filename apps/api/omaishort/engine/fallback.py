from __future__ import annotations

import re

from omaishort_schema.models import (
    Camera,
    Character,
    CharacterBible,
    Motion,
    Scene,
    Shot,
    Storyboard,
    StoryInput,
    StoryStructure,
)

BEAT_ORDER = ("hook", "conflict", "rising_action", "twist", "ending")
CAMERA_CYCLE = (Camera.wide, Camera.medium, Camera.close_up)
MOTION_CYCLE = (Motion.hold, Motion.zoom_in, Motion.pan_right, Motion.zoom_out, Motion.pan_left)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _chunk_sentences(sentences: list[str], target_scenes: int) -> list[list[str]]:
    if not sentences:
        return [["A quiet confession begins."]]
    target_scenes = max(8, min(15, target_scenes))
    if len(sentences) <= target_scenes:
        groups: list[list[str]] = []
        buf: list[str] = []
        for sentence in sentences:
            buf.append(sentence)
            if len(" ".join(buf).split()) >= 18:
                groups.append(buf)
                buf = []
        if buf:
            if groups:
                groups[-1].extend(buf)
            else:
                groups.append(buf)
        return groups
    size = max(1, len(sentences) // target_scenes)
    groups = []
    for i in range(0, len(sentences), size):
        groups.append(sentences[i : i + size])
    while len(groups) > 15:
        tail = groups.pop()
        groups[-1].extend(tail)
    return groups


def _guess_characters(text: str) -> CharacterBible:
    lowered = text.lower()
    chars: list[Character] = [
        Character(
            id="narrator",
            age=29,
            gender="female" if any(w in lowered for w in ("i was his wife", "my husband", "i'm his")) else "female",
            appearance="late-twenties woman, dark brown hair in a low knot, tired eyes, small gold stud earrings",
            clothing="black silk robe over a white tank, no jewelry except a thin wedding band",
            personality="controlled, then cracking",
        )
    ]
    if any(w in lowered for w in ("husband", "he left", "his phone")):
        chars.append(
            Character(
                id="husband",
                age=32,
                gender="male",
                appearance="early-thirties man, short black hair, faint stubble, sharp jaw",
                clothing="charcoal office shirt, sleeves rolled, watch on left wrist",
                personality="smooth, then cornered",
            )
        )
    if any(w in lowered for w in ("her name", "the other woman", "her lipstick", "mistress")):
        chars.append(
            Character(
                id="other_woman",
                age=26,
                gender="female",
                appearance="mid-twenties woman, long straight black hair, red lip",
                clothing="red coat, gold hoop earrings",
                personality="unapologetic",
            )
        )
    return CharacterBible(characters=chars)


def _guess_structure(text: str, target: int) -> StoryStructure:
    sentences = _sentences(text)
    n = max(5, len(sentences))
    def at(frac: float) -> str:
        idx = min(len(sentences) - 1, int(frac * n))
        return sentences[idx]
    return StoryStructure(
        hook=at(0.02),
        conflict=at(0.22),
        rising_action=at(0.5),
        twist=at(0.78),
        ending=at(0.96),
        hook_sec=round(target * 0.10, 2),
        conflict_sec=round(target * 0.20, 2),
        rising_sec=round(target * 0.33, 2),
        twist_sec=round(target * 0.23, 2),
        ending_sec=round(target * 0.14, 2),
    )


def _shots_for_scene(still_id: str, duration: float, index: int) -> list[Shot]:
    if duration < 3.2:
        return [
            Shot(
                camera=CAMERA_CYCLE[index % 3],
                motion=MOTION_CYCLE[index % 5],
                t_start=0,
                t_end=duration,
                still_id=still_id,
            )
        ]
    split = round(duration * 0.45, 2)
    return [
        Shot(
            camera=Camera.wide if index % 2 == 0 else Camera.medium,
            motion=Motion.hold,
            t_start=0,
            t_end=split,
            still_id=still_id,
        ),
        Shot(
            camera=Camera.close_up,
            motion=Motion.zoom_in if index % 2 == 0 else Motion.pan_right,
            t_start=split,
            t_end=duration,
            still_id=still_id,
        ),
    ]


def fallback_analyze(story: StoryInput) -> tuple[CharacterBible, StoryStructure]:
    return _guess_characters(story.text), _guess_structure(story.text, story.target_seconds)


def fallback_plan(story: StoryInput, bible: CharacterBible, structure: StoryStructure) -> Storyboard:
    groups = _chunk_sentences(_sentences(story.text), 10)
    total_words = sum(len(" ".join(g).split()) for g in groups) or 1
    ids = [c.id for c in bible.characters]
    scenes: list[Scene] = []
    locations = [
        "dim apartment hallway",
        "kitchen at night",
        "bedroom doorway",
        "bathroom mirror",
        "living room couch",
        "phone screen close",
        "rain-wet street",
        "front door",
    ]
    beats = [structure.hook, structure.conflict, structure.rising_action, structure.twist, structure.ending]
    for i, group in enumerate(groups, start=1):
        vo = " ".join(group)
        duration = max(3.5, story.target_seconds * (len(vo.split()) / total_words))
        still_id = f"still_{i:02d}"
        beat_name = BEAT_ORDER[min(len(BEAT_ORDER) - 1, int((i - 1) / max(1, len(groups)) * 5))]
        back = any(w in vo.lower() for w in ("walked away", "his back", "turned away"))
        present = [ids[0]]
        if "he " in vo.lower() or "husband" in vo.lower():
            if "husband" in ids:
                present.append("husband")
        scenes.append(
            Scene(
                index=i,
                duration_sec=round(duration, 2),
                location=locations[(i - 1) % len(locations)],
                characters=present,
                emotion=beat_name if beat_name != "rising_action" else "rising dread",
                action=vo[:140],
                dialogue_or_vo=vo,
                lighting="practical lamps, cinematic contrast, 9:16",
                mood=beats[min(i - 1, len(beats) - 1)][:80],
                consistency_notes="keep narrator wardrobe and wedding band",
                still_id=still_id,
                shots=_shots_for_scene(still_id, round(duration, 2), i),
                use_face_ref=not back,
            )
        )
    scale = story.target_seconds / max(0.1, sum(s.duration_sec for s in scenes))
    for scene in scenes:
        scene.duration_sec = round(scene.duration_sec * scale, 2)
        for shot in scene.shots:
            shot.t_start = round(shot.t_start * scale, 2)
            shot.t_end = round(shot.t_end * scale, 2)
        if scene.shots:
            scene.shots[-1].t_end = scene.duration_sec
    title = story.text.strip().split("\n")[0][:72] or "Untitled short"
    return Storyboard(title=title, target_seconds=float(story.target_seconds), language=story.language, scenes=scenes)
