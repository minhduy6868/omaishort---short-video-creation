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
        repair_scene_shots(scene)
    drift = round(audio_seconds - sum(s.duration_sec for s in board.scenes), 3)
    if board.scenes and abs(drift) >= 0.001:
        last = board.scenes[-1]
        last.duration_sec = round(last.duration_sec + drift, 3)
        repair_scene_shots(last)
    board.target_seconds = round(audio_seconds, 3)
    return board


def repair_scene_shots(scene: Scene) -> None:
    if not scene.shots:
        return
    scene.shots[0].t_start = 0.0
    n = len(scene.shots)
    if n == 1:
        scene.shots[0].t_end = max(0.2, scene.duration_sec)
        return
    raw_lens = [max(0.05, shot.t_end - shot.t_start) for shot in scene.shots]
    total = sum(raw_lens) or 1.0
    t = 0.0
    for i, shot in enumerate(scene.shots):
        shot.t_start = round(t, 3)
        if i == n - 1:
            shot.t_end = round(scene.duration_sec, 3)
        else:
            t += scene.duration_sec * (raw_lens[i] / total)
            shot.t_end = round(t, 3)
        if shot.t_end <= shot.t_start:
            shot.t_end = round(shot.t_start + 0.2, 3)
    scene.shots[-1].t_end = max(scene.shots[-1].t_start + 0.2, scene.duration_sec)


def flatten_shots(board: Storyboard) -> list[tuple[Scene, Shot, float]]:
    """Return (scene, shot, global_start)."""
    t = 0.0
    out: list[tuple[Scene, Shot, float]] = []
    for scene in board.scenes:
        for shot in scene.shots:
            out.append((scene, shot, t + shot.t_start))
        t += scene.duration_sec
    return out
