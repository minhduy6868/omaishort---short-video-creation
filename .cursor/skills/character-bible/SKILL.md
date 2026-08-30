---
name: character-bible
description: Maintains omaishort Character Bible, passport reference stills, and face-ref injection into scene prompts. Use when editing character identity, reference images, or consistency across scenes.
---

# Character Bible

Source of truth: `Character` in `packages/schema/omaishort_schema/models.py`.

Flow from AI-Story-To-Movie:

1. Analyzer writes the bible.
2. Image provider makes one passport still per character at `data/jobs/<id>/refs/<id>.png`.
3. Scene planner lists `character_ids` only.
4. `engine/image_prompts.py` concatenates appearance + clothing + scene action.
5. Set `use_face_ref=false` when the character is back-turned, distant, or face-hidden.

Never describe a new face inside a scene prompt if that person already has a bible row.
