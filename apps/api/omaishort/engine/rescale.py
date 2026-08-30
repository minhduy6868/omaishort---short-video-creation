from __future__ import annotations

from omaishort_schema.models import Scene, Shot, Storyboard


def rescale_to_audio(board: Storyboard, audio_seconds: float) -> Storyboard:
    planned = sum(s.duration_sec for s in board.scenes)
    if planned <= 0 or audio_seconds <= 0:
        return board
    factor = audio_seconds / planned
    for scene in board.scenes:
        scene.duration_sec = round(scene.duration_sec * factor, 3)
        for shot in scene.shots:
            shot.t_start = round(shot.t_start * factor, 3)
            shot.t_end = round(shot.t_end * factor, 3)
        _repair_shots(scene)
    board.target_seconds = round(audio_seconds, 3)
    return board


def _repair_shots(scene: Scene) -> None:
    if not scene.shots:
        return
    scene.shots[0].t_start = 0.0
    scene.shots[-1].t_end = scene.duration_sec
    for i in range(1, len(scene.shots)):
        scene.shots[i].t_start = scene.shots[i - 1].t_end
    for shot in scene.shots:
        if shot.t_end <= shot.t_start:
            shot.t_end = shot.t_start + 0.2


def flatten_shots(board: Storyboard) -> list[tuple[Scene, Shot, float]]:
    """Return (scene, shot, global_start)."""
    t = 0.0
    out: list[tuple[Scene, Shot, float]] = []
    for scene in board.scenes:
        for shot in scene.shots:
            out.append((scene, shot, t + shot.t_start))
        t += scene.duration_sec
    return out
