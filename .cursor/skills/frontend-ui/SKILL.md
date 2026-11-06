---
name: frontend-ui
description: Builds and restyles the omaishort Vite React studio (paste story, poll job stages, storyboard stills, MP4 download). Use when editing apps/web, UI layout, fonts, CSS, or the create-job flow.
---

# Frontend UI

Read `apps/web/src/types.ts`, `api.ts`, `App.tsx`, `App.css`, `index.css`.

Checklist:

- Pages, not one scroll: gate (`/login`, `/register`), rail (`/work`, `/drama`, `/news`, `/knowledge`, `/account`, `/admin` for `operator`), job screen (`/watch/{id}`). Split files rather than a mega-component.
- Poll job JSON; map `artifacts[still_id]` through `dataFileUrl`. `fetch` uses `credentials: "include"` (auth cookies).
- Logged-out routes are only the gate. Attachments bind onto `POST /jobs` from the compose page for that kind. ChatGPT sign-in stays on Knowledge.
- Stages match the API: analyze, plan, refs, stills, tts, captions, render.
- Visual: two site themes. `brutal` (Khối thô, default): cream page, white blocks, 2–3px black borders, hard offset shadows (`--hard*`), yellow/orange, Space Grotesk, uppercase display. `soft` (Gối mềm): one grey surface, paired light/dark shadows (`--soft-out*`, `--soft-in`), blue accent, Manrope. Tokens in `index.css`; blocks/insets/chips/buttons get their depth in `styles/skins.css`. The admin (`operator`) picks the theme on Account (`SiteThemePicker`, `PUT /site/theme`); `?theme=` previews without saving. CSS reads tokens, never a raw hex, except the always-dark video frame. No emoji in the UI.
- New component with its own border: add its class to the block, inset or chip list in `skins.css` for both themes.
- After edits: `npx tsc --noEmit` in `apps/web`. Exercise paste → create job → poll if the API is up.
