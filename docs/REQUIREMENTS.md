# Requirements — omaishort

Product: **Story Video Engine** for vertical short-drama (confession / family / cheating / revenge / twist). Not a TikTok clone. Not a fork of one repo.

Canonical research: [docs/RESEARCH.md](RESEARCH.md). Elevation: [docs/ROADMAP.md](ROADMAP.md). Schema: `packages/schema/omaishort_schema/models.py`.

## 1. Problem

Creators paste a story or idea and need a **1080×1920 short** with:

- Stable characters across scenes (same face, same clothes)
- Drama beats (hook → conflict → rising → twist → ending)
- Motion from **few stills**, not one image per sentence
- Voiceover + captions synced to real audio length. If the paste is **character dialogue** (`Name: line`), TTS is those spoken lines, not a narrator recap.

## 2. Users

| User | Job |
| --- | --- |
| Creator | Paste script/idea, wait, download MP4 |
| Operator | Run local API, plug LLM/ComfyUI/ElevenLabs keys |
| Agent (Cursor) | Change pipeline without breaking bible/scene/render contracts |

## 3. In scope (MVP)

- Input: `idea` or `script`, genre, language (`en`/`vi`), target 15–180s (default 60)
- Story Analyzer → Character Bible + five-beat structure
- Scene Planner → 8–15 scenes, **one still per scene**, 1–3 Ken Burns shots sharing that still
- Image chain: Pollinations Flux/Kontext (free, no key) → OpenAI images (if keyed) → placeholder. Character passports and scene stills must be photographs when Pollinations is on; location/prop passports may stay geometric to save quota.
- TTS: ElevenLabs if keyed, else edge-tts, else silence
- Rescale scene/shot times to probed audio duration
- Captions: edge-tts WordBoundary timestamps, else faster-whisper, else even word-split → ASS (`SubtitleStyle`)
- Compose: I2V (Pollinations Wan if `POLLINATIONS_KEY`) else FFmpeg Ken Burns; 1080×1920 @ 30fps; optional BGM (first file in `assets/music/`, ducked under VO)
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
- Never default: Pexels stock as the picture; AGPL vendoring; auto social upload

## 5. Functional requirements

- **FR1** Analyzer always emits hook, conflict, rising_action, twist, ending. Never fun-fact/explainer arcs.
- **FR2** Scene.characters are bible ids only. Prompts compose appearance + clothing + scene fields.
- **FR3** Do not create one still per sentence. Merge same location+emotion.
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
- Storyboard: unique `still_id` per scene; shots share that id; shot count > scene count

## 8. Stack

Python 3.11, FastAPI, Pydantic v2, SQLite, Vite + React, FFmpeg, optional ComfyUI / OpenAI-compatible LLM / ElevenLabs / faster-whisper.
