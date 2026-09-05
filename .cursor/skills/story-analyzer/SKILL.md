---
name: story-analyzer
description: Analyzes a pasted script or story idea into a Character Bible and five-beat drama structure (hook, conflict, rising, twist, ending). Use when changing Story Analyzer prompts, bible output, or the analyze job stage.
---

# Story Analyzer

Read `prompts/analyzer.txt` (drama) or `prompts/analyzer_brief.txt` (news/knowledge) and `apps/api/omaishort/engine/analyzer.py`.

Output JSON with `bible` and `structure` only.

Drama: genre is confession/family/cheating/revenge/twist — not explainer.

News/knowledge: `kind=news` or `kind=knowledge` (legacy `brief` → news). Bible is narrator-only. Knowledge **topics** call `write_knowledge_script` first so ChatGPT writes VO into `script.json` before stills. ChatGPT web is in-process Playwright (`providers/chatgpt_web.py`, `python -m omaishort --chatgpt-login` once). Wiki is fallback; `script.json.note` says why.

If the LLM is missing or JSON fails Pydantic, use `engine/fallback.py`. Do not invent a different beat model.

Character ids are stable slugs (`wife`, `husband`, `narrator`). Appearance and clothing must be lockable across scenes.
