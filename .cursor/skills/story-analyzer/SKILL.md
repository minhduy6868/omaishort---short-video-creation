---
name: story-analyzer
description: Analyzes a pasted script or story idea into a Character Bible and five-beat drama structure (hook, conflict, rising, twist, ending). Use when changing Story Analyzer prompts, bible output, or the analyze job stage.
---

# Story Analyzer

Read `prompts/analyzer.txt` and `apps/api/omaishort/engine/analyzer.py`.

Output JSON with `bible` and `structure` only. Genre is confession/family/cheating/revenge/twist — not explainer.

If the LLM is missing or JSON fails Pydantic, use `engine/fallback.py`. Do not invent a different beat model.

Character ids are stable slugs (`wife`, `husband`, `narrator`). Appearance and clothing must be lockable across scenes.
