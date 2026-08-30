---
name: scene-planner
description: Plans omaishort scenes with duration and multi-shot Ken Burns on a shared still. Use when editing the Scene Planner, storyboard schema, or shot/camera/motion logic.
---

# Scene Planner

Read `prompts/planner.txt` and `apps/api/omaishort/engine/planner.py`.

Hard rules:

- 8–15 scenes for a 60s short. Merge lines that share location and emotion.
- One `still_id` per scene. Shots reuse it.
- Shot fields: `camera` (wide|medium|close_up), `motion` (hold|zoom_in|zoom_out|pan_left|pan_right), `t_start`, `t_end`.
- `dialogue_or_vo` is the TTS line for that scene.
- Target ~12–20 stills for 60–90s, not one still per sentence.

After TTS, `engine/rescale.py` stretches all times to the real voiceover length.
