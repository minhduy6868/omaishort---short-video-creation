from __future__ import annotations

from pathlib import Path

from omaishort_schema.models import Storyboard, Timeline, TimelineAudio, TimelineElement, TimelineText


def build_timeline(
    board: Storyboard,
    stills: dict[str, Path],
    audio_path: Path,
    audio_seconds: float,
) -> Timeline:
    elements: list[TimelineElement] = []
    texts: list[TimelineText] = []
    t_scene = 0.0
    for scene in board.scenes:
        for shot in scene.shots:
            src = stills.get(scene.still_id)
            elements.append(
                TimelineElement(
                    id=f"{scene.still_id}_{shot.camera.value}_{shot.t_start}",
                    src=src.as_posix() if src else "",
                    from_sec=round(t_scene + shot.t_start, 3),
                    duration_sec=round(shot.t_end - shot.t_start, 3),
                    animation=shot.motion.value,
                    camera=shot.camera.value,
                )
            )
        texts.append(
            TimelineText(
                text=scene.dialogue_or_vo,
                from_sec=round(t_scene, 3),
                duration_sec=round(scene.duration_sec, 3),
            )
        )
        t_scene += scene.duration_sec
    return Timeline(
        shortTitle=board.title[:48],
        elements=elements,
        text=texts,
        audio=[TimelineAudio(src=audio_path.as_posix(), duration_sec=audio_seconds)],
    )
