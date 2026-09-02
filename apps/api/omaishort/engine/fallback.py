from __future__ import annotations

import math
import re

from omaishort.engine.rescale import repair_scene_shots
from omaishort_schema.models import (
    AssetRef,
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
# Wind Comic: hook→push-in, conflict→tight, rising→pan, twist→punch-in, ending→pull-out.
_BEAT_LENSES: dict[str, tuple[tuple[Camera, Motion], tuple[Camera, Motion]]] = {
    "hook": ((Camera.medium, Motion.zoom_in), (Camera.close_up, Motion.zoom_in)),
    "conflict": ((Camera.medium, Motion.hold), (Camera.close_up, Motion.zoom_in)),
    "rising_action": ((Camera.wide, Motion.pan_right), (Camera.medium, Motion.zoom_in)),
    "twist": ((Camera.close_up, Motion.hold), (Camera.close_up, Motion.zoom_in)),
    "ending": ((Camera.medium, Motion.hold), (Camera.wide, Motion.zoom_out)),
}

LOCATION_CATALOG: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("kitchen", "kitchen at night", "galley kitchen, white cabinets, under-cabinet lights, dark window, tile floor", ("kitchen", "counter")),
    ("hallway", "dim apartment hallway", "narrow apartment hall, warm wall sconce, scuffed wood floor, beige walls", ("hallway", "corridor")),
    ("bedroom", "bedroom doorway", "small bedroom, rumpled white sheets, doorway frame, night lamp", ("bedroom", "bed")),
    ("bathroom", "bathroom mirror", "bathroom vanity, round mirror, warm bulb, tiled wall", ("bathroom", "mirror")),
    ("living_room", "living room couch", "living room, grey sofa, table lamp, dark tv", ("living room", "couch", "sofa")),
    ("street", "rain-wet street", "wet asphalt street at night, sodium streetlights, parked cars", ("street", "outside")),
    ("door", "front door", "apartment front door, peephole, deadbolt, dim porch light", ("front door", "changed the locks", "deadbolt")),
]

HUSBAND_ON_CAMERA = (
    "he kissed",
    "he stood",
    "he walked",
    "his back",
    "he turned",
    "beside him",
    "he sat",
    "he asked if i slept",
)
OTHER_ON_CAMERA = ("she stood", "she walked", "mara in the", "the other woman")

INSERT_MARKERS = (
    "phone screen",
    "screen close",
    "close-up of phone",
    "lock screen",
    "insert",
    "hands only",
    "messages on",
)

DIALOGUE_RE = re.compile(
    r"^([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ0-9_' ]{0,28}?)(?:\s*\(([^)]+)\))?\s*[:：]\s+(.+)$",
    re.UNICODE,
)
SPEAKER_ALIASES: dict[str, tuple[str, ...]] = {
    "wife": ("wife", "vo", "vợ", "em", "chi", "chị", "nàng"),
    "husband": ("husband", "chong", "chồng", "anh", "hắn"),
    "other_woman": ("other_woman", "mara", "lover", "cô ta", "người ấy", "co ta"),
}


