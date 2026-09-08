# Research — Story → AI short

omaishort **does not fork** a repo. It copies **contracts and stage order**, then implements its own engine.

Positioning:

| Family | Examples | Visuals | Fit for omaishort |
| --- | --- | --- | --- |
| Stock-short factory | MoneyPrinter, MoneyPrinterTurbo, ShortGPT | Pexels / keyword clips | Steal **ops** (TTS timestamps, BGM, LLM gateway). Do **not** steal stock footage as the picture. |
| Agentic studio | OpenMontage | Remotion / I2V / stock | Steal **gates, skills, render_runtime lock**. Do **not** vendor AGPL code. |
| Story / short-drama | ArcReel, AIDrama, FTL Studio, AI-Story-To-Movie | Character refs → stills → optional I2V | `kind=drama` — **default** (user facts in viral shape) or **custom** (prompt from scratch). |
| News / knowledge collage | MoneyPrinter ops + news 5-beat, not HyperFrames | Editorial stills + Ken Burns (ảnh ghép) | `kind=news` / `kind=knowledge`. Steal the **5-beat editorial arc** and per-scene VO. Do **not** fork HyperFrames, use Pexels, or put bible faces on editorial stills. |
| I2V model APIs | Seedance, Wan, LTX, Veo (Gemini HTTP), Kling | First-frame still → short 9:16 clip | Drama motion only. Map onto `VideoProvider`. Do **not** scrape Flow/Dreamina/ginigen UIs or fork “free Veo/Seedance” wrappers. |

