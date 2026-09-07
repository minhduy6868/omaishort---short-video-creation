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


def motion_prompt(scene: Scene) -> str:
    shot = scene.shots[0]
    camera = _CAMERA.get(shot.camera, _CAMERA[Camera.medium])
    move = _MOTION.get(shot.motion, _MOTION[Motion.hold])
    # Wind Comic: never put VO/dialogue in the I2V prompt (garbled on-screen text).
    action = (scene.action or scene.emotion or "").strip()[:180]
    feel = (scene.emotion or scene.mood or "").strip()[:40]
    intensity = f" Emotion: {feel}." if feel else ""
    return (
        f"{camera}, {move}. Action: {action}.{intensity} "
        "Keep the exact person, face, hair, and clothes from the start frame. "
        "Photoreal short-drama, 9:16 vertical, no text, no subtitles, no watermark."
    )
