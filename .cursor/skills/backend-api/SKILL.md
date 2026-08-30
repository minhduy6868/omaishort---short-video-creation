---
name: backend-api
description: Changes the omaishort FastAPI job API, SQLite persistence, and provider pipeline. Use when editing apps/api, routes, db, pipeline stages, or LLM/image/TTS providers.
---

# Backend API

Read `apps/api/omaishort/main.py`, `db.py`, `pipeline.py`, `providers/`.

- Routes: `POST /jobs`, `GET /jobs/{id}`, artifacts, download, `/health`.
- Serialize rows with `db.public_job()`. Do not leak raw `*_json` keys to the client.
- Provider order is documented in `docs/REQUIREMENTS.md`. Add adapters; do not hardcode vendors in the planner.
- BackgroundTasks run `pipeline.run_job`. Persist artifacts incrementally so the UI can show stills before the MP4 exists.
- After edits: `pytest -q`.
