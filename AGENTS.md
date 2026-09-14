# omaishort agent notes

Read [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md), [docs/RESEARCH.md](docs/RESEARCH.md), and [docs/ROADMAP.md](docs/ROADMAP.md) before changing the pipeline.

This file is the **shared** brief for every coding agent (Cursor, Claude Code, Codex, Gemini CLI, GitHub Copilot, Grok, DeepSeek, Cline/Roo, Windsurf). Tool-specific loaders are thin adapters. Do not copy product rules into a second long file.

## Source of truth

| Kind | Canonical path | Do not fork into |
| --- | --- | --- |
| Always-on rules | [`.cursor/rules/`](.cursor/rules/) | New `RULE.md` trees per vendor |
| Task skills | [`.cursor/skills/*/SKILL.md`](.cursor/skills/) | Rewritten skill bodies |
| Product contract | [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | Comments in planner code |

After you edit a Cursor skill, run `python scripts/sync_agent_skills.py` so Codex (`.agents/skills`) and Claude Code (`.claude/skills`) pointers stay aligned.

## Rules (read these)

- Pipeline: [`.cursor/rules/pipeline.mdc`](.cursor/rules/pipeline.mdc)
- Quality: [`.cursor/rules/quality.mdc`](.cursor/rules/quality.mdc)
- How we work: [`.cursor/rules/working.mdc`](.cursor/rules/working.mdc)
- GitHub / PRs: [`.cursor/rules/github.mdc`](.cursor/rules/github.mdc)
- CI: [`.cursor/rules/cicd.mdc`](.cursor/rules/cicd.mdc)
- API/engine files: [`.cursor/rules/python-backend.mdc`](.cursor/rules/python-backend.mdc)
- Studio UI: [`.cursor/rules/frontend.mdc`](.cursor/rules/frontend.mdc)

## Skills (read the matching one before you edit)

When the task matches, **read the Cursor `SKILL.md` now** and follow it. Pointers under `.agents/skills` and `.claude/skills` only exist so other tools can discover the same names.

| Skill | Use when |
| --- | --- |
| `backend-api` | FastAPI jobs, SQLite, providers, `pipeline.py` |
| `story-analyzer` | Analyze stage, bible, five-beat drama |
| `character-bible` | Passport stills, face-ref, identity |
| `scene-planner` | Storyboard, shots, beat lenses |
| `render-short` | Compose, Ken Burns, captions, `timeline.json` |
| `frontend-ui` | Vite studio |
| `source-research` | Learn from MoneyPrinter / OpenMontage / HyperFrames — **do not clone** |
| `refactor` | Dọn dẹp without changing the contract |
| `test` | pytest, `tsc`, dry-run |

`kind=news` / `kind=knowledge` are editorial **ảnh ghép**. Legacy `kind=brief` aliases to news. They do not vendor HyperFrames.

## Non-negotiables

- Do not fork a random story-to-video repo into this tree. Extend `apps/api/omaishort`.
- Do not emit one image per sentence. One still per scene; 1–3 shots share `still_id`.
- Do not turn news/knowledge into drama. Do not use Pexels. Do not scrape Gemini/Midjourney UIs.
- Do not commit `data/`, `.env`, MP4, or venv.
- After engine/schema: `pytest -q`. After `apps/web`: `npx tsc --noEmit`.
- API venv: `apps/api/.venv/Scripts/python.exe` on Windows (`python -m omaishort`).

## Which file each tool loads

| Tool | Entry file | Skills |
| --- | --- | --- |
| Cursor | `.cursor/rules/*.mdc` + this file | `.cursor/skills/` |
| Claude Code | [`CLAUDE.md`](CLAUDE.md) (`@AGENTS.md` + rules) | `.claude/skills/` → Cursor skill |
| Codex | this `AGENTS.md` | `.agents/skills/` → Cursor skill |
| Gemini CLI | [`GEMINI.md`](GEMINI.md) + [`.gemini/settings.json`](.gemini/settings.json) | same Cursor skills |
| GitHub Copilot | [`.github/copilot-instructions.md`](.github/copilot-instructions.md) | path notes in `.github/instructions/` |
| Grok | [`GROK.md`](GROK.md) | Cursor skills |
| DeepSeek | [`DEEPSEEK.md`](DEEPSEEK.md) | Cursor skills |
| Cline / Roo | [`.clinerules`](.clinerules) | Cursor skills |
| Windsurf | [`.windsurf/rules/omaishort.md`](.windsurf/rules/omaishort.md) | Cursor skills |
