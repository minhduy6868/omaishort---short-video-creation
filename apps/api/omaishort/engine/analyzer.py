from __future__ import annotations

from omaishort.engine.fallback import fallback_analyze
from omaishort.providers.llm import complete_json, load_prompt
from omaishort_schema.models import CharacterBible, StoryInput, StoryStructure


async def analyze_story(story: StoryInput) -> tuple[CharacterBible, StoryStructure, str]:
    system = load_prompt("analyzer.txt")
    user = (
        f"mode={story.mode.value}\n"
        f"genre={story.genre.value}\n"
        f"language={story.language}\n"
        f"target_seconds={story.target_seconds}\n\n"
        f"STORY:\n{story.text}"
    )
    raw = await complete_json(system, user)
    if raw:
        try:
            bible = CharacterBible.model_validate(raw.get("bible") or raw.get("characters") or raw)
            structure = StoryStructure.model_validate(raw["structure"] if "structure" in raw else raw)
            return bible, structure, "llm"
        except Exception:
            pass
    bible, structure = fallback_analyze(story)
    return bible, structure, "fallback"
