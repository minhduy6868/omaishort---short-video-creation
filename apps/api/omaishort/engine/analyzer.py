from __future__ import annotations

import re

from omaishort.engine.brief_media import knowledge_spoken_from_notes, knowledge_spoken_from_wiki
from omaishort.engine.fallback import fallback_analyze, stamp_identity_locks
from omaishort.providers.llm import complete_json, complete_json_result, load_prompt
from omaishort.providers.tts import ensure_spoken_stops
from omaishort_schema.models import CharacterBible, StoryInput, StoryStructure, is_editorial

_SCRIPT_KEYS = ("hook", "conflict", "rising_action", "twist", "ending")
_FAKE_VIDEO_FACTORY = re.compile(
    r"stop stitching a script|stock clips|muxes a vertical short|character bible|"
    r"topic in,? (?:one )?finished short|biến một chủ đề đơn giản thành cả một video ngắn|"
    r"matches footage, adds a voice|stock stills are the default",
    re.I,
)
_VIDEO_FACTORY_SOURCE = re.compile(
    r"short video generator|writes a script, matches footage|MoneyPrinter|"
    r"topic in.*short out|vertical short from a topic",
    re.I,
)


def _beats_from_script(raw: dict | None) -> list[str] | None:
    if not isinstance(raw, dict):
        return None
    src = raw.get("structure") if isinstance(raw.get("structure"), dict) else raw
    beats = [re.sub(r"\s+", " ", str(src.get(key) or "")).strip() for key in _SCRIPT_KEYS]
    if any(len(beat.split()) < 8 for beat in beats):
        return None
    if re.search(r"thuyết minh về|[\u2E80-\u9FFF]|là một cơ chế", " ".join(beats), flags=re.I):
        return None
    return beats


def clip_script_brief(text: str | None, limit: int = 2000) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())[:limit].strip()


def knowledge_script_user(
    title: str,
    extract: str,
    language: str,
    target_seconds: float,
    topic: str = "",
    script_brief: str = "",
) -> str:
    parts = [
        f"title={title}",
        f"topic={topic or title}",
        f"language={language}",
        f"target_seconds={int(target_seconds or 90)}",
    ]
    brief = clip_script_brief(script_brief)
    if brief:
        parts.append(f"USER_BRIEF={brief}")
    parts.append("")
    parts.append(f"SOURCE:\n{(extract or '')[:8000]}")
    return "\n".join(parts)


async def write_knowledge_script(
    title: str,
    extract: str,
    language: str,
    target_seconds: float,
    topic: str = "",
    script_brief: str = "",
) -> tuple[str, str, str]:
    """ChatGPT writes the VO first. Wikipedia / README notes are fallback."""
    system = load_prompt("knowledge_script.txt")
    user = knowledge_script_user(
        title, extract, language, target_seconds, topic=topic, script_brief=script_brief
    )
    raw, src, err = await complete_json_result(system, user)
    beats = _beats_from_script(raw)
    joined = "\n\n".join(beats) if beats else ""
    if beats and _FAKE_VIDEO_FACTORY.search(joined) and not _VIDEO_FACTORY_SOURCE.search(extract or ""):
        beats = None
    if beats:
        return ensure_spoken_stops(joined), src or "llm", ""
    if extract and len(extract.split()) >= 40 and "github.com" in f"{topic} {title}":
        return ensure_spoken_stops(knowledge_spoken_from_notes(extract, name=title)), "github", err
    return ensure_spoken_stops(knowledge_spoken_from_wiki(title, extract, language)), "wiki", err


async def analyze_story(story: StoryInput) -> tuple[CharacterBible, StoryStructure, str]:
    prompt_name = "analyzer_brief.txt" if is_editorial(story.kind) else "analyzer.txt"
    system = load_prompt(prompt_name)
    brief = clip_script_brief(story.script_brief)
    extra = f"USER_BRIEF={brief}\n" if brief else ""
    user = (
        f"kind={story.kind.value}\n"
        f"mode={story.mode.value}\n"
        f"genre={story.genre.value}\n"
        f"language={story.language}\n"
        f"target_seconds={story.target_seconds}\n"
        f"{extra}\n"
        f"STORY:\n{story.text}"
    )
    raw = await complete_json(system, user)
    if raw:
        try:
            bible = CharacterBible.model_validate(raw.get("bible") or raw.get("characters") or raw)
            structure = StoryStructure.model_validate(raw["structure"] if "structure" in raw else raw)
            return _ensure_assets(bible, story), structure, "llm"
        except Exception:
            pass
    bible, structure = fallback_analyze(story)
    return bible, structure, "fallback"


def _ensure_assets(bible: CharacterBible, story: StoryInput) -> CharacterBible:
    guessed, _ = fallback_analyze(story)
    if is_editorial(story.kind):
        bible.characters = guessed.characters
        bible.locations = bible.locations or guessed.locations
        bible.props = []
        return stamp_identity_locks(bible)
    if not bible.locations:
        bible.locations = guessed.locations
    if not bible.props:
        bible.props = guessed.props
    return stamp_identity_locks(bible)
