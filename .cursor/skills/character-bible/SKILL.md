---
name: character-bible
description: Maintains omaishort Character Bible, passport reference stills, and face-ref injection into scene prompts. Use when editing character identity, reference images, or consistency across scenes.
---

# Character Bible

Source of truth: `Character` in `packages/schema/omaishort_schema/models.py`.

Flow from AI-Story-To-Movie:

1. Analyzer writes the bible.
2. Image provider makes one passport still per character at `data/jobs/<id>/refs/<id>.png` (photographic; Pollinations sidecar `{id}.pollinations.json` stores the public GET URL).
3. Locations (`refs/locations/<id>.png`) and props (`refs/props/<id>.png`) may stay geometric placeholders so quota goes to faces.
4. Scene planner lists **on-camera** character ids only, plus `location_id` and `prop_ids`.
5. `engine/image_prompts.py` concatenates appearance + clothing + **On camera ONLY: {ids}**.
6. `compact_image_prompt` keeps cast + wardrobe; do not dump the full template into the Pollinations URL.
7. Scene gens with `use_face_ref` call Pollinations Kontext using the passport URL (not a local file). News/knowledge jobs skip character passports.
8. Set `use_face_ref=false` when the character is back-turned, distant, or face-hidden. Inserts: no full-body people.

Never describe a new face inside a scene prompt if that person already has a bible row.
Never invent a new kitchen if `location_id=kitchen` already exists.
Do not drop a geometric placeholder into a scene still when Pollinations is enabled — fail the still and retry.
