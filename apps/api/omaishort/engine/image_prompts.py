from __future__ import annotations

from omaishort.providers.llm import load_prompt
from omaishort_schema.models import AssetRef, Character, CharacterBible, Scene, Storyboard


def character_block(char: Character) -> str:
    return (
        f"- {char.id}: {char.age or ''} {char.gender or ''}. "
        f"Appearance lock: {char.appearance}. Clothing lock: {char.clothing}."
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


def visual_action(scene: Scene) -> str:
    """Camera action for stills — never dump voiceover into the image prompt."""
    loc = scene.location or "interior"
    blob = f"{scene.location} {scene.dialogue_or_vo} {scene.action}".lower()
    if not scene.use_face_ref and not scene.characters:
        return scene.action or (
            f"uninhabited editorial still of {loc}, zero people, zero faces"
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
    return (
        f"only {who} in {loc}, {beat} beat, silent photographic moment, "
        "do not illustrate spoken dialogue or off-screen people"
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
