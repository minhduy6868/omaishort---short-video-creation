---
name: render-short
description: Renders an omaishort 1080x1920 MP4 from stills, TTS, Whisper/ASS captions, and FFmpeg Ken Burns. Use when changing compose, captions, timeline.json, or the render job stage.
---

# Render short

Order: stills → TTS → probe duration → rescale storyboard → word timestamps (faster-whisper or even-split) → ASS → **I2V clip per scene** (`HF_TOKEN` Space or Wan pollen) **or** FFmpeg zoompan at 2160×3840 with cosine ease → concat → mix VO → burn subtitles → `short.mp4` + `render/motion.json`.

Ken Burns is not I2V. `timeline.json` `elements[].type` is `video` only when a real clip was generated.

Also write `timeline.json` with `elements`, `text`, `audio` (Remotion prompt-to-video shape). Do not make Remotion required for MVP.

Windows: run the subtitle ffmpeg pass with cwd = render dir and `subtitles=captions.ass`.

Output is always 1080×1920 at 30fps.
