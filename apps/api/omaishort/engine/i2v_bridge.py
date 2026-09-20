from __future__ import annotations

from pathlib import Path

from omaishort_schema.models import Scene


def can_bridge_frames(current: Scene, nxt: Scene) -> bool:
    """True when next still can be a last frame without swapping identity."""
    if current.still_id == nxt.still_id:
        return False
    if current.use_face_ref != nxt.use_face_ref:
        return False
    if not current.use_face_ref:
        return bool(current.location_id and current.location_id == nxt.location_id)
    return bool(set(current.characters) & set(nxt.characters))


def pick_end_scene(
    scenes: list[Scene],
    index: int,
    stills: dict[str, Path],
) -> Scene | None:
    """Next scene still as last frame (HTTP Frames). Same on-camera ids, not Flow."""
    if index < 0 or index + 1 >= len(scenes):
        return None
    current = scenes[index]
    nxt = scenes[index + 1]
    if not can_bridge_frames(current, nxt):
        return None
    path = stills.get(nxt.still_id)
    if path is None or not path.exists():
        return None
    return nxt


def pick_start_frame(
    current: Scene,
    scene_still: Path,
    *,
    prev: Scene | None,
    prev_tail: Path | None,
    prev_used_end_frame: bool,
) -> Path:
    """Next I2V start: previous last frame when the same people stay in the same set."""
    if prev is None or prev_tail is None or not prev_tail.is_file():
        return scene_still
    if not can_bridge_frames(prev, current):
        return scene_still
    if prev_used_end_frame:
        return prev_tail
    if prev.location_id and prev.location_id == current.location_id:
        return prev_tail
    return scene_still


def drama_clip_plan(
    scenes: list[Scene],
    stills: dict[str, Path],
) -> list[dict[str, str | None]]:
    """One I2V window per drama scene: start still, optional last-frame still."""
    plan: list[dict[str, str | None]] = []
    for index, scene in enumerate(scenes):
        end = pick_end_scene(scenes, index, stills)
        plan.append(
            {
                "still_id": scene.still_id,
                "end_still_id": end.still_id if end is not None else None,
            }
        )
    return plan