Canonical product: [REQUIREMENTS.md](REQUIREMENTS.md) (numeric contract + routing). Elevation plan: [ROADMAP.md](ROADMAP.md).

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
- Treating MPT as Seedance/Wan/Kling. Core MPT still **retrieves stock clips**. Optional Volcengine Ark / WaveSpeed / OFox checkboxes in their README are paid T2V/I2V gateways, not the default pipeline ([issue #1183](https://github.com/harry0703/MoneyPrinterTurbo/issues/1183)). Steal the **submit-then-poll clip** idea; do not vendor their stock matcher as drama motion.

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

Video: free path is the public Hugging Face Space `Lightricks/ltx-video-distilled` (LTX I2V, ZeroGPU queue) plus `multimodalart/wan2-1-fast`, via `providers/video.py`. Anonymous ZeroGPU is **2 minutes/day** on a shared pool and often returns `error null`; a free HF account + `HF_TOKEN` is **5 minutes/day** of *your* quota ([Spaces as API](https://huggingface.co/docs/hub/spaces-api-endpoints)). Trial/paid HTTP: WaveSpeed Wan 2.2 Ultra Fast (`WAVESPEED_API_KEY`, default `wavespeed-ai/wan-2.2/i2v-480p-ultra-fast`, 5 or 8s). Paid pollen: `GET gen.pollinations.ai/video/{motion}?model=wan-fast&aspectRatio=9:16&image=<still URL>` requires `POLLINATIONS_KEY`. Registry also lists `wan-3.0`, `ltx-2`, `seedance` / `seedance-2.0`, **`veo`**, `google/gemini-omni-1.1-flash` (all pollen). `veo` duration is 4/6/8s; pass `image` as start (and optional end) frame. Identity from the start frame; motion prompt is camera + action only. Ken Burns if both fail. Full I2V menu (Seedance, Veo, Flow, open weights): §F.

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

## F. Drama I2V — Seedance and peers

ByteDance **Seedance** is a **closed** cinematic video model (Doubao / Volcengine Ark in CN; BytePlus Dreamina internationally). It is not an open-weight GitHub project. “Seedance free” repos and Spaces are **HTTP wrappers around a paid gateway**. Do not clone them. Drama already has the right contract: one approved still per scene → I2V clip → mux our TTS + ASS. News/knowledge stay Ken Burns collage.

### How Seedance actually makes a clip

Official I2V ([BytePlus video gen](https://docs.byteplus.com/en/docs/Byteplus_LAS/video_gen_enhanced), Ark `doubao-seedance-*`):

1. **First frame** = the still (jpeg/png/webp URL or upload). That frame *is* identity — do not T2V a new face.
2. Optional **last frame** (second image) to land on the next beat. `return_last_frame=true` gives a clean PNG to chain scene N → N+1. omaishort today is one still per scene, so last-frame chaining is later, not MVP drama.
3. **Motion prompt** = camera + action only (same as FTL / our `motion_prompt.py`). Do not paste VO or bible appearance text.
4. **`ratio=9:16`**, resolution 480p/720p (1080p on some SKUs). Crop the still to 1080×1920 first or the clip squash-jumps.
5. **Duration** integer seconds: Seedance 2.0 **4–15s**; Seedance 2.5 **4–30s**. Submit a job, poll until MP4. Native `generate_audio` exists — **turn it off**; we already mix Edge TTS.
6. Multimodal refs (2.0: up to 9 images; 2.5: more) can lock extra faces/sets. Our Character Bible passport URL is the first-frame still, not a second “style ref” that fights Kontext.

Paper: [Seedance 2.0](https://huggingface.co/papers/2604.14148) (Feb 2026). There are **no official open weights** and no official free Space.

### Official paid gates (HTTP adapter later)

| Gate | Model ids (examples) | Notes |
| --- | --- | --- |
| Volcengine Ark | `doubao-seedance-1-0-pro-*`, 2.x | CN; MoneyPrinterTurbo README optional checkbox |
| BytePlus / Dreamina | `dreamina-seedance-2-5-*` | International LAS submit/poll |
| Pollinations pollen | `seedance`, `seedance-2.0` | Same `VideoProvider` GET as Wan; needs `POLLINATIONS_KEY` |
| Replicate | `bytedance/seedance` | I2V from `image`, 4–15s, 720p, 9:16; `image[0]` start, `image[1]` end |

Map: new `SeedanceVideoProvider` (or `POLLINATIONS_VIDEO_MODEL=seedance`) behind `VideoProvider`. Planner never imports Ark/BytePlus/muapi SDKs.

### Google Veo and Flow (allowed HTTP vs skip scrape)

[Google Flow](https://labs.google/fx/tools/flow) is the **consumer** Veo UI (labs.google). Reports of ~50 free credits/day for logged-in users are **UI quota**, not an API. [Gemini Veo 3.1](https://ai.google.dev/gemini-api/docs/pricing) on the Developer API has **no free video tier** — paid per output second (`veo-3.1-generate-preview`, `veo-3.1-fast-generate-preview`, `veo-3.1-lite-generate-preview`). Vertex / Gemini Enterprise is the same model family with GCS + IAM.

How Veo I2V is made (matches drama if keyed):

1. First frame = still (`image=` on `client.models.generate_videos`, or Pollinations `image=`).
2. Optional last frame (`last_frame` / second image) — same later-chain idea as Seedance.
3. `aspect_ratio="9:16"`, duration **4, 6, or 8 seconds**, 24 fps (FFmpeg to 30fps on mux). Native audio exists — **off**; we mux Edge TTS.
4. Poll long-running operation, download MP4. Still should already be 9:16 or Google crops.

Official HTTP paths (same rule as Gemini **image** already in `providers/` — key in `.env`, no browser):

| Gate | Fit | Skip |
| --- | --- | --- |
| Gemini API `generate_videos` + `GEMINI_API_KEY` | Same HTTP pattern as our still adapter. Best Google path. | Do not import the planner into `google.genai`. |
| Vertex / Agent Platform | Enterprise IAM; GCS first-frame | Extra ops; not required for local-first. |
| Pollinations `model=veo` | Already in `PollinationsVideoProvider` if `POLLINATIONS_VIDEO_MODEL=veo` | Pollen, not free. |

**Do not automate Flow.** Product already forbids Gemini/Midjourney **UI** scrape. These GitHub tools drive Flow with Playwright + reCAPTCHA and a private `aisandbox-pa.googleapis.com` API — same class as ginigen Veo Spaces:

| Project | What it is | Take | Skip |
| --- | --- | --- | --- |
| [kittinan/gflow-cli](https://github.com/kittinan/gflow-cli) | Headed Chrome + Playwright → Flow | Confirms Flow I2V exists | Clone; steal session cookies |
| [eddie-fqh/flow-py](https://github.com/eddie-fqh/flow-py) | Playwright interceptor for Flow | Character-ref idea is already bible | Vendor |
| [farisdatosheikh/flowkit-veo-3.1](https://github.com/farisdatosheikh/flowkit-veo-3.1) | Chrome extension + agent skills | Scene still → video is our P4 | Extension bridge |
| [ginigen/VEO3-Free](https://huggingface.co/spaces/ginigen/VEO3-Free) | Gradio “free Veo” Space | — | Clone / scrape |
| [gxbvc/veo-cli](https://github.com/gxbvc/veo-cli) | Thin CLI over official `@google/genai` | Submit/poll + `--image` + `--aspect 9:16` | Vendor the CLI; copy the HTTP shape |

ChatGPT-web for **knowledge VO** stays the only in-process browser exception. Flow/Veo UI is not a second exception.

### Free-enough ranking (what actually fits a laptop drama job)

True $0 I2V that keeps bible faces (still → clip, 9:16):

| Rank | Path | Cost | Why it fits / why it fails |
| --- | --- | --- | --- |
| 1 | HF Spaces Wan Fast + LTX distilled (`HF_TOKEN`) | Free HF account, ~5 min/day ZeroGPU | **Already in engine.** First drama I2V. Quota is the limit, not quality. |
| 2 | Pollinations `wan-fast` / `ltx-2` | Pollen | Same `VideoProvider` GET. Use when HF queue dies. |
| 3 | Local LTX distilled / FramePack via Comfy | Electricity; VRAM **≥6–8GB** (not 4GB laptops) | Open weights ([Lightricks/LTX-Video](https://github.com/Lightricks/LTX-Video), FramePack). Next local adapter. |
| 4 | CogVideoX-2B (Apache) | Local GPU | Smaller than 14B Wan; still not a 4GB laptop. 5B I2V has a separate license. |
| 5 | Google Flow UI (manual) | ~50 credits/day if offered | Human can download a clip; **engine must not drive Flow**. |
| 6 | Gemini Veo / Pollinations `veo` / Seedance | Paid per second / pollen | Best motion. HTTP only. Five drama scenes ≈ five paid clips. |
| — | HunyuanVideo-I2V, Wan 2.2 14B | 40–80GB VRAM | Skip for this machine. Comfy later on a GPU box. |

There is **no** unofficial GitHub that gives unlimited Veo. “Veo free” = Flow credits in a browser, or a reseller wrapping Google’s paid API.

### Free video src catalog (do not clone)

“Free” here means **no per-clip invoice** (ZeroGPU quota, open weights, or Ken Burns). Sites that wrap the same Spaces and claim “unlimited no signup” still burn **your** HF IP quota — do not add them as providers.

#### Hosted $0 HTTP (still → MP4)

| Src | What | Engine today | Notes |
| --- | --- | --- | --- |
| [multimodalart/wan2-1-fast](https://huggingface.co/spaces/multimodalart/wan2-1-fast) | Wan 2.1 I2V, 4-step, ZeroGPU | **Yes** (`HF_I2V_WAN_URL`) | Default drama free path. Needs `HF_TOKEN`. |
| [Lightricks/ltx-video-distilled](https://huggingface.co/spaces/Lightricks/ltx-video-distilled) | LTX I2V distilled | **Yes** (`HF_I2V_SPACE_URL`) | Same quota pool as Wan. |
| [OpenKing/wan2-video-generation](https://huggingface.co/spaces/OpenKing/wan2-video-generation) | Wan 2.2 TI2V-5B, I2V, ~3s default | Later: point `HF_I2V_WAN_URL` if Gradio schema matches | Asks 180s GPU — often **PRO-only** per call cap. |
| [zai-org/CogVideoX-2B-Space](https://huggingface.co/spaces/THUDM/CogVideoX-2B-Space) | CogVideoX-2B T2V/I2V | Optional third Space | Apache-2.0 2B. Same ZeroGPU minutes. |
| Pollinations **image** turbo/flux | Stills, not video | **Yes** (`providers/pollinations.py`) | Anonymous stills OK. Video endpoints are pollen (`paid_only`). |
| omaishort Ken Burns | FFmpeg zoompan 1080×1920 | **Yes** (`engine/kenburns.py`) | Always-on $0 fallback. Honest `motion.json=kenburns`. |

Do **not** add: ginigen Veo/Seedance Spaces, promptspace.in / wan2-7.io (proxies of the same HF Spaces), Flow CLIs.

#### Open-weight GitHub (electricity + VRAM, no API bill)

Map behind `ComfyUIVideoProvider` later. Do not vendor the trees.

| Src | License | I2V / 9:16 | Laptop? |
| --- | --- | --- | --- |
| [Wan-Video/Wan2.1](https://github.com/Wan-Video/Wan2.1) / [Wan2.2](https://github.com/Wan-Video/Wan2.2) | Apache-2.0 | Yes (I2V / TI2V-5B) | 5B + offload maybe 8GB; 14B needs a GPU box |
| [Lightricks/LTX-Video](https://github.com/Lightricks/LTX-Video) | Apache on older distilled; LTX-2.x has a **revenue cap** | Yes | Distilled 2B is the local P4 candidate |
| [Lightricks/LTX-Desktop](https://github.com/Lightricks/LTX-Desktop) | check repo | Local editor on LTX-2.3 | NVIDIA desktop, not the API |
| [zai-org/CogVideo](https://github.com/zai-org/CogVideo) | **2B Apache**; 5B CogVideoX license (commercial register) | Yes | ~12–16GB for 2B |
| [genmoai/mochi](https://github.com/genmoai/mochi) | Apache-2.0 | T2V-first; I2V weaker | 20GB+ |
| [lllyasviel/FramePack](https://github.com/lllyasviel/FramePack) | Apache-2.0 | Next-frame I2V | Advertised ≥6GB |
| [deepbeepmeep/Wan2GP](https://github.com/deepbeepmeep/Wan2GP) | Community; free non-commercial | Wan/Hunyuan/LTX GUI | Quantized **~6GB** — closest “4GB laptop adjacent” |
| [PKU-YuanGroup/Helios](https://github.com/PKU-YuanGroup/Helios) | check | T2V/I2V/V2V | Offload ~6GB research |
| [SkyReels-A1 / SkyReels-V1](https://github.com/SkyworkAI/SkyReels-V1) | MIT (verify card) | Human motion | 24GB class |
| [stabilityai/stable-video-diffusion-img2vid-xt](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt) | Stability license | I2V from still | Hosted API **dead** (2025); weights only |
| [Tencent-Hunyuan/HunyuanVideo-I2V](https://github.com/Tencent-Hunyuan/HunyuanVideo-I2V) | Tencent community | I2V 720p | 40–80GB; skip this machine |
| [AIDC-AI/Pixelle-Video](https://github.com/AIDC-AI/Pixelle-Video) | Apache-2.0 | Topic → Comfy stills → Edge-TTS → mux | Steal **ops** (already our stages). Do not fork. Still not character-locked drama unless Comfy uses the bible. |

#### Free story-to-MP4 that is **not** I2V

These emit a short without a video model. Use for news/knowledge collage, not bible faces in motion.

| Src | Picture | Take | Skip |
| --- | --- | --- | --- |
| omaishort Ken Burns | Generated / Commons stills | Product fallback | Calling it I2V |
| MoneyPrinterTurbo | Pexels | TTS timestamps, BGM | Pexels as the picture |
| [still-motion](https://github.com/dheera/still-motion) (see §E) | One photo | Upscale + zoompan | New product surface |

### Trial and credit reality (checked 2026-09-08)

Legitimate **trial / grant** paths only. Do not farm extra Cloud/Flow accounts. Prices and quotas change; confirm on the vendor page before spending.

**Can the engine use it?** HTTP + key in `.env` = yes. Browser UI = no (except ChatGPT-web for knowledge VO).

| Offer | What it actually is | Engine? | Enough for one 5-beat drama? |
| --- | --- | --- | --- |
| HF ZeroGPU + `HF_TOKEN` | Official: unauthenticated **2 min/day**, free login **5 min/day**, PRO **40 min/day** ([Spaces ZeroGPU](https://huggingface.co/docs/hub/spaces-zerogpu)). Resets 24h after first GPU use. | **Yes** — already `providers/video.py` | Maybe. Quota is charged at the Space’s **requested** duration (often 60–120s), not wall clock. One Wan/LTX clip can eat 1–2 min → **2–5 clips/day**, not a reliable five-scene short. PRO (~$9/mo) is the cheapest “more clips” upgrade. |
| Pollinations **grant** pollen | Register, no card. Tiers refill: Spore ~0.01 pollen/hour, Seed 0.15/hour, Flower **10/day** ([POLLEN_FAQ](https://github.com/pollinations/pollinations/blob/master/enter.pollinations.ai/POLLEN_FAQ.md)). Grants expire; purchased pollen does not. | **Yes** if `POLLINATIONS_KEY` | Video models are **`paid_only`**. Live `GET gen.pollinations.ai/video/models` (this date): **`wan-fast` 0.01 pollen/s** (5s clip ≈ **0.05**); **`seedance-pro` 0.025/s**; **`veo` 0.08/s** video (+0.02/s audio). Five 5s Wan-fast clips ≈ **0.25 pollen** — Spore’s ~0.24/day is tight; Seed/Flower covers a short. Five 4s Veo clips ≈ **1.6 pollen** — needs Seed+ or a tiny pack, not Spore. **Checked 2026-09-08 on a live key:** `GET /account/balance` showed `balance: 1`, but Wan I2V returned **402** `Insufficient balance … available paid balance is 0.0000`. Grant/tier pollen ≠ paid video spend. Top-up at enter.pollinations.ai or use HF/WaveSpeed. |
| Google **Flow** 50 credits/day | Official help: non-subscribers get **50/day**, no rollover, refresh after first gen. Peak **02:00–05:00 UTC** may block video without a plan ([Manage Flow credits](https://support.google.com/flow/answer/16526234)). Lite **10**/clip, Fast **20**, Quality **100**. One request can emit **two** generations. | **No** — UI only | Lite: 5 clips = 50 → **one short/day** if each beat is a single generation. Fast: only **2 clips/day**. Quality: none. Download MP4 by hand; do not wire gflow-cli. |
| Gemini API Veo | Official pricing: Veo **Free tier = Not available**. Lite ~$0.05/s, Fast ~$0.10/s (720p, with audio; video-only cheaper on Vertex). | HTTP yes, **paid billing** | Five 4s Lite clips ≈ **$1**/short; Fast ≈ **$2**. No trial SKU. |
| GCP **$300** / 90 days | Official: new Cloud customers, card for ID. **Cannot** pay **Gemini API in AI Studio**. **Cannot** pay **partner MaaS** models. Trial accounts **cannot add GPUs**. ([Free Cloud features](https://docs.cloud.google.com/free/docs/free-cloud-features)) | Vertex HTTP maybe | Marketing blogs treat $300 as “free Veo”. Google does **not** list Veo as a covered SKU. Forum reports of **404 / not in catalog** on trial projects. Treat as **unproven**; check the Billing report after one clip. Never assume AI Studio `GEMINI_API_KEY` is covered. |
| Google AI Plus/Pro trial | Regional Google One trials exist; they add **monthly Flow credits**, not Gemini Veo API. | Flow UI only | Plus extra 200/mo; Pro extra 1,000/mo. Still not `VideoProvider`. |
| BytePlus ModelArk | VN is in the [availability list](https://docs.byteplus.com/en/docs/ModelArk/availability). **Free Tokens Only** pauses when quota ends (cannot re-enable if you turn it off). Seedance **1.0** family often has a free-token column; **2.0/2.5 often 0 free + prepaid pack** (~$30 floor in 2026 write-ups). | HTTP later | Maybe a few **1.0** clips. Do not plan drama on “unlimited Seedance trial”. |
| Replicate / fal signup credits | Occasional $1–$10 promo; not a durable product. | Optional later adapter | A smoke test, not a pipeline. |
| WaveSpeed signup **$1** | Pricing page: no card, $1 trial. [API-key blog](https://wavespeed.ai/blog/developer-friction/why-does-api-key-require-top-up-before-use/): keys may stay dead until a first top-up; some models block trial credit. | **Yes** — `WaveSpeedVideoProvider` | See pass 2–3. 480p Ultra Fast 5×5s ≈ **$0.25** *if* the key actually spends trial credit. |

**Rough pollen math for one short** (5 I2V clips, start-frame still, audio off where the model allows; live catalog 2026-09-08):

| Pollinations model | ~pollen / 5-clip short | Grant that covers it |
| --- | --- | --- |
| `wan-fast` (480p, 5s) | ~0.25 | Spore almost; Seed/Flower yes |
| `seedance-pro` (5s) | ~0.63 | Seed day or Flower |
| `veo` (4s, no extra audio) | ~1.6 | Seed several hours or Flower; not Spore |
| `seedance-2.0` (5s) | ~4.5 | Flower half-day or purchased pack |

**Operator recommendation for omaishort:** keep **HF_TOKEN** as the $0 drama path; register Pollinations and spend **grant pollen on `wan-fast`** when ZeroGPU dies; WaveSpeed **$1** Wan 480p Ultra Fast is the next HTTP smoke test (~one 5-beat short at $0.05/clip **if** the API key is live). Use Flow / Runway UI **by hand** only to judge cinema models. News/knowledge stay Ken Burns (no trial spend).

#### More trials (pass 2, same day)

Official pages, Sep 2026. One account per product. Do not farm.

| Offer | Official claim | Engine? | One 5-beat drama? |
| --- | --- | --- | --- |
| [WaveSpeed](https://wavespeed.ai/pricing) **$1** | “No credit card • Start with $1 free credits.” Some premium models blocked on trial. Live SKUs (API docs this date): Wan 2.2 **480p** Ultra Fast **$0.05 / 5s** ($0.01/s); **720p** Ultra Fast **$0.10 / 5s** on the model page (the marketing “$0.01/s” row is the 480p SKU). Seedance 2.0 Fast **$0.10/s**; Veo 3.1 Fast **$0.15/s**. Duration on Wan Ultra Fast I2V is **5 or 8s** only. | **Yes** — `WAVESPEED_API_KEY`, default `wavespeed-ai/wan-2.2/i2v-480p-ultra-fast`. Still needs a **public** start-frame URL. | 480p: 5×5s ≈ **$0.25** → **yes** on $1 *if* trial credit hits the API. 720p: 5×5s ≈ **$0.50**. Seedance Fast / Veo Fast still **no** for a full short on $1. |
| [Runway Free](https://www.runwayml.com/pricing) | **125 one-time** credits, $0/mo. Gen-4.5 = 60 cr / 5s; Seedance 2.0 Fast = 116 cr / 4s. | **No** (consumer studio; API is a paid plan) | Gen-4.5 ≈ **2 clips**. Seedance Fast ≈ **1 clip**. Not a full short. |
| [Modal Starter](https://modal.com/pricing) | **$30 / month** included compute, 10 GPU concurrency. Billing docs still want a payment method on file. | Later: run LTX/Wan in a container, not a vendor in the planner | Maybe several distilled I2V jobs if T4/L4. Not a clip API. |
| [Lightning AI Free](https://lightning.ai/pricing) | 5 credits at signup; **+25 if you add a card**; ~80 interruptible GPU hours advertised; 1 Studio, restart every **4h**; phone to anti-abuse. Credits expire 12 months. | Same as Modal — GPU box, not `generate_clip` | Enough to try FramePack/LTX distilled. Studio sleep kills long jobs. |
| [Replicate prepaid](https://replicate.com/docs/topics/billing/prepaid-credit) | Current docs: **buy credit first**. Older “run a bit free then add billing” is not a stated $N grant. Wan I2V on their public catalog is ~$0.09–$0.25/s. | Optional later adapter | No reliable $0 short. |
| [fal.ai](https://fal.ai/pricing) | Pay-per-second (Wan ~$0.05/s, Kling ~$0.07/s, Veo ~$0.4/s on their comparison table). No signup credit on the pricing page. | Optional later | No trial SKU found. |
| [DashScope 百炼](https://help.aliyun.com/zh/model-studio/new-free-quota) | New-user **90-day** inference quota (Beijing). Typical **1M tokens / model** for LLMs. Same legal person cannot re-claim. Enable **用完即停**. | Wan video often **has no** free bar in the console — confirm per model | Do not assume Wan I2V is included. LLM quota ≠ video seconds. |
| HF [Inference Providers](https://huggingface.co/docs/inference-providers/en/pricing) | Free users **$0.10 / month** routed credits (PRO $2). | Chat/embeddings mainly; video burns this instantly | **No** for I2V. Keep `HF_TOKEN` for **Spaces ZeroGPU**, not this pool. |
| Together / OpenRouter | Marketing “start free”; no video I2V grant found on Together pricing. | Skip for drama motion | — |

**Best extra trials for a $0 cinema-ish short (this pass):** WaveSpeed $1 → Wan 480p Ultra Fast HTTP (`WAVESPEED_API_KEY`; set `HF_I2V_ENABLED=0` so ZeroGPU is not tried first). Runway 125 cr / Flow 50/day → **look** at Seedance/Veo, then come back to omaishort stills. Modal $30 or Lightning credits → **self-host** LTX if you accept GPU ops. Replicate/fal/Gemini still need a card and cash for a 5-clip Veo short.

#### More trials (pass 3, same day)

Official pages, Sep 2026. One account per product. Do not farm extra WaveSpeed / Colab / Kaggle accounts.

| Offer | Official claim | Engine? | One 5-beat drama? |
| --- | --- | --- | --- |
| WaveSpeed **API vs UI** | [Why API keys require top-up](https://wavespeed.ai/blog/developer-friction/why-does-api-key-require-top-up-before-use/) (Jul 2026): keys created **before** a first top-up **may not work**. Trial credit can still run the **playground**. Premium models can refuse trial credit. | Adapter is live; a 401/empty task is a **billing** fail, not a code bug | Treat $1 as **maybe**. If the first `POST /v3/wavespeed-ai/wan-2.2/i2v-480p-ultra-fast` fails, the UI credit did not activate the key. Do not open a second account. |
| [Google Colab](https://colab.research.google.com/) free | T4 when available; idle disconnect; no SLA. | **No** — not `VideoProvider`. Self-host Wan/LTX/FramePack in a notebook, download MP4, then Ken Burns mux is a manual path. | Maybe a few distilled clips if the session lasts. Not a job-stage adapter. |
| [Kaggle](https://www.kaggle.com/docs/efficient-gpu-usage) GPU | Advertised **~30 GPU hours / week** on the free tier (P100/T4; quotas change). | Same as Colab — notebook GPU, not HTTP | Same: try FramePack/LTX locally-in-cloud. Do not scrape Kaggle as a clip factory. |
| Kie / PiAPI / “confirm dashboard” aggregators | Reseller dashboards in front of Kling/Veo/Seedance. Free SKUs, if any, are account-specific. | Skip unless you already have a key and an HTTP spec | Do not clone their SDKs. Confirm **your** dashboard; do not assume a public $0 I2V grant. |

**Do not:** farm extra Cloud/Flow/WaveSpeed/Colab accounts, scrape Flow/Dreamina, or treat ginigen Spaces as free Seedance.

**Pollinations Veo duration:** catalog allows **4 / 6 / 8** only. `providers/video.py` now clamps `POLLINATIONS_VIDEO_MODEL=veo` (a 5s scene becomes 6s, then FFmpeg conform). `wan-fast` stays 5s.

### “Free Seedance” on GitHub / Hugging Face — skip

| Project | What it actually is | Take | Skip |
| --- | --- | --- | --- |
| [ginigen/Seedance-Free](https://huggingface.co/spaces/ginigen/Seedance-Free) | Gradio UI that calls **Seedance v1 via WaveSpeed keys**; 480p; watermark | Confirms I2V = image URL + prompt + aspect | Clone the Space; scrape Gradio; depend on “free” third-party keys |
| [micky-M12/Seedance-2.5-API](https://github.com/micky-M12/Seedance-2.5-API) | Python client for **muapi.ai** | Submit/poll JSON shape | Vendor the wrapper; put a reseller key in `.env.example` as if it were ByteDance |
| [Anil-matcha/Seedance-2-API](https://github.com/Anil-matcha/Seedance-2-API) | Same pattern for 2.0 / 2.5 / Mini | Same | Same |

A Space named Seedance is not Seedance weights. Same rule as Gemini/Midjourney: **no UI scrape**.

### Other I2V families (drama motion menu)

| Family | How you get a clip | Length / 9:16 | Fit for omaishort |
| --- | --- | --- | --- |
| **Wan 2.1 Fast** (Alibaba) | HF Space `multimodalart/wan2-1-fast`; Pollinations `wan-fast` | ~5s | **Already in** `providers/video.py`. First free-ish path with `HF_TOKEN`. |
| **Wan 2.2 Ultra Fast** | WaveSpeed HTTP `wavespeed-ai/wan-2.2/i2v-480p-ultra-fast` (720p SKU is 2× price) | **5 or 8s** | **Already in** as `WaveSpeedVideoProvider`. Needs public still URL + `WAVESPEED_API_KEY`. |
| **LTX** (Lightricks) | Space `Lightricks/ltx-video-distilled`; pollen `ltx-2` | short distilled | **Already in** the same chain. |
| **Seedance** (ByteDance) | Ark / BytePlus / pollen `seedance*` | 4–15s (2.0), 4–30s (2.5) | Next **paid** drama adapter. Best official first/last-frame contract. |
| **Veo 3.1** (Google) | Gemini `generate_videos` (paid); Pollinations `veo`; Flow UI credits | 4/6/8s, 9:16, 24fps | HTTP + still = drama. **No** Flow/Playwright. Mute native audio. |
| **Gemini Omni Flash** | Pollinations `google/gemini-omni-1.1-flash` | 3–10s | Pollen; always-on audio — strip or don’t use. |
| **Kling** (Kuaishou) | Paid API | cinematic | Skip as a required planner vendor. Optional later gateway. |
| **Hailuo / MiniMax** | Paid API; pollen `minimax-h3` | ~5s | Same — optional, not hardcoded. |
| **Runway Gen-3 / Luma / Grok video** | Paid / pollen `grok-video-pro` | | Skip lock-in. |
| **CogVideoX-2B** | Local Apache weights | ~5s | Comfy later if GPU exists. |
| **HunyuanVideo-I2V** | Local; ~60GB+ VRAM | ~5s 720p | GPU box only. |
| **FramePack** | Local next-frame I2V | advertised ≥6GB VRAM | Existing P4 note. |
| **Wan 2.2 14B / Hunyuan 14B** | Replicate / local | longer, slower | Paid or GPU box; keep Fast in the free chain. |

Story-pipeline peers already mapped in §D/§E (FTL, Story Forge, Wind Comic, DramaDirector) all do **still → I2V**, not T2V per sentence. That is the drama motion product.

### Map onto `kind=drama`

Take:

- One I2V clip **per scene**, start frame = approved `still_id` (bible faces already in the photo).
- Motion prompt from beat lenses (hook zoom_in → … → ending zoom_out); no VO text.
- Race providers: HF Wan → LTX → WaveSpeed Wan HTTP (if keyed) → Pollinations (Wan, Seedance, or Veo if keyed) → Gemini Veo HTTP if `GEMINI_API_KEY` billed → Comfy → Ken Burns. Failed I2V stays a labeled animatic (`render/motion.json`).
- Seedance last-frame / Veo `last_frame` only after scene stills are stable (P3 review).
- Native model audio **off**; duration clamp to the model’s integer window (Veo 4/6/8, Seedance 4–15, Wan ~5), then FFmpeg stretch/trim to probed TTS like today.

Skip:

- T2V without a still (new face, bible broken).
- One clip per sentence or per shot.
- News/knowledge I2V (ảnh ghép stays Ken Burns).
- Hardcoding Kling/Veo/Seedance in the planner.
- Cloning ginigen / muapi / gflow-cli / flow-py / flowkit / MoneyPrinterTurbo Ark helpers into this tree.

Used in: `providers/video.py` (Wan / LTX / WaveSpeed Wan / Pollinations Wan). Seedance or Veo HTTP = same chain via `POLLINATIONS_VIDEO_MODEL` or a later Gemini `generate_videos` adapter, not a new product surface.

---

## G. What omaishort already does differently

1. Ken Burns over stills — not one generate per sentence.
2. Character Bible is source of truth **for drama**. News/knowledge have a narrator-only bible and empty `scene.characters`.
3. Drama beats are mandatory (hook / conflict / rising / twist / ending). News/knowledge reuse the same keys with different meanings.
4. Provider chain so Windows without GPU still emits MP4.
5. Three `VideoKind`s (`drama` | `news` | `knowledge`) on one FFmpeg pipeline. Legacy `brief` aliases to `news`. Not three products.

## H. HyperFrames / AI-auto-generate-video (news / knowledge)

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

## I. License cheat-sheet

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
| ginigen/Seedance-Free, muapi Seedance wrappers | check repo | **No.** HTTP shape only; do not vendor |
| gflow-cli / flow-py / flowkit / ginigen VEO3-Free | check repo | **No.** Flow/Veo UI scrape |
| Lightricks/LTX-Video | Apache-2.0 (check LTX-2.x community cap) | Comfy adapter later; do not vendor the desktop studio |
| zai-org/CogVideo (2B) | Apache-2.0 | Ideas; 5B I2V has a separate license |
| Wan-Video/Wan2.1–2.2, genmoai/mochi | Apache-2.0 | Weights OK; do not vendor inference apps |
| AIDC-AI/Pixelle-Video | Apache-2.0 | Ops only; do not fork |
| deepbeepmeep/Wan2GP | community | Local low-VRAM later; check non-commercial clause |
