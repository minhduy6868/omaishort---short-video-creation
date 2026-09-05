# Requirements — omaishort

Product: **Story Video Engine** for three vertical kinds on one pipeline: **drama** (confession / family / cheating / revenge / twist), **news** (human story / event), and **knowledge** (one claim / explainer). Legacy `kind=brief` aliases to **news**. Not a TikTok clone. Not a fork of one repo.

Canonical research: [docs/RESEARCH.md](RESEARCH.md). Elevation: [docs/ROADMAP.md](ROADMAP.md). Schema: `packages/schema/omaishort_schema/models.py`.

## 1. Problem

Creators paste a story, idea, or news brief and need a **1080×1920 short** with:

- **Drama:** stable characters across scenes (same face, same clothes); dialogue VO when the paste is `Name: line`
- News / knowledge: off-camera narrator, **summarized story** that fills `target_seconds` (drama default 60s, news/knowledge default 90s, never above 10 minutes). News covers the full article through the ending. Knowledge stays on one claim, turns a **topic request** (“thuyết minh về lạm phát…”) into an explainer, or a **GitHub README** into a short how-to. Spoken VO uses real sentence stops.
- Shared beats (hook → conflict → rising → twist → ending). News maps those to headline → obstacle → how it unfolded → turn → where it stands now. Knowledge maps them to claim → proof → how it works → misconception → what to remember.
- Motion from **few stills**, not one image per sentence
- Voiceover + captions synced to real audio length

## 2. Users

| User | Job |
| --- | --- |
| Creator | Paste script/idea, wait, download MP4 |
| Operator | Run local API, plug LLM/ComfyUI/ElevenLabs keys |
| Agent (Cursor) | Change pipeline without breaking bible/scene/render contracts |

## 3. In scope (MVP)

- Input: `kind` (`drama` | `news` | `knowledge`; `brief` → news), `idea` or `script`, genre, language (`en`/`vi`), target 15–180s (drama default 60, editorial default 90)
- Story Analyzer → Character Bible + five-beat structure (drama: faces; news/knowledge: narrator-only bible)
- Scene Planner → drama 8–15 scenes / news+knowledge **exactly 5 scenes** (one still per beat), **one still per scene**, 1–3 Ken Burns shots sharing that still
- Image chain: Pollinations Flux/Kontext (free, no key) → OpenAI images (if keyed) → placeholder. Character passports and scene stills must be photographs when Pollinations is on; location/prop passports may stay geometric to save quota.
- TTS: ElevenLabs if keyed, else edge-tts, else silence
- Rescale scene/shot times to probed audio duration
- Captions: edge-tts WordBoundary timestamps, else faster-whisper, else even word-split → ASS (`SubtitleStyle`)
- Compose: I2V (Pollinations Wan if `POLLINATIONS_KEY`) else FFmpeg Ken Burns; 1080×1920 @ 30fps; optional BGM (first file in `assets/music/`, ducked under VO); optional logo overlay (`mix.logo_enabled`, file in `assets/logo/` or `mix.logo_path`)
- Location/prop bible: passport stills + reused `location_id`
- Persist job in SQLite; write `bible.json`, `storyboard.json`, `timeline.json`, MP4
- Web: one page — paste, poll stages, storyboard stills, download
- Remotion app only **reads** `timeline.json` (`elements`, `text`, `audio`). Render is FFmpeg.

## 4. Out of scope (later)

See [ROADMAP.md](ROADMAP.md) for order. Do not pull these in during an unrelated change.

- P3: review gates + locked `render_runtime`
- P4: I2V on approved stills — **shipped with Ken Burns fallback** (Pollinations Wan needs `POLLINATIONS_KEY`; no key → zoompan)
- P5: named LLM/TTS/image gateway
- P6: Part 1..N factory + edit-agent
- Never default: Pexels stock as the picture; HyperFrames HTML templates; AGPL vendoring; auto social upload

## 5. Functional requirements

- **FR1** Analyzer always emits hook, conflict, rising_action, twist, ending. Drama never uses fun-fact arcs. News/knowledge reuse those five keys (news: headline / obstacle / unfold / turn / outcome; knowledge: claim / proof / context / misconception / remember).
- **FR2** Drama: Scene.characters are bible ids only. Prompts compose appearance + clothing + scene fields. News/knowledge: Scene.characters is empty; stills prefer publisher photos from `source_url` on early beats, then **per-beat** Wikimedia/Openverse terms (MoneyPrinter-style, not Pexels), then generated editorial. `use_face_ref=false`.
- **FR3** Do not create one still per sentence. Merge same location+emotion. Do not recycle one mugshot across later beats that talk about something else.
- **FR4** `use_face_ref=false` when back-turned, distant, or face hidden.
- **FR5** After TTS, rescale all `duration_sec` / shot windows so they sum to audio length.
- **FR6** Job stages: `analyze → plan → refs → stills → tts → captions → render`.
- **FR7** API: `POST /jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/artifacts`, `GET /jobs/{id}/download`, `GET /health`.
- **FR8** Dry-run without cloud keys still produces an MP4. If Pollinations is on and the free image API is down, stills fail instead of mixing stick-figure frames. Set `POLLINATIONS_ENABLED=0` for geometric stills.

## 6. Non-functional

- Local-first on Windows. FFmpeg from PATH or `imageio-ffmpeg`.
- Providers behind protocols; planner must not import a vendor SDK.
- Secrets only in `.env` (gitignored). CI never needs API keys.
- Output always 1080×1920, 30fps.

## 7. Acceptance (MVP)

- `pytest -q` green
- `npx tsc --noEmit` in `apps/web` green
- `python -m omaishort samples/confession-60s.md` writes MP4 1080×1920 with audio
- `python -m omaishort samples/knowledge-topic.md --kind knowledge --language vi` writes an explainer short (`script.json` from ChatGPT HTTP/CLI first, wiki fallback, no on-camera bible faces)
- `python -m omaishort samples/brief-60s.md --kind knowledge --language vi` writes a knowledge short with no on-camera bible faces
- News URL jobs (`--kind news`) cover the article ending; stills match each beat (article photos then per-beat CC search, not Pexels)
- Storyboard: unique `still_id` per scene; shots share that id; shot count > scene count

## 8. Stack

Python 3.11, FastAPI, Pydantic v2, SQLite, Vite + React, FFmpeg, optional ComfyUI / OpenAI-compatible LLM / ElevenLabs / faster-whisper.
