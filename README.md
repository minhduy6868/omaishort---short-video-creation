# omaishort

Story Video Engine for vertical short-drama. Paste a script, get a **1080×1920** MP4.

- Requirements: [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md)
- Research (sources we learned from, not forked): [docs/RESEARCH.md](docs/RESEARCH.md)
- Agent entry: [AGENTS.md](AGENTS.md)

## Pipeline

```
StoryInput → Analyzer → CharacterBible + StoryStructure
         → ScenePlanner → 1 still / scene, 1–3 Ken Burns shots
         → Image (ComfyUI → OpenAI images → placeholder)
         → TTS (ElevenLabs → edge-tts → silence)
         → rescale to audio
         → captions → FFmpeg → 1080×1920
```

## Layout

| Path | Role |
| --- | --- |
| `apps/api` | FastAPI + engine |
| `apps/web` | Vite studio UI |
| `apps/remotion` | timeline scaffold (FFmpeg is the renderer) |
| `packages/schema` | Pydantic + JSON Schema |
| `prompts/` | analyzer / planner / image templates |
| `tests/` | pytest |
| `.cursor/skills` | agent skills |
| `.cursor/rules` | always-on + glob rules |

## Setup (Windows)

```bat
cd apps\api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

```bat
cd apps\web
npm install
npm run dev
```

```bat
cd apps\api
python run.py
```

Optional: copy `.env.example` to `.env`. UI: `http://127.0.0.1:5173` (proxy → API `:8765`).

## Commands

```bat
pytest -q
cd apps\web && npx tsc --noEmit
cd apps\api && python -m omaishort ..\..\samples\confession-60s.md
```

## API

`POST /jobs` · `GET /jobs/{id}` · `GET /jobs/{id}/artifacts` · `GET /jobs/{id}/download` · `GET /health`

Stages: `analyze | plan | refs | stills | tts | captions | render`
