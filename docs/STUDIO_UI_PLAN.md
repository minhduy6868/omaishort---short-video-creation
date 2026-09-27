# Studio UI plan

Goal: make `apps/web` feel closer to a focused desktop production studio while keeping the omaishort product contract: one 1080x1920 short, one still per scene, drama uses Character Bible/I2V when available, news and knowledge stay editorial collages with Ken Burns.

## Reference notes from `D:\tool\videoai`

The useful pattern in `videoai` is not its browser/provider automation. The useful pattern is the workspace shape:

- A persistent shell with a compact sidebar, dense pages, status pills, progress rows, asset cards, and right-side inspectors.
- A job-first workflow: create a job, show progress, expose logs/details, retry failed work, and preview the final media from the same screen.
- A video pipeline UI that treats narration/audio as the master clock and lets visuals adapt to it.
- A news flow that separates source text, real/manual images, narration, collage thumbnail, render, and export.
- A desktop-style asset library where generated/imported media is visible, selectable, and inspectable.

The useful video-creation lessons are already compatible with omaishort:

- `videoai` News Studio analyzes text, searches/selects photos, matches them to narration, builds a collage thumbnail, generates voice, and renders stills with FFmpeg zoom/crossfade. Omaishort already has the stronger product version: five editorial beats, per-beat still assignment, captions, BGM, and `render/motion.json`.
- `videoai` drama workflows follow still -> image-grounded video prompt -> one video clip. Omaishort should keep its stronger scene contract: one still per scene, one I2V clip per scene when available, otherwise honest Ken Burns.
- `videoai` job recovery/log UI is worth copying at the UX level. Omaishort can first show stage/progress/errors from existing `/jobs`; full logs/retry need backend work later.

Do not bring over:

- Workflow graph authoring.
- Browser Hub, Grok/Flow UI automation, account allocator, or provider session controls.
- Arbitrary output presets as the main path. Omaishort output remains 1080x1920.
- Local desktop export-folder selection. The current web studio downloads from authenticated `/files` and `/jobs/{id}/download`.

## Additional UI references

These are local source reads. They add UI patterns only; they do not change the video pipeline contract.

| Source | Useful UI pattern | Map to omaishort | Do not copy |
| --- | --- | --- | --- |
| `D:\tool\claude-code\web` | Full-height workbench, resizable/collapsible sidebar, slim header, command palette, grouped quick actions. | Later collapsible rail, compact topbar/provider strip, optional quick-create/search palette. | Next/Tailwind/Radix stack and chat-specific layout. |
| `D:\tool\multi_profile` | Header stats, selectable left list, running-state lockout, timestamped activity log, modal create/edit. | Work counters, selectable job/scene list, disabled create controls while submitting, future job activity panel. | Browser-profile automation, emoji-heavy labels, cyan palette. |
| `D:\tool\lonton\Auto-Post-Group-Facebook\app\ui.py` | Operator dashboard with sidebar nav, topbar account selector, tabs, stat cards, progress/log area, stop controls. | Account/provider surface, job status behavior, future worker controls when API supports cancel/stop. | Facebook automation flows, cookies, account data, and platform-specific copy. |
| `D:\tool\btmob` | Mobile-first form shell, status chips, progress stepper, sticky bottom action bar, offline/online chip. | Better mobile compose ergonomics, sticky submit/cancel bar, provider/API status chip. | Decorative landing/orb styling and unrelated survey copy. |
| `D:\tool\bsc\mixer\apps\web` | Numbered sequential action cards with concise hint text. | Simple create-job validation steps in compose panels. | Crypto/wallet flow, palette, and financial wording. |
| `D:\tool\srt-whiteboard-animation\assets\preview.html` | Stage/canvas plus right inspector, ordered module list, timeline scrubber, dirty/save state. | Future still review/contact-sheet inspector and timeline scrubber. | Whiteboard region editor as the default compose UI. |
| `D:\tool\youtube-shorts-pipeline` | Stage state with status, timestamps, and artifact paths. | Future artifact log/timeline panel. | Pexels/stock defaults or niche system as the product surface. |

Updated decisions from these references:

