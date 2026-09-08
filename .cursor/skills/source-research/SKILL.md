---
name: source-research
description: Maps external video repos (MoneyPrinter, OpenMontage, ArcReel, FTL, Story Forge, Wind Comic, FramePack, Seedance wrappers) onto omaishort without forking. Use when the user asks to tham khảo source, nâng cấp pipeline, add I2V, captions, or compare products.
---

# Source research

Read `docs/RESEARCH.md` and `docs/ROADMAP.md` first.

Rules:

- Do not clone MoneyPrinter or OpenMontage into this repo. Reimplement behind existing protocols (`ImageProvider`, `TTSProvider`, later `VideoProvider`).
- OpenMontage is AGPL — patterns and stage names only.
- MoneyPrinter is a **stock-short factory**. Steal TTS timestamps, BGM ducking, LLM gateway, and **per-scene search terms**. Do not make Pexels the default picture. Optional Ark Seedance in MPT is a paid clip gateway, not the core product.
- Seedance (ByteDance) is closed I2V. Map first-frame + 9:16 + submit/poll onto `VideoProvider`. Do not clone ginigen/Seedance-Free, muapi wrappers, or scrape Dreamina. Free-ish drama I2V stays HF Wan/LTX.
- Google Veo I2V is Gemini/Vertex HTTP (paid, 4/6/8s, 9:16) or Pollinations `model=veo`. Google Flow daily credits are UI-only. Do not clone gflow-cli, flow-py, flowkit, or ginigen/VEO3-Free. ChatGPT-web is the only in-process browser exception (knowledge VO).
- Trials: HF ZeroGPU (free login ~5 min/day) and Pollinations grant pollen (wan-fast is cheap) are engine-usable. WaveSpeed $1 is HTTP (`WAVESPEED_API_KEY`) but the API key may need a first top-up. Gemini Veo has no API free tier. GCP $300 cannot pay Gemini API in AI Studio. Do not farm extra Cloud/Flow/WaveSpeed accounts.
- Elevation order: P1 captions/mix → P2 location/prop bible → P3 review gates → P4 I2V → P5 gateways → P6 factory/edit-agent.
- Drama beats and “one still, many shots” stay mandatory. `kind=news` and `kind=knowledge` are the editorial paths (narrator VO, per-beat stills). Do not fork HyperFrames. New features must not revert to one image per sentence.
