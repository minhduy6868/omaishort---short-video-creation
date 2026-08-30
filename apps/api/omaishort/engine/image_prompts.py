from __future__ import annotations

from omaishort.providers.llm import load_prompt
from omaishort_schema.models import Character, CharacterBible, Scene, Storyboard


def character_block(char: Character) -> str:
    return (
        f"- {char.id}: {char.age or ''} {char.gender or ''}. "
        f"Appearance lock: {char.appearance}. Clothing lock: {char.clothing}."
    )


def build_ref_prompt(char: Character) -> str:
    template = load_prompt("character_ref.txt")
    return template.format(
        id=char.id,
        age=char.age or "adult",
        gender=char.gender or "person",
        appearance=char.appearance,
        clothing=char.clothing,
    )


def build_scene_prompt(scene: Scene, bible: CharacterBible) -> str:
    by_id = {c.id: c for c in bible.characters}
    blocks = []
    refs = []
    for cid in scene.characters:
        char = by_id.get(cid)
        if not char:
            continue
        blocks.append(character_block(char))
        if scene.use_face_ref and char.reference_image:
            refs.append(char.reference_image)
    template = load_prompt("scene_still.txt")
    camera = scene.shots[0].camera.value if scene.shots else "medium"
    ref_note = (
        "Use attached character reference images as identity lock."
        if scene.use_face_ref and refs
        else "Do not attach a face reference (back-turned / distant / obscured)."
    )
    return template.format(
        location=scene.location,
        action=scene.action,
        emotion=scene.emotion,
        mood=scene.mood,
        lighting=scene.lighting,
        camera=camera,
        character_blocks="\n".join(blocks) or "- empty frame",
        ref_note=ref_note,
        consistency_notes=scene.consistency_notes or "none",
    )


def fill_image_prompts(board: Storyboard, bible: CharacterBible) -> None:
    for scene in board.scenes:
        scene.image_prompt = build_scene_prompt(scene, bible)
