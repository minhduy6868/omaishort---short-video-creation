# Remotion scaffold

MVP rendering is **FFmpeg Ken Burns**, not Remotion.

Each job writes `data/jobs/<id>/timeline.json` with three tracks matching the official Remotion prompt-to-video template:

- `elements` — stills + camera motion
- `text` — VO lines
- `audio` — voiceover

Point a later Remotion composition at that file. Do not change the planner to emit a different timeline shape.
