---
name: test
description: Adds or runs omaishort tests (pytest engine/schema, TypeScript check, sample dry-run). Use when writing tests, fixing CI, or verifying planner/rescale/API behavior.
---

# Test

- Unit: `tests/test_engine.py` (fallback stills/shots, rescale, captions), `tests/test_schema.py`.
- Run from repo root: `pytest -q` (see `pytest.ini` pythonpath).
- Web: `cd apps/web && npx tsc --noEmit`.
- Render smoke (local, has network/TTS): `cd apps/api && python -m omaishort ../../samples/confession-60s.md`.
- CI is `.github/workflows/ci.yml` — no API keys, no ffmpeg dry-run.
- New engine behavior needs a test that does not call ComfyUI or ElevenLabs.