- Keep the first pass page-based and guided. Use modals only for upload/picker/detail flows.
- Add compact counters to the Work page: total, running, done, failed.
- Treat an activity/log panel as a future enhancement until the API exposes structured job events.
- Add a sticky mobile action bar for Compose so long forms remain easy to submit on phones.
- Add a future command palette only after the core pages are stable.
- Add a future review/timeline inspector when the product has review gates or editable scene metadata.
- Disable submit/destructive controls while a create request is pending. Keep navigation available. Add Stop/Cancel only after the backend has a real cancel endpoint.

## Current omaishort UI baseline

`apps/web` already has the correct route shape:

- Gate: `/login`, `/register`.
- Main rail: `/work`, `/drama`, `/news`, `/knowledge`, `/account`.
- Job screen: `/watch/{id}`.

Available API/UI data today:

- `/jobs` and `/jobs/{id}` expose status, stage, progress, structure, storyboard, artifacts, input, and errors.
- `/attachments` supports uploaded face/location/prop/editorial/logo/script files.
- `/voices` feeds language-specific voice options.
- `/providers` can show image/video/TTS/ChatGPT readiness and `drama_motion`.
- `artifacts.motion_mode` exists and must be shown honestly as `kenburns`, `i2v`, or `mixed`.

Known gaps for later:

- No retry endpoint.
- No job log endpoint.
- No approve/regenerate endpoint for P3 review gates yet.
- No attachment delete helper in `apps/web/src/api.ts`, though the API route exists.

## Information architecture

Keep the current route model, but make each page feel like a studio workspace.

### Shell

Use a fixed left rail with:

- Brand and compact route links.
- Primary creation links: Drama, News, Knowledge.
- Secondary links: Work, Account.
- User/session block at the bottom.

Keep the current charcoal/terracotta/Fraunces identity. Do not copy `videoai`'s blue gradient desktop palette. Use full-height layouts, table density, and inspectors from the desktop app pattern.

### Work page

Replace the simple vertical job list with a production queue table:

- Columns: title/id, kind, stage, status, progress, updated/created, motion, action.
- Status pill and progress bar per row.
- Filters: all, running, done, failed.
- Quick actions: open watch page, download when done.
- Empty state with direct create links for Drama, News, Knowledge.

This can be done with existing `listJobs()` data.

### Compose pages

Keep separate `/drama`, `/news`, and `/knowledge` pages, but redesign the body as a two- or three-column workspace:

- Left: source editor.
  - Drama: story/script field, mode, shape, genre.
  - News: URL + article/notes.
  - Knowledge: topic/GitHub URL + notes.
- Middle: production settings.
  - Language, voice, duration, BGM, logo.
  - ChatGPT login state for Knowledge.
  - Provider readiness summary from `/providers`.
- Right: reference/attachment picker.
  - Drama: face, location, prop, logo, script.
  - News/knowledge: editorial, logo, script.
  - Show selected files as compact chips/cards with bind labels.

The current single form already has the data. The first UI pass should mostly restructure markup and CSS, not change the create-job contract.

### Watch page

Turn `/watch/{id}` into the main production monitor:

- Left inspector: stage rail, status, error, input summary, provider/motion summary.
- Center: 9:16 phone preview. Show poster/still while running and video when done.
- Bottom or right: scene contact sheet.
  - Thumbnail, beat/emotion, duration, `still_id`, motion pair, short VO/dialogue excerpt.
  - Mark I2V scenes only if `artifacts` or future motion metadata proves it.
- Beats panel: hook/conflict/rising/twist/ending, with editorial labels implied by kind.
- Artifact actions: download MP4, open stills through `dataFileUrl()`.

This is where the UI should borrow the desktop "detail modal/inspector" feeling from `videoai`, but as a first-class route.

### Account page

Make Account the operator surface:

- Current user and role.
- Provider readiness cards from `/providers`.
- ChatGPT login action for Knowledge.
- Attachment library table/cards.
- Later: attachment delete, storage totals, and auth/session controls.

## Component plan

Create small local components under `apps/web/src/components/`:

- `PageHeader`: kicker/title/lede/actions.
- `TopBar` / `ProviderHealthBar`: compact account/provider/API status area.
- `StatusPill`: status and stage coloring.
- `ProgressBar`: compact progress display.
- `StageRail`: analyze -> plan -> refs -> stills -> tts -> captions -> render.
- `PhonePreview`: fixed 9:16 preview surface for poster/video/empty states.
- `SceneStrip`: reusable scene thumbnail list/contact sheet.
- `AttachmentPicker`: upload + library select + selected chips.
- `ProviderStrip`: provider readiness summary.
- `SegmentedControl`: shape/filter/status choices.
- `JobTable`: work queue table.
- `CounterCard`: Work dashboard counts.
- `MobileActionBar`: sticky mobile submit/action row.
- `InspectorPanel`: future scene/job detail panel.
- `ActivityLog`: future structured job event list.

Keep dependencies unchanged for the first pass. If icon buttons become important, add `lucide-react` in a separate UI-polish change with a clear reason.

## Implementation phases

### Phase 1: shared studio shell and primitives

Files:

- `apps/web/src/index.css`
- `apps/web/src/App.css`
- `apps/web/src/Shell.tsx`
- new `apps/web/src/components/*`

Tasks:

- Add reusable page/header/status/progress/phone-preview styles.
- Keep route behavior untouched.
- Add compact topbar space for backend/provider state.
- Improve responsive rules so the rail collapses on mobile and content does not overflow.

Validation: `npx tsc --noEmit` in `apps/web`.

### Phase 2: Work dashboard

Files:

- `apps/web/src/pages/WorkPage.tsx`
- `apps/web/src/types.ts` if typing `created_at`, `updated_at`, `input`, or artifact details.

Tasks:

- Convert job list to table/cards.
- Add status filters and progress display.
- Add direct navigation to create routes and watch route.
- Show motion mode when artifacts are present.
- Add compact counters for total, running, done, and failed jobs.
- Show a “last updated” state from polling or manual refresh.

Validation: TypeScript plus manual check with empty job list and non-empty job list.

### Phase 3: Compose workspace

Files:

- `apps/web/src/pages/ComposePage.tsx`
- `apps/web/src/api.ts` only if extracting attachment helpers.

Tasks:

- Split the existing form into Source, Production, and References panels.
- Keep `createJob()` payload unchanged.
- Improve attachment selection UX with selected cards/chips.
- Show provider/ChatGPT readiness where it affects the current kind.
- Use a sticky mobile action bar for submit/reset when the form stacks vertically.

Validation: create payload must still include `attachments`, `mix`, `voice_id`, `script_brief`, `source_url`, and `drama_shape`.

### Phase 4: Watch page

Files:

- `apps/web/src/pages/JobPage.tsx`
- shared components from Phase 1.

Tasks:

- Replace the plain stage list with `StageRail`.
- Add phone preview, contact sheet, beat panel, and artifact actions.
- Show `motion_mode` without calling Ken Burns I2V.
- Keep polling `/jobs/{id}` every 1.5 seconds until `done` or `failed`.
- Leave space for future scene inspector, timeline scrubber, and activity log.

Validation: running job, failed job, done job with MP4, and job with stills but no MP4.

### Phase 5: Account/provider/library polish

Files:

- `apps/web/src/pages/AccountPage.tsx`
- `apps/web/src/api.ts` if adding delete attachment.

Tasks:

- Provider readiness cards.
- Attachment library with file kind, filename, size, created date.
- ChatGPT login action with clear ready/opening state.

Validation: logged-in account, API down/fallback provider state, attachment list.

### Phase 6: future review gates

Only after backend P3 endpoints exist:

- Add contact sheet approval state after `stills`.
- Add approve/regenerate actions.
- Add one-still regeneration UI by `still_id` or character id.

Do not fake this with frontend-only buttons before the API supports it.

## Acceptance checklist

- UI routes stay off `/jobs`; `/jobs` remains API-only.
- All fetches use cookies/credentials through existing API helpers.
- Stages match `analyze`, `plan`, `refs`, `stills`, `tts`, `captions`, `render`.
- News/knowledge UI says editorial stills/Ken Burns, not I2V.
- Drama UI shows shape/mode clearly and keeps attachments for face/location/prop.
- Text fits in tables, buttons, cards, and mobile layouts.
- No one-image-per-sentence language appears in the UI.
- After every `apps/web` change: run `npx tsc --noEmit`.