def parse_dialogue_cues(text: str) -> list[tuple[str, str, str]]:
    """Return (speaker_label, place_hint, spoken_line) for Name: line scripts."""
    cues: list[tuple[str, str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = DIALOGUE_RE.match(line)
        if match:
            cues.append((match.group(1).strip(), (match.group(2) or "").strip(), match.group(3).strip()))
    return cues


def is_dialogue_script(text: str, cues: list[tuple[str, str, str]] | None = None) -> bool:
    cues = cues if cues is not None else parse_dialogue_cues(text)
    nonempty = [ln for ln in text.splitlines() if ln.strip()]
    if len(cues) >= 4:
        return True
    return bool(nonempty) and len(cues) >= 2 and len(cues) >= 0.4 * len(nonempty)


def _speaker_slug(label: str) -> str:
    key = re.sub(r"\s+", " ", label.strip().lower())
    for cid, aliases in SPEAKER_ALIASES.items():
        if key in aliases:
            return cid
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return slug[:40] or "narrator"


def resolve_speaker_id(label: str, bible: CharacterBible) -> str:
    slug = _speaker_slug(label)
    by_id = {char.id.lower(): char.id for char in bible.characters}
    if slug in by_id:
        return by_id[slug]
    if slug in {char.id for char in bible.characters}:
        return slug
    return bible.characters[0].id


def _character_stub(cid: str, label: str) -> Character:
    if cid == "husband":
        return Character(
            id="husband",
            age=32,
            gender="male",
            appearance="early-thirties man, short black hair, faint stubble, sharp jaw",
            clothing="charcoal office shirt, sleeves rolled, watch on left wrist",
            personality="smooth, then cornered",
        )
    if cid == "other_woman":
        return Character(
            id="other_woman",
            age=26,
            gender="female",
            appearance="mid-twenties woman, long straight black hair, red lip",
            clothing="red coat, gold hoop earrings",
            personality="unapologetic",
        )
    return Character(
        id=cid if cid != "narrator" else "wife",
        age=29,
        gender="female",
        appearance="late-twenties woman, dark brown hair in a low knot, tired eyes, small gold stud earrings",
        clothing="black silk robe over a white tank, no jewelry except a thin wedding band",
        personality=f"speaking as {label}",
    )


def _merge_dialogue_cues(cues: list[tuple[str, str, str]], limit: int) -> list[tuple[str, str, str]]:
    merged: list[tuple[str, str, str]] = []
    for label, place, spoken in cues:
        if (
            merged
            and _speaker_slug(merged[-1][0]) == _speaker_slug(label)
            and len(merged[-1][2].split()) + len(spoken.split()) <= 16
        ):
            prev_label, prev_place, prev_spoken = merged[-1]
            merged[-1] = (prev_label, place or prev_place, f"{prev_spoken} {spoken}")
        else:
            merged.append((label, place, spoken))
    while len(merged) > limit:
        idx = min(range(len(merged) - 1), key=lambda i: len(merged[i][2].split()) + len(merged[i + 1][2].split()))
        a, b = merged[idx], merged[idx + 1]
        merged[idx] = (a[0], a[1] or b[1], f"{a[2]} {b[2]}")
        merged.pop(idx + 1)
    return merged[:limit]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _chunk_sentences(sentences: list[str], target_scenes: int) -> list[list[str]]:
    if not sentences:
        return [["A quiet confession begins."]]
    target = max(8, min(15, target_scenes))
    n = len(sentences)
    if n <= 15:
        groups: list[list[str]] = []
        buf: list[str] = []
        for sentence in sentences:
            words = len(sentence.split())
            if buf and (len(" ".join(buf).split()) + words) <= 7:
                buf.append(sentence)
                continue
            if buf:
                groups.append(buf)
            buf = [sentence]
        if buf:
            groups.append(buf)
        while len(groups) > 15:
            tail = groups.pop()
            groups[-1].extend(tail)
        return groups
    size = max(1, math.ceil(n / target))
    groups = [sentences[i : i + size] for i in range(0, n, size)]
    while len(groups) > 15:
        tail = groups.pop()
        groups[-1].extend(tail)
    return groups


def _guess_locations() -> list[AssetRef]:
    return [
        AssetRef(id=loc_id, description=desc, appearance=appearance)
        for loc_id, desc, appearance, _keys in LOCATION_CATALOG
    ]


def _guess_props(text: str) -> list[AssetRef]:
    lowered = text.lower()
    props: list[AssetRef] = []
    if any(w in lowered for w in ("phone", "messages", "lock screen", "texted")):
        props.append(
            AssetRef(
                id="phone",
                description="husband's smartphone",
                appearance="black glass smartphone, lock-screen couple photo, faint fingerprint smudge",
            )
        )
    return props


def _guess_characters(text: str) -> CharacterBible:
    cues = parse_dialogue_cues(text)
    if is_dialogue_script(text, cues):
        chars: list[Character] = []
        seen: set[str] = set()
        for label, _place, _spoken in cues:
            cid = _speaker_slug(label)
            if cid in seen:
                continue
            seen.add(cid)
            chars.append(_character_stub(cid, label))
            if len(chars) >= 5:
                break
        if not chars:
            chars.append(_character_stub("wife", "wife"))
        return CharacterBible(characters=chars, locations=_guess_locations(), props=_guess_props(text))
    lowered = text.lower()
    first_person = bool(re.search(r"\bi\b", lowered))
    husband_cues = ("husband", "he left", "his phone", "he said", "he typed", "he kissed", "he called", "his mother")
    protagonist = "wife" if first_person and any(w in lowered for w in husband_cues) else "narrator"
    chars: list[Character] = [
        Character(
            id=protagonist,
            age=29,
            gender="female",
            appearance="late-twenties woman, dark brown hair in a low knot, tired eyes, small gold stud earrings",
            clothing="black silk robe over a white tank, no jewelry except a thin wedding band",
            personality="controlled, then cracking",
        )
    ]
    if any(w in lowered for w in husband_cues):
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
    if any(w in lowered for w in ("her name", "the other woman", "her lipstick", "mistress", "mara")):
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
    return CharacterBible(characters=chars, locations=_guess_locations(), props=_guess_props(text))


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


def infer_beat(scene: Scene, index: int = 0, total: int = 1) -> str:
    blob = f"{scene.emotion} {scene.mood}".lower().replace("-", " ")
    aliases = (
        ("rising_action", ("rising_action", "rising dread", "rising")),
        ("hook", ("hook",)),
        ("conflict", ("conflict",)),
        ("twist", ("twist",)),
        ("ending", ("ending", "ending beat", "end beat")),
    )
    for beat, keys in aliases:
        if any(key in blob for key in keys):
            return beat
    span = max(1, total)
    return BEAT_ORDER[min(len(BEAT_ORDER) - 1, int(index / span * 5))]


def beat_shots(still_id: str, duration: float, beat: str) -> list[Shot]:
    first, second = _BEAT_LENSES.get(beat, _BEAT_LENSES["hook"])
    if duration < 3.2:
        return [
            Shot(camera=first[0], motion=first[1], t_start=0, t_end=duration, still_id=still_id),
        ]
    split = round(duration * 0.45, 2)
    return [
        Shot(camera=first[0], motion=first[1], t_start=0, t_end=split, still_id=still_id),
        Shot(camera=second[0], motion=second[1], t_start=split, t_end=duration, still_id=still_id),
    ]


def apply_beat_lenses(board: Storyboard) -> Storyboard:
    total = max(1, len(board.scenes))
    for i, scene in enumerate(board.scenes):
        beat = infer_beat(scene, i, total)
        scene.shots = beat_shots(scene.still_id, scene.duration_sec, beat)
        repair_scene_shots(scene)
    return board


def _keyword_hit(text: str, keys: tuple[str, ...]) -> bool:
    lowered = text.lower()
    for key in keys:
        if " " in key:
            if key in lowered:
                return True
        elif re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", lowered):
            return True
    return False


def visible_character_ids(vo: str, bible: CharacterBible) -> list[str]:
    ids = [char.id for char in bible.characters]
    if not ids:
        return []
    present = [ids[0]]
    lowered = vo.lower()
    if "husband" in ids and any(cue in lowered for cue in HUSBAND_ON_CAMERA):
        present.append("husband")
    if "other_woman" in ids and any(cue in lowered for cue in OTHER_ON_CAMERA):
        present.append("other_woman")
    return present


def is_insert_scene(location: str, vo: str) -> bool:
    blob = f"{location} {vo}".lower()
    if not any(marker in blob for marker in INSERT_MARKERS):
        return False
    sents = [s for s in re.split(r"(?<=[.!?])\s+", vo.strip()) if s.strip()] or [vo]
    insert_sents = sum(1 for sent in sents if any(marker in sent.lower() for marker in INSERT_MARKERS))
    if len(vo.split()) <= 16:
        return True
    return insert_sents >= max(1, math.ceil(len(sents) / 2))


def _slug_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:40] or "place"


def _match_location(blob: str, locations: list[AssetRef]) -> AssetRef | None:
    by_id = {loc.id: loc for loc in locations}
    for loc_id, _desc, _appearance, keys in LOCATION_CATALOG:
        if _keyword_hit(blob, keys) and loc_id in by_id:
            return by_id[loc_id]
    for loc in locations:
        tokens = tuple([loc.id] + [w for w in loc.description.lower().split() if len(w) > 4])
        if _keyword_hit(blob, tokens):
            return loc
    return None


def pick_location(
    vo: str,
    index: int,
    locations: list[AssetRef],
    previous: AssetRef | None = None,
) -> AssetRef:
    if not locations:
        loc_id, desc, appearance, _keys = LOCATION_CATALOG[(index - 1) % len(LOCATION_CATALOG)]
        return AssetRef(id=loc_id, description=desc, appearance=appearance)
    matched = _match_location(vo, locations)
    if matched:
        return matched
    if previous and previous.id in {loc.id for loc in locations}:
        return previous
    return locations[0]


def replan_locations(board: Storyboard, bible: CharacterBible) -> None:
    """Re-bind location_id from VO so leftover catalog rotation does not invent a street."""
    locations = list(bible.locations) or _guess_locations()
    previous: AssetRef | None = None
    for i, scene in enumerate(board.scenes, start=1):
        loc = pick_location(scene.dialogue_or_vo, i, locations, previous=previous)
        insert = is_insert_scene(scene.location, scene.dialogue_or_vo)
        if insert and previous:
            loc = previous
            scene.use_location_ref = False
        scene.location_id = loc.id
        if not insert:
            scene.location = loc.description
        previous = loc


def bind_scene_assets(board: Storyboard, bible: CharacterBible) -> None:
    by_id = {loc.id: loc for loc in bible.locations}
    reused: dict[str, str] = {}
    for loc in bible.locations:
        reused[loc.description.strip().lower()] = loc.id
        reused[loc.id] = loc.id
    prop_ids = {prop.id for prop in bible.props}
    for scene in board.scenes:
        if scene.location_id and scene.location_id in by_id:
            if not scene.location:
                scene.location = by_id[scene.location_id].description
        else:
            key = (scene.location or "").strip().lower()
            if key in reused:
                scene.location_id = reused[key]
            else:
                matched = _match_location(f"{scene.location} {scene.dialogue_or_vo}", bible.locations)
                if matched:
                    scene.location_id = matched.id
                    if key:
                        reused[key] = matched.id
                else:
                    slug = _slug_id(scene.location or f"place_{scene.index}")
                    scene.location_id = slug
                    if key:
                        reused[key] = slug
        if is_insert_scene(scene.location, scene.dialogue_or_vo):
            scene.use_location_ref = False
            if "phone" in f"{scene.location} {scene.dialogue_or_vo}".lower() and len(scene.dialogue_or_vo.split()) <= 16:
                scene.use_face_ref = False
        if "phone" in prop_ids and "phone" in scene.dialogue_or_vo.lower() and "phone" not in scene.prop_ids:
            scene.prop_ids.append("phone")


def normalize_storyboard(board: Storyboard, bible: CharacterBible) -> Storyboard:
    valid = {char.id for char in bible.characters}
    default = bible.characters[0].id
    for scene in board.scenes:
        if scene.speaker_id and scene.speaker_id in valid:
            extras = [cid for cid in scene.characters if cid in valid and cid != scene.speaker_id]
            scene.characters = [scene.speaker_id] + extras[:1]
        else:
            scene.characters = [cid for cid in visible_character_ids(scene.dialogue_or_vo, bible) if cid in valid] or [default]
        if scene.duration_sec <= 0:
            scene.duration_sec = 4.0
        repair_scene_shots(scene)
    apply_beat_lenses(board)
    bind_scene_assets(board, bible)
    return board


def fallback_analyze(story: StoryInput) -> tuple[CharacterBible, StoryStructure]:
    return _guess_characters(story.text), _guess_structure(story.text, story.target_seconds)


def _scale_scenes(scenes: list[Scene], target: float) -> None:
    scale = target / max(0.1, sum(s.duration_sec for s in scenes))
    for scene in scenes:
        scene.duration_sec = round(scene.duration_sec * scale, 2)
        for shot in scene.shots:
            shot.t_start = round(shot.t_start * scale, 2)
            shot.t_end = round(shot.t_end * scale, 2)
        repair_scene_shots(scene)


def _plan_dialogue(
    story: StoryInput,
    bible: CharacterBible,
    structure: StoryStructure,
    cues: list[tuple[str, str, str]],
) -> Storyboard:
    groups = _merge_dialogue_cues(cues, max(4, min(15, round(story.target_seconds / 5))))
    total_words = sum(len(item[2].split()) for item in groups) or 1
    locations = list(bible.locations) or _guess_locations()
    scenes: list[Scene] = []
    prev_speaker: str | None = None
    for i, (label, place, spoken) in enumerate(groups, start=1):
        speaker = resolve_speaker_id(label, bible)
        duration = max(2.8, story.target_seconds * (len(spoken.split()) / total_words))
        still_id = f"still_{i:02d}"
        beat_name = BEAT_ORDER[min(len(BEAT_ORDER) - 1, int((i - 1) / max(1, len(groups)) * 5))]
        previous = next((item for item in locations if item.id == scenes[-1].location_id), None) if scenes else None
        loc = pick_location(f"{place} {spoken}", i, locations, previous=previous)
        other = prev_speaker if prev_speaker and prev_speaker != speaker else None
        action = (
            f"{speaker} speaking to {other} in {loc.description}"
            if other
            else f"{speaker} speaking in {loc.description}"
        )
        scenes.append(
            Scene(
                index=i,
                duration_sec=round(duration, 2),
                location=loc.description,
                location_id=loc.id,
                characters=[speaker],
                prop_ids=["phone"] if "phone" in spoken.lower() and any(p.id == "phone" for p in bible.props) else [],
                emotion=beat_name if beat_name != "rising_action" else "rising dread",
                action=action,
                dialogue_or_vo=spoken,
                lighting="practical lamps, cinematic contrast, 9:16",
                mood=beat_name,
                consistency_notes="same wardrobe; reverse shot on the speaker",
                still_id=still_id,
                shots=beat_shots(still_id, round(duration, 2), beat_name),
                use_face_ref=True,
                use_location_ref=True,
                speaker_id=speaker,
            )
        )
        prev_speaker = speaker
    _scale_scenes(scenes, float(story.target_seconds))
    title = f"{groups[0][0]}: {groups[0][2]}"[:72] if groups else "Untitled short"
    board = Storyboard(title=title, target_seconds=float(story.target_seconds), language=story.language, scenes=scenes)
    return normalize_storyboard(board, bible)


def fallback_plan(story: StoryInput, bible: CharacterBible, structure: StoryStructure) -> Storyboard:
    cues = parse_dialogue_cues(story.text)
    if is_dialogue_script(story.text, cues):
        return _plan_dialogue(story, bible, structure, cues)
    target_scenes = max(8, min(15, round(story.target_seconds / 6)))
    groups = _chunk_sentences(_sentences(story.text), target_scenes)
    total_words = sum(len(" ".join(g).split()) for g in groups) or 1
    locations = list(bible.locations) or _guess_locations()
    scenes: list[Scene] = []
    beats = [structure.hook, structure.conflict, structure.rising_action, structure.twist, structure.ending]
    for i, group in enumerate(groups, start=1):
        vo = " ".join(group)
        duration = max(3.5, story.target_seconds * (len(vo.split()) / total_words))
        still_id = f"still_{i:02d}"
        beat_name = BEAT_ORDER[min(len(BEAT_ORDER) - 1, int((i - 1) / max(1, len(groups)) * 5))]
        back = any(w in vo.lower() for w in ("walked away", "his back", "turned away"))
        present = visible_character_ids(vo, bible)
        previous = next((item for item in locations if item.id == scenes[-1].location_id), None) if scenes else None
        loc = pick_location(vo, i, locations, previous=previous)
        insert = is_insert_scene(loc.description, vo)
        if insert and scenes:
            prev = next((item for item in locations if item.id == scenes[-1].location_id), None)
            if prev:
                loc = prev
        location_label = "phone screen close" if insert else loc.description
        scenes.append(
            Scene(
                index=i,
                duration_sec=round(duration, 2),
                location=location_label,
                location_id=loc.id,
                characters=present,
                prop_ids=["phone"] if (insert or "phone" in vo.lower()) and any(p.id == "phone" for p in bible.props) else [],
                emotion=beat_name if beat_name != "rising_action" else "rising dread",
                action=vo[:140],
                dialogue_or_vo=vo,
                lighting="practical lamps, cinematic contrast, 9:16",
                mood=beats[min(i - 1, len(beats) - 1)][:80],
                consistency_notes="keep narrator wardrobe and wedding band",
                still_id=still_id,
                shots=beat_shots(still_id, round(duration, 2), beat_name),
                use_face_ref=not back and not (insert and len(vo.split()) <= 16),
                use_location_ref=not insert,
            )
        )
    scale = story.target_seconds / max(0.1, sum(s.duration_sec for s in scenes))
    for scene in scenes:
        scene.duration_sec = round(scene.duration_sec * scale, 2)
        for shot in scene.shots:
            shot.t_start = round(shot.t_start * scale, 2)
            shot.t_end = round(shot.t_end * scale, 2)
        repair_scene_shots(scene)
    title = story.text.strip().split("\n")[0][:72] or "Untitled short"
    board = Storyboard(title=title, target_seconds=float(story.target_seconds), language=story.language, scenes=scenes)
    return normalize_storyboard(board, bible)
