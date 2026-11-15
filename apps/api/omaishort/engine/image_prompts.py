from __future__ import annotations

from pathlib import Path

from omaishort.providers.llm import load_prompt
from omaishort_schema.models import AssetRef, Character, CharacterBible, Scene, Storyboard


def character_block(char: Character) -> str:
    personality = (char.personality or "").strip()
    extra = f" Personality lock: {personality}." if personality else ""
    return (
        f"- {char.id}: {char.age or ''} {char.gender or ''}. "
        f"Appearance lock: {char.appearance}. Clothing lock: {char.clothing}.{extra}"
    )


def asset_block(asset: AssetRef, kind: str) -> str:
    appearance = asset.appearance or asset.description
    return f"- {kind} {asset.id}: {asset.description}. Appearance lock: {appearance}."


def build_ref_prompt(char: Character) -> str:
    template = load_prompt("character_ref.txt")
    return template.format(
        id=char.id,
        age=char.age or "adult",
        gender=char.gender or "person",
        appearance=char.appearance,
        clothing=char.clothing,
        personality=char.personality or "neutral, in-character",
    )


def build_location_prompt(loc: AssetRef) -> str:
    template = load_prompt("location_ref.txt")
    return template.format(
        id=loc.id,
        description=loc.description,
        appearance=loc.appearance or loc.description,
    )


def build_prop_prompt(prop: AssetRef) -> str:
    template = load_prompt("prop_ref.txt")
    return template.format(
        id=prop.id,
        description=prop.description,
        appearance=prop.appearance or prop.description,
    )


def _vo_visual_gist(vo: str, *, limit: int = 12) -> str:
    """Short noun/gesture cues from VO — never a quote for the image model."""
    text = " ".join(str(vo or "").replace('"', " ").replace("'", " ").split())
    if not text:
        return ""
    stop = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "to",
        "of",
        "in",
        "on",
        "at",
        "for",
        "is",
        "are",
        "was",
        "were",
        "i",
        "you",
        "he",
        "she",
        "we",
        "they",
        "my",
        "your",
        "his",
        "her",
        "their",
        "this",
        "that",
        "with",
        "from",
        "said",
        "says",
        "say",
        "told",
        "tell",
    }
    words: list[str] = []
    for raw in text.split():
        token = "".join(ch for ch in raw.lower() if ch.isalnum() or ch == "-")
        if len(token) < 3 or token in stop:
            continue
        if token not in words:
            words.append(token)
        if len(words) >= limit:
            break
    return " ".join(words)


def visual_action(scene: Scene) -> str:
    """Camera action for stills — never dump voiceover into the image prompt."""
    loc = scene.location or "interior"
    action = " ".join(str(scene.action or "").split())
    gist = _vo_visual_gist(scene.dialogue_or_vo or "")
    blob = f"{scene.location} {scene.dialogue_or_vo} {scene.action}".lower()
    if not scene.use_face_ref and not scene.characters:
        # News/knowledge ảnh ghép: keep uninhabited, pin still to this beat's VO gist.
        base = action or f"uninhabited editorial still of {loc}"
        cue = ""
        if gist:
            missing = [
                token
                for token in gist.split()
                if token not in base.lower()
            ]
            if missing:
                cue = f", suggesting {' '.join(missing[:8])}"
            elif not action:
                cue = f", suggesting {gist}"
        return (
            f"{base}{cue}, zero people, zero faces, no text on image, "
            "no soap-opera couple, no narrator portrait"
        )
    if not scene.use_face_ref:
        if any(token in blob for token in ("phone", "lock screen", "message", "screenshot")):
            return (
                "extreme close-up of two hands holding a smartphone, lock screen lit, "
                "no standing people, no hallway"
            )
        return "extreme close-up of hands and the object only, no standing portraits"
    who = " and ".join(scene.characters) if scene.characters else "nobody"
    beat = scene.emotion or "drama"
    light = (scene.lighting or "").strip()
    mood = (scene.mood or beat).strip()
    look = f", {light}" if light else ""
    moment = action or (f"moment suggesting {gist}" if gist else "silent beat")
    cue = f", visual cue: {gist}" if gist and gist.lower() not in moment.lower() else ""
    return (
        f"only {who} in {loc}, {moment}{cue}, {beat} beat, {mood} mood{look}, "
        "silent photographic moment, no text, no speech bubbles, do not quote dialogue"
    )


