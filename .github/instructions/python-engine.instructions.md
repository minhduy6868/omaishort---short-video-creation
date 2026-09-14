---
applyTo: "apps/api/**/*.py,packages/schema/**/*.py,tests/**/*.py"
---

Read `.cursor/rules/python-backend.mdc` and `.cursor/rules/pipeline.mdc`.

If you touch jobs, providers, or `pipeline.py`, also read `.cursor/skills/backend-api/SKILL.md`. Analyzer → `story-analyzer`. Planner / shots → `scene-planner`. Compose / captions → `render-short`. Bible / faces → `character-bible`.

After edits: `pytest -q` from the repo root.
