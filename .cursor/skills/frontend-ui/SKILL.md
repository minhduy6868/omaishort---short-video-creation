---
name: frontend-ui
description: Builds and restyles the omaishort Vite React studio (paste story, poll job stages, storyboard stills, MP4 download). Use when editing apps/web, UI layout, fonts, CSS, or the create-job flow.
---

# Frontend UI

Read `apps/web/src/types.ts`, `api.ts`, `App.tsx`, `App.css`, `index.css`.

Checklist:

- Keep the one-page studio. Split files rather than a mega-component.
- Poll job JSON; map `artifacts[still_id]` through `dataFileUrl`.
- Stages match the API: analyze, plan, refs, stills, tts, captions, render.
- Visual: charcoal panel, terracotta `--accent`, Fraunces heading. No emoji in the UI.
- After edits: `npx tsc --noEmit` in `apps/web`. Exercise paste → create job → poll if the API is up.
