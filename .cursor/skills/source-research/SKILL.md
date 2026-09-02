---
name: source-research
description: Maps external video repos (MoneyPrinter, OpenMontage, ArcReel, FTL, Story Forge, Wind Comic, FramePack) onto omaishort without forking. Use when the user asks to tham khảo source, nâng cấp pipeline, add I2V, captions, or compare products.
---

# Source research

Read `docs/RESEARCH.md` and `docs/ROADMAP.md` first.

Rules:

- Do not clone MoneyPrinter or OpenMontage into this repo. Reimplement behind existing protocols (`ImageProvider`, `TTSProvider`, later `VideoProvider`).
- OpenMontage is AGPL — patterns and stage names only.
- MoneyPrinter is a **stock-short factory**. Steal TTS timestamps, BGM ducking, LLM gateway. Do not make Pexels the default picture.
- Elevation order: P1 captions/mix → P2 location/prop bible → P3 review gates → P4 I2V → P5 gateways → P6 factory/edit-agent.
- Drama beats and “one still, many shots” stay mandatory. New features must not revert to one image per sentence.