def build_scene_prompt(scene: Scene, bible: CharacterBible) -> str:
    by_id = {c.id: c for c in bible.characters}
    loc_by_id = {loc.id: loc for loc in bible.locations}
    prop_by_id = {prop.id: prop for prop in bible.props}
    blocks = []
    for cid in scene.characters:
        char = by_id.get(cid)
        if not char:
            continue
        blocks.append(character_block(char))
    loc = loc_by_id.get(scene.location_id or "")
    location_lock = (
        asset_block(loc, "location")
        if loc
        else f"- location: {scene.location}"
    )
    prop_blocks = [asset_block(prop_by_id[pid], "prop") for pid in scene.prop_ids if pid in prop_by_id]
    is_brief = not scene.use_face_ref and not scene.characters
    template = load_prompt("scene_still_brief.txt" if is_brief else "scene_still.txt")
    camera = scene.shots[0].camera.value if scene.shots else "medium"
    on_camera = ", ".join(scene.characters) if scene.characters else "nobody"
    if is_brief:
        cast_rule = "BRIEF: uninhabited editorial still. Zero people, zero faces, zero couple."
        ref_note = "Do not attach a face reference."
        location_ref_note = "Do not use a character or location passport. Generate a fresh empty set."
    elif not scene.use_face_ref:
        cast_rule = (
            "INSERT: no full-body people, no crowd. Phone, hands, or object only. "
            f"Do not draw {on_camera} as a standing portrait unless the action is a face in a screen."
        )
        ref_note = "Do not attach a face reference (back-turned / distant / obscured)."
        location_ref_note = (
            "Use attached location passport as set lock. Same kitchen/hallway must match prior scenes."
            if scene.use_location_ref and loc
            else "Hands-only or object close-up: do not use the location passport still."
        )
    else:
        cast_rule = (
            f"On camera ONLY: {on_camera}. Do not depict anyone else. "
            "No extra people, no crowd, no second couple."
        )
        ref_note = "Use attached character reference images as identity lock."
        location_ref_note = (
            "Use attached location passport as set lock. Same kitchen/hallway must match prior scenes."
            if scene.use_location_ref and loc
            else "Hands-only or object close-up: do not use the location passport still."
        )
    return template.format(
        location=scene.location,
        location_id=scene.location_id or "none",
        location_lock=location_lock,
        action=visual_action(scene),
        emotion=scene.emotion,
        mood=scene.mood,
        lighting=scene.lighting,
        camera=camera,
        cast_rule=cast_rule,
        still_id=scene.still_id,
        character_blocks="\n".join(blocks) or "- empty frame",
        prop_blocks="\n".join(prop_blocks) or "- no featured props",
        ref_note=ref_note,
        location_ref_note=location_ref_note,
        consistency_notes=scene.consistency_notes or "none",
    )


def fill_image_prompts(board: Storyboard, bible: CharacterBible) -> None:
    for scene in board.scenes:
        scene.image_prompt = build_scene_prompt(scene, bible)


def scene_still_refs(
    scene: Scene,
    *,
    refs_dir: Path,
    location_dir: Path,
    prop_dir: Path,
) -> list[Path]:
    """Drama still inputs: on-camera passports, then location, then props (LocalForge referenceAssetIds)."""
    out: list[Path] = []
    if scene.use_face_ref:
        for cid in scene.characters:
            path = refs_dir / f"{cid}.png"
            if path.is_file():
                out.append(path)
    if scene.use_location_ref and scene.location_id:
        path = location_dir / f"{scene.location_id}.png"
        if path.is_file():
            out.append(path)
    for pid in scene.prop_ids:
        path = prop_dir / f"{pid}.png"
        if path.is_file():
            out.append(path)
    return out
