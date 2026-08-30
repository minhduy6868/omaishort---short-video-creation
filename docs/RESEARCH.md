# Research — Story → AI short

omaishort **does not fork** a single repo. It copies contracts, then implements its own engine.

## What we take

### 1. AIStoryVideoGenerator
https://github.com/yenloned/AIStoryVideoGenerator

Take: emotion in image prompts, TTS, **sync scene duration to real audio**, FFmpeg assemble.

Skip: one image per text chunk; in-process Stable Diffusion as the only image path.

Used in: `providers/tts.py`, `engine/rescale.py`, `engine/compose.py`.

### 2. story2video-style scene contract

Story → chapters/scenes with setting, character, action, mood, dialogue, duration, camera, lighting, motion, consistency notes, SQLite storyboard.

That JSON **is** `Scene` + `Shot` in `packages/schema`.

### 3. AI-Story-To-Movie
https://github.com/SDSmirnov/AI-Story-To-Movie

Take: Character Bible → passport stills in `data/jobs/<id>/refs/` → inject references into later scene prompts. Skip face-ref when the character is back-turned.

Skip: lock-in to Imagen/Veo.

Used in: `engine/analyzer.py`, `engine/image_prompts.py`, `pipeline.py` refs stage.

### 4. Remotion prompt-to-video
https://github.com/remotion-dev/template-prompt-to-video

Take: `timeline.json` with three tracks — `elements` (stills + motion), `text`, `audio`.

Skip: OpenAI+ElevenLabs-only CLI; explainer/fun-fact topics.

MVP **renders with FFmpeg**. `apps/remotion` is a scaffold for a later player.

### 5. Montage / prompt-to-video agents
https://github.com/AliHamzaAzam/montage-ai  
https://github.com/google/project-montage

Take later: multi-agent + natural-language **edit agent** (“darken scene 5”). Not in MVP.

## What omaishort does differently

1. **Ken Burns over stills**, not one generate per sentence. Target ~12–20 stills for 60–90s.
2. **Character Bible is source of truth.** Scenes only store ids + emotion/location/camera/action.
3. **Drama structure is mandatory** (hook/conflict/rising/twist/ending).
4. **Provider chain** so a Windows machine without GPU still emits MP4.

## Future (not coded)

Long story → Part 1..N (60s each) with continuity of character/state/location. Edit-agent regenerates one scene. I2V optional upgrade of an approved still.
