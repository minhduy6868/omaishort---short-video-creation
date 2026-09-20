from __future__ import annotations

from omaishort_schema.models import Camera, Motion, Scene

_CAMERA = {
    Camera.wide: "slow cinematic push-in from a wide frame",
    Camera.medium: "subtle handheld breathe in a medium shot",
    Camera.close_up: "slow dolly into a close-up, eyes alive",
}
_MOTION = {
    Motion.hold: "locked-off camera, subject breathes and micro-moves",
    Motion.zoom_in: "slow zoom in",
    Motion.zoom_out: "slow zoom out",
    Motion.pan_left: "slow pan left",
    Motion.pan_right: "slow pan right",
}
# One I2V clip covers the whole scene — both beat-lens shots, camera + action only.
_BEAT_MOVE = {
    "hook": "hook punch-in: start medium, slow push into a tight close-up, faces react",
    "conflict": "conflict tighten: hold medium, then slow push into the face",
    "rising_action": "rising pan: slow pan right from wide, then medium push-in",
    "twist": "twist punch-in: stay close-up, hold then push into the eyes",
    "ending": "ending pull-out: hold medium, then wide zoom out",
}


def motion_prompt(
    scene: Scene,
    *,
    beat: str | None = None,
    has_end_frame: bool = False,
    chained: bool = False,
) -> str:
    shot = scene.shots[0]
    camera = _CAMERA.get(shot.camera, _CAMERA[Camera.medium])
    move = _MOTION.get(shot.motion, _MOTION[Motion.hold])
    if len(scene.shots) > 1:
        last = scene.shots[-1]
        camera = f"{camera}, then {_CAMERA.get(last.camera, _CAMERA[Camera.medium])}"
        move = f"{move}, then {_MOTION.get(last.motion, _MOTION[Motion.hold])}"
    beat_move = _BEAT_MOVE.get(beat or "", "")
    lens = beat_move or f"{camera}, {move}"
    # Wind Comic: never put VO/dialogue in the I2V prompt (garbled on-screen text).
    action = (scene.action or scene.emotion or "").strip()[:180]
    feel = (scene.emotion or scene.mood or "").strip()[:40]
    intensity = f" Emotion: {feel}." if feel else ""
    if chained and has_end_frame:
        frames = (
            "Continue from this start frame toward the last frame. "
            "Same person walking the cut; do not swap faces. "
        )
    elif chained:
        frames = "Continue from this start frame; same person, same clothes. "
    elif has_end_frame:
        frames = "Animate from the start frame toward the last frame. "
    else:
        frames = ""
    return (
        f"{lens}. Action: {action}.{intensity} "
        f"{frames}"
        "Keep the exact person, face, hair, and clothes from the start frame. "
        "Photoreal short-drama, 9:16 vertical, no text, no subtitles, no watermark."
    )
