"""Muse drama shot planning — same contracts as videoai museVideoPlan (clean-room)."""

from __future__ import annotations

import json
import math
import re

MUSE_VIDEO_DURATIONS = (10, 20, 30, 40, 60)
MUSE_SHOT_SEC = 10
# Cap multi-shot cost: long scenes still get continuity, but not 6× Hatch jobs.
MUSE_MAX_SHOTS = 2


def normalize_muse_duration(value: object) -> int:
    duration = int(round(float(value or 0)))
    return duration if duration in MUSE_VIDEO_DURATIONS else 30


def muse_scene_count_for_duration(duration: float) -> int:
    """How many ~10s Muse takes for one omaishort scene (cap 2 shots)."""
    seconds = max(1.0, float(duration or 10))
    if seconds <= MUSE_SHOT_SEC:
        return 1
    return max(1, min(MUSE_MAX_SHOTS, int(math.ceil(seconds / MUSE_SHOT_SEC))))


def muse_scene_draft_prompt(idea: str, scene_count: int) -> str:
    return "\n".join(
        [
            f"You are a short-video director. Write EXACTLY {scene_count} shots for ONE continuous story.",
            "Each shot is ONE approximately 10-second take, written as a self-contained English prompt for a video generator.",
            "Keep the user idea as the source of truth. Preserve every subject, object, place, action, emotion, product detail and spoken line in its original order. Do not replace, drop, reinterpret or add plot events, characters or props. Add only camera, lighting, lens and texture detail.",
            "Lock each character identity across every shot: preserve the same face, apparent age, skin tone, hair, build, outfit and voice; do not recast, redesign, or change these traits. Keep location, time of day, weather, props and visual style consistent. Each shot continues directly from the prior shot. If the idea has more content than fits one shot, split it across the shots in order.",
            "Each shot must restate the visual details needed to stand alone. Use one clear action and one camera move per shot. Write spoken lines only when the user requested them.",
            f'Output exactly {scene_count} blocks. Each block starts on its own line with "### SHOT n" where n runs from 1 to {scene_count}, followed by that shot prompt. No JSON, markdown fences, introduction or conclusion.',
            "",
            f"Idea: {str(idea or '').strip()}",
            f"Shots: {scene_count}",
        ]
    )


def parse_muse_scenes(value: object, expected_count: int) -> list[str] | None:
    text = re.sub(r"```[a-z]*\s*", "", str(value or ""), flags=re.I)
    text = text.replace("```", "").strip()
    if not text:
        return None

    headings = list(re.finditer(r"^\s*#{2,}\s*(?:shot|scene|cảnh)\s*\d+[^\r\n]*\r?\n", text, re.I | re.M))
    if headings:
        scenes = [
            text[h.end() : (headings[i + 1].start() if i + 1 < len(headings) else len(text))].strip()
            for i, h in enumerate(headings)
        ]
        scenes = [s for s in scenes if s]
        return scenes if len(scenes) == expected_count else None

    json_start = text.find("[")
    json_end = text.rfind("]")
    if json_start >= 0 and json_end > json_start:
        try:
            parsed = json.loads(text[json_start : json_end + 1])
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None:
            if isinstance(parsed, dict):
                values = parsed.get("shots") or parsed.get("scenes") or list(parsed.values())
            else:
                values = parsed
            out: list[str] = []
            for item in values if isinstance(values, list) else []:
                if isinstance(item, str):
                    piece = item.strip()
                elif isinstance(item, dict):
                    piece = str(item.get("prompt") or item.get("text") or item.get("description") or "").strip()
                else:
                    piece = ""
                if piece:
                    out.append(piece)
            if len(out) == expected_count:
                return out

    numbered = [
        part.strip()
        for part in re.split(r"^\s*(?:(?:shot|scene|cảnh)\s*)?\d+\s*[.:)\-–]\s+", text, flags=re.I | re.M)
        if part.strip()
    ]
    return numbered if len(numbered) == expected_count else None


def muse_clip_prompt(scene_prompt: str, *, has_continuity_frame: bool = False) -> str:
    if has_continuity_frame:
        continuity = (
            "Continue the same character identity and exact appearance from the supplied previous-scene "
            "final frame. Treat supplied user reference images as identity anchors; preserve their faces, "
            "hair, age, skin tone, build and outfits."
        )
    else:
        continuity = (
            "Preserve all character identities and exact appearances from the supplied user reference "
            "images. Keep each face, hair, age, skin tone, build and outfit unchanged."
        )
    return (
        "Create a realistic 10-second video.\n"
        f"{continuity}\n"
        f"SCENE (follow exactly; include every action and detail; add nothing else): "
        f"{str(scene_prompt or '').strip()}\n"
        "The output should be about 10 seconds long."
    )
