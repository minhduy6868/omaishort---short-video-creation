# omaishort (GitHub Copilot)

Follow the repo-root [AGENTS.md](../AGENTS.md). That file is the shared brief for every coding agent.

Before pipeline work, read:

- `.cursor/rules/pipeline.mdc`
- `.cursor/rules/quality.mdc`
- `.cursor/rules/working.mdc`
- `.cursor/rules/github.mdc`

When the task matches a skill name (`backend-api`, `story-analyzer`, `character-bible`, `scene-planner`, `render-short`, `frontend-ui`, `source-research`, `refactor`, `test`), read `.cursor/skills/<name>/SKILL.md` and follow it.

Do not fork MoneyPrinter, OpenMontage, or HyperFrames into this tree. Do not use Pexels. Do not turn `kind=news` / `kind=knowledge` into drama. Do not commit `data/`, `.env`, or generated MP4.

After engine or schema edits: `pytest -q`. After `apps/web`: `npx tsc --noEmit`.
