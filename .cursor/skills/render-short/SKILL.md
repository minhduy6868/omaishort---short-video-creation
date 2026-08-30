---
name: render-short
description: Renders an omaishort 1080x1920 MP4 from stills, TTS, Whisper/ASS captions, and FFmpeg Ken Burns. Use when changing compose, captions, timeline.json, or the render job stage.
---

# Render short

Order: stills → TTS → probe duration → rescale storyboard → word timestamps (faster-whisper or even-split) → ASS → FFmpeg zoompan clips → concat → mix VO → burn subtitles → `short.mp4`.

Also write `timeline.json` with `elements`, `text`, `audio` (Remotion prompt-to-video shape). Do not make Remotion required for MVP.

Windows: run the subtitle ffmpeg pass with cwd = render dir and `subtitles=captions.ass`.

Output is always 1080×1920 at 30fps.
