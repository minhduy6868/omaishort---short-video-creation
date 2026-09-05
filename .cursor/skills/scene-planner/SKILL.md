---
name: scene-planner
description: Plans omaishort scenes with duration and multi-shot Ken Burns on a shared still. Use when editing the Scene Planner, storyboard schema, or shot/camera/motion logic.
---

# Scene Planner

Read `prompts/planner.txt` and `apps/api/omaishort/engine/planner.py`.

Hard rules:

- 8–15 scenes for a 60s **drama**. Exactly 5 scenes for **news** or **knowledge** (one still per beat). Merge lines that share location and emotion.
- One `still_id` per scene. Shots reuse it.
- Shot fields: `camera` (wide|medium|close_up), `motion` (hold|zoom_in|zoom_out|pan_left|pan_right), `t_start`, `t_end`.
- After plan, `normalize_storyboard` rewrites shots to beat lenses (hook zoom_in … ending zoom_out). Do not leave a random motion cycle.
- `dialogue_or_vo` is the spoken line. Drama: character speech, not narrator recap; `speaker_id` is the bible id who is talking. News/knowledge: narration VO; `speaker_id` is null and `characters` is empty. News ending beat includes the article outcome. Each still matches that beat's VO (MoneyPrinter per-scene terms on Wikimedia/Openverse, not Pexels).
- `characters` are bible ids **visible in the still**. Mentioning "he said" / "he called" does not put the husband in frame.
- Reuse `location_id` when the place is the same. `use_location_ref=false` on phone/insert shots.
- Target ~12–20 stills for 60–90s, not one still per sentence.

After TTS, `engine/rescale.py` stretches all times to the real voiceover length.
