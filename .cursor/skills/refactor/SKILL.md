---
name: refactor
description: Refactors omaishort without changing the storyboard/timeline contract. Use when cleaning structure, splitting files, removing duplication, or the user asks to dọn dẹp / refactor.
---

# Refactor

Rules:

- Behavior stays the same. Schema fields and job stages do not rename unless a migration is explicit.
- Prefer extracting a module (`api.ts`, `db.public_job`) over extra abstraction layers.
- Touch the minimum files. Do not “upgrade” Remotion, Redis, or I2V while refactoring.
- Delete dead helpers (unused imports, unused timeline utilities).
- Prove it: `pytest -q` and `npx tsc --noEmit` in `apps/web`.
