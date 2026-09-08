# Research — Story → AI short

omaishort **does not fork** a repo. It copies **contracts and stage order**, then implements its own engine.

Positioning:

| Family | Examples | Visuals | Fit for omaishort |
| --- | --- | --- | --- |
| Stock-short factory | MoneyPrinter, MoneyPrinterTurbo, ShortGPT | Pexels / keyword clips | Steal **ops** (TTS timestamps, BGM, LLM gateway). Do **not** steal stock footage as the picture. |
| Agentic studio | OpenMontage | Remotion / I2V / stock | Steal **gates, skills, render_runtime lock**. Do **not** vendor AGPL code. |
| Story / short-drama | ArcReel, AIDrama, FTL Studio, AI-Story-To-Movie | Character refs → stills → optional I2V | `kind=drama`. |
| News / knowledge brief | [AI-auto-generate-video](https://github.com/huytranvan2010/AI-auto-generate-video) (HyperFrames templates) | HTML templates → Chromium MP4 | Steal the **5-beat news arc** and per-scene VO. Do **not** fork HyperFrames or use Pexels. |

Canonical product: [REQUIREMENTS.md](REQUIREMENTS.md). Elevation plan: [ROADMAP.md](ROADMAP.md).

---

## A. Original four (already in the engine)

### 1. AIStoryVideoGenerator
https://github.com/yenloned/AIStoryVideoGenerator

Take: emotion in image prompts, TTS, **sync scene duration to real audio**, FFmpeg assemble.

Skip: one image per text chunk; in-process SD as the only image path.

Used in: `providers/tts.py`, `engine/rescale.py`, `engine/compose.py`.

### 2. story2video-style scene contract

Story → scenes with setting, character, action, mood, dialogue, duration, camera, lighting, motion, consistency notes, SQLite.

That JSON **is** `Scene` + `Shot` in `packages/schema`.

### 3. AI-Story-To-Movie
https://github.com/SDSmirnov/AI-Story-To-Movie

Take: Character Bible → passport stills → inject into later prompts. Skip face-ref when back-turned.

Skip: lock-in to Imagen/Veo.

Used in: `engine/analyzer.py`, `engine/image_prompts.py`, refs stage.

### 4. Remotion prompt-to-video
https://github.com/remotion-dev/template-prompt-to-video

Take: `timeline.json` tracks `elements` / `text` / `audio`.

Skip: explainer/fun-fact topics; OpenAI+ElevenLabs-only CLI.

MVP renders with **FFmpeg**. Remotion is a later player.

---

## B. MoneyPrinter family (ops, not drama)

### MoneyPrinterTurbo
https://github.com/harry0703/MoneyPrinterTurbo — MIT, Python 3.11, 9:16 + 16:9

Take:

- **LLM gateway**: OpenAI-compatible HTTP, or in-process ChatGPT web (`providers/chatgpt_web.py`: Playwright, profile in `data/chatgpt-web`, `--chatgpt-login` once then headless, one `/c/` thread per day). Knowledge topics write `script.json` before stills. Do not clone ChatGPT-Web2API / chatgpt-pro-web. Wiki is last resort. Gemini/Ideogram/Midjourney **web UIs** are the same login idea but too brittle for stills — use HTTP adapters (`GEMINI_API_KEY`, Pollinations, OpenAI images).
- **Subtitle dual path**: `edge` = timestamps from TTS (fast, no GPU) vs `whisper` = transcribe. We should prefer **edge-tts word boundaries** before even-split.
- **Subtitle cosmetics**: font, color, outline, position (MoneyPrinter WebUI). Map onto our ASS styles.
- **BGM**: pick track, volume slider; mix under VO.
- **Batch N takes**, keep the best (we can generate 2 stills per scene and pick).
- **Preset import/export** of generation settings (not secrets in git).
- Layered API: controller / service / model.

Skip:

Skip: Pexels / Pixabay as the **default picture**. Free **generated** stills (Pollinations Flux, no key) are OK; stock footage is not character-locked drama.
- Auto TikTok/Instagram/YouTube upload (Upload-Post). Optional later, not core.
- Topic→keyword explainer scripts as the story model.

### MoneyPrinter / MoneyPrinterV2
https://github.com/FujiwaraChoki/MoneyPrinterV2

Take: niche → script → images → TTS → Whisper SRT → MoviePy 1080×1920; `stt_provider` switch.

Skip: Selenium YouTube upload, cron spam posting.

---

## C. OpenMontage (agent studio)

https://github.com/calesthio/OpenMontage — **AGPL-3.0**. Patterns only. Do not copy tools/skills files into this repo.

Take:

- **Three knowledge layers**: tool registry → project skills → vendor skills. omaishort already has `.cursor/skills` + `.cursor/rules`.
- **Review gates**: pause after stills; human/agent approves before expensive I2V or final encode. “Backlot” contact sheet.
- **`render_runtime` locked at plan time** (`ffmpeg` | `remotion`). No silent swap at compose.
- When no video model: stills + Ken Burns / Remotion motion (same as our MVP).
- Word-level captions; BGM ducking under speech.
- Selector: cloud API **or** local, same tool name.

Skip:

- Replacing FastAPI with “the coding agent is the orchestrator”.
- 12 generic pipelines (explainer, talking-head, documentary). We stay **short-drama**.
- Vendoring Remotion/HyperFrames trees.

Related: [AliHamzaAzam/montage-ai](https://github.com/AliHamzaAzam/montage-ai), [google/project-montage](https://github.com/google/project-montage) — edit-agent (“darken scene 5”).

---

## D. Story / short-drama (closest peers)

### ArcReel
https://arc-reel.com — novel → agents → **reference sheets first** (characters + locations + props/“clues”) → storyboard → I2V → FFmpeg.

Take: **Location bible + prop bible**, not only characters. Block storyboard until refs exist.

### AIDrama Studio
https://github.com/Averdim/ai-short-drama

Take: Character Workshop; 2–4 candidates per shot, pick one; bilingual UI; one gateway key for many models.

### FTL Studio
https://github.com/uby174/ftl-studio

Take: canon character still **and** canon set still; composite shot-1 from canon; **vision judge before I2V spend**; motion prompt describes only movement/camera/audio.

### Story Forge
https://github.com/nicedreamzapp/story-forge

Take: Flux still → Wan/LTX I2V; Piper VO; original music; **VLM QC** (identity drift, extra limbs); Whisper verifies each scripted line is audible; sidechain ducking.

Skip: Mac-only Metal stack as a requirement.

### hariharsecure/identity-locked-film-pipeline / AnimeLoom

Take later: per-character LoRA + IP-Adapter face-lock when ComfyUI is real, not placeholder.

### Pollinations (free image API)

https://github.com/pollinations/pollinations — used by MoneyPrinter (LLM gateway) and storyboard apps (GaurAk495/ai-story-board).

Take: `GET image.pollinations.ai/prompt/{text}?model=turbo&seed=` (Flux is nicer but 500s more on the anonymous tier). Compact the bible appearance lock into the URL; reuse `seed` from character id. After a passport succeeds, save that public Pollinations URL and generate scene stills with `model=kontext&image=<passport URL>` (localhost files cannot be fetched).

Video: free path is the public Hugging Face Space `Lightricks/ltx-video-distilled` (LTX I2V, ZeroGPU queue) plus `multimodalart/wan2-1-fast`, via `providers/video.py`. Anonymous ZeroGPU is **2 minutes/day** on a shared pool and often returns `error null`; a free HF account + `HF_TOKEN` is **5 minutes/day** of *your* quota ([Spaces as API](https://huggingface.co/docs/hub/spaces-api-endpoints)). Paid path: `GET gen.pollinations.ai/video/{motion}?model=wan-fast&aspectRatio=9:16&image=<still URL>` requires `POLLINATIONS_KEY` and pollen. Registry also lists `wan-3.0`, `ltx-2`, `seedance` (all pollen). Identity from the start frame; motion prompt is camera + action only. Ken Burns if both fail.

Skip: Pexels; treating seed+prompt as real identity lock; burning quota on location passports before faces.

Used in: `providers/pollinations.py`, `providers/video.py`.

---

## E. Wave 2 (2026) — new peers, not in the original four

Do not clone these trees. Map patterns onto existing protocols.

### Wind Comic
https://github.com/ChrisChen667788/wind-comic — MIT, TypeScript studio, ~550★. Closest **short-drama** open product after FTL / AIDrama.

Take:

- **Vision-audit retry**: regenerate a still/clip scoring below a threshold (maps to P3, not a new stage).
- **I2V race**: `VIDEO_ENGINE_ORDER=…`, first good clip wins (our `VideoProvider` chain). Failed I2V → labeled animatic, never a still pretending to be video.
- **LLM via 3 env vars** (OpenAI-compatible / Ollama). Matches P5; we already point `OPENAI_BASE_URL` at Ollama.
- **Strip dialogue from image/video prompts**; burn real ASS after (CJK garbled-glyph problem). We already keep motion prompts camera+action only.
- **Emotion → camera**: hook→push-in, reveal→zoom, even Ken Burns follows the beat (`engine/motion_prompt.py`).
- **Segment retake**: re-encode only a broken time range; `-c copy` the rest (P6 edit-agent).

Skip:

- One I2V clip **per shot** as the default (we stay one still / scene).
- Kling / Veo / MiniMax as required vendors; lip-sync / viseme / Yjs collab; Next.js rewrite of the studio.

### FramePack (local I2V)
https://github.com/lllyasviel/FramePack — Apache-2.0. Next-frame I2V; advertised **6GB VRAM**, 30GB+ weights. Wrapper: [kijai/ComfyUI-FramePackWrapper](https://github.com/kijai/ComfyUI-FramePackWrapper).

Take: when ComfyUI is actually live, add a FramePack adapter behind `VideoProvider` (smallest local I2V that is not Wan-14B).

Skip: cloning FramePack into this repo; promising it on RTX 3050 Ti **4GB** (reports of OOM even on 8GB). Need ≥6GB + `--low-vram` before this is an operator path.

### DramaDirector
https://github.com/iLearn-Lab/DramaDirector — MIT research. First-frame still → I2V; planner borrows depth/pose from a real-drama shot gallery.

Take: keep **still then I2V** (already our P4). Schema-constrained storyboard JSON (already `Scene`/`Shot`).

Skip: training SFT/GRPO, depth/pose retrieval, DramaBoard dataset as a runtime dependency.

### SEAM (paper)
https://arxiv.org/abs/2608.22725 — Shot Entity-Attribute Memory. Training-free prompt rewrite: remember props, blocking, clothing across shots/episodes.

Take later (P6): a continuity JSON carried between scenes (who holds the phone, which kitchen wall). Inject into still prompts, not a new image model.

Skip: until there is a small MIT implementation; do not vendor CreativeFitting production code.

### still-motion
https://github.com/tomastimelock/still-motion — Ken Burns that **upscales before `zoompan`** so 1080p30 does not judder.

Take: if I2V stays down, apply the same upscale-then-zoompan trick in `engine/kenburns.py`.

Skip: making Ken Burns the product goal; HTML overlay titles.

### Hugging Face Spaces API (not a product repo)

https://huggingface.co/docs/hub/spaces-api-endpoints

Take: send `Authorization: Bearer $HF_TOKEN`; prefer `gradio_client` + `handle_file()` over ad-hoc SSE. Quota table: anonymous 2 min/day, free login 5 min, PRO 40 min. That is why unauthenticated LTX/Wan Spaces return `error null`.

Skip: adding `gradio_client` until a keyed smoke test actually returns an MP4.

---

## F. What omaishort already does differently

1. Ken Burns over stills — not one generate per sentence.
2. Character Bible is source of truth **for drama**. News/knowledge have a narrator-only bible and empty `scene.characters`.
3. Drama beats are mandatory (hook / conflict / rising / twist / ending). News/knowledge reuse the same keys with different meanings.
4. Provider chain so Windows without GPU still emits MP4.
5. Three `VideoKind`s (`drama` | `news` | `knowledge`) on one FFmpeg pipeline. Legacy `brief` aliases to `news`. Not three products.

## G. HyperFrames / AI-auto-generate-video (news / knowledge)

https://github.com/huytranvan2010/AI-auto-generate-video

Input: article URL or txt → `script.json`. Scenes: first `hook`, body, last `outro`. Each scene is `voiceText` + a HyperFrames `templateId` + text inputs (kicker / headline / stat). Chromium renders HTML templates to MP4. TTS per scene, concat, mux 9:16.

Steal:

- **Typed frames, not one still per sentence.** Five beats only: hook (empty desk) → claim/stat graphic → context establishing → implication/product hero → empty outro.
- Per-scene VO fitted to audio (we already rescale after TTS).
- Editorial stills. Compact image prompt must lead with **uninhabited / zero people** — “no soap-opera” alone is too weak for turbo.

Skip:

- HyperFrames, Chromium HTML templates, OmniVoice lock-in, emoji kickers, burned-in headline text.
- One template per sentence.
- Cloning that tree into omaishort. Pexels / stock B-roll as the picture.

Used in: `StoryInput.kind=news|knowledge` (legacy `brief`→news), `_plan_brief` + `BRIEF_TREATMENTS`, `prompts/scene_still_brief.txt`, `engine/brief_media.py` (`visual_terms_for_beat` → Wikimedia/Openverse, article photos on early beats). Never cycle one mugshot across five beats. Never Pexels.

### Other news/knowledge repos (map, do not vendor)

| Repo | What they do | Take | Skip |
| --- | --- | --- | --- |
| [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) | Topic → LLM script → **per-scene search terms** → Pexels clips → TTS | Steal `match_materials_to_script`: one English term set **per beat**, in script order | Pexels as the picture; auto social upload; one clip per sentence |
| [MPVSAP](https://github.com/thienphucnt/MPVSAP) | Wikipedia ingest + proper-noun Wikimedia + Pexels B-roll | Place/occupation Commons search when the article gallery is thin | Pexels; one clip per sentence |
| [hueanmy/ai-shorts-generator](https://github.com/hueanmy/ai-shorts-generator) | URL → HTML storyboard → Playwright MP4 | News vs promo share one renderer | HTML/Playwright templates |
| [bonskpy/video-explainer-system](https://github.com/bonskpy/video-explainer-system) | Topic → HTML deck → Kokoro + ffmpeg | Local TTS + captions | HTML animation engine |
| [yudduy/chatgpt-pro-web](https://github.com/yudduy/chatgpt-pro-web) | Playwright CLI for chatgpt.com quota | Persistent profile + headed login + composer/stop-button wait | Do not vendor the Node CLI; omaishort has `providers/chatgpt_web.py` |

## H. License cheat-sheet

| Repo | License | Copy code? |
| --- | --- | --- |
| MoneyPrinterTurbo | MIT | Ideas + small snippets OK |
| OpenMontage | AGPL-3.0 | **No.** Patterns and stage names only |
| Remotion template | Remotion license | Use as reference for `timeline.json` |
| FTL Studio / Story Forge / AIDrama | check repo | Prefer reimplementation |
| Wind Comic | MIT | Ideas + contracts OK; do not fork the Next.js studio |
| FramePack | Apache-2.0 | Comfy adapter later; do not vendor the desktop app |
| DramaDirector | MIT | Planner/I2V order only; no training stack |
| still-motion | check repo | zoompan-upscale idea only |
| AI-auto-generate-video / HyperFrames | check repo | **No.** News-arc mapping only |
