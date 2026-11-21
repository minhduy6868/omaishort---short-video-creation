from __future__ import annotations

import re

from omaishort.engine.brief_media import knowledge_spoken_from_notes, knowledge_spoken_from_wiki
from omaishort.engine.fallback import fallback_analyze, stamp_identity_locks
from omaishort.providers.llm import complete_json, complete_json_result, load_prompt
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
    prompt_name: str = "knowledge_script.txt",
) -> tuple[str, str, str]:
    """ChatGPT writes the VO first. Wikipedia / README notes are fallback."""
    from omaishort.providers.tts import ensure_spoken_stops

    system = load_prompt(prompt_name)
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


def analyze_user(story: StoryInput) -> str:
    brief = clip_script_brief(story.script_brief)
    extra = f"USER_BRIEF={brief}\n" if brief else ""
    shape = ""
    if not is_editorial(story.kind):
        shape = f"drama_shape={story.drama_shape.value}\n"
    return (
        f"kind={story.kind.value}\n"
        f"mode={story.mode.value}\n"
        f"genre={story.genre.value}\n"
        f"language={story.language}\n"
        f"target_seconds={story.target_seconds}\n"
        f"{shape}"
        f"{extra}\n"
        f"STORY:\n{story.text}"
    )


async def analyze_story(story: StoryInput) -> tuple[CharacterBible, StoryStructure, str]:
    prompt_name = "analyzer_brief.txt" if is_editorial(story.kind) else "analyzer.txt"
    system = load_prompt(prompt_name)
    user = analyze_user(story)
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


async def draft_content_structure(
    *,
    kind: str,
    text: str,
    language: str = "vi",
    target_seconds: int = 90,
    source_url: str | None = None,
    script_brief: str | None = None,
) -> dict[str, object]:
    """Draft a 5-beat Viral Documentary / Storytelling structure via ChatGPT/LLM or smart fallback."""
    from omaishort.engine.brief_media import (
        fetch_article,
        fetch_github_project,
        fetch_knowledge_topic,
        looks_like_github,
        looks_like_url,
    )
    from omaishort_schema.models import Genre, StoryMode, VideoKind

    vkind = VideoKind.knowledge if kind == "knowledge" else VideoKind.news if kind in {"news", "brief"} else VideoKind.drama
    raw_text = (text or "").strip()
    url = (source_url or "").strip()
    if not url and looks_like_url(raw_text):
        url = raw_text
    title = raw_text.split("\n")[0][:80] or "Nội dung mới"
    extract = raw_text

    if vkind in {VideoKind.knowledge, VideoKind.news}:
        if url:
            try:
                if looks_like_github(url):
                    page = await fetch_github_project(url)
                else:
                    page = await fetch_article(url)
                title = page.title or title
                extract = page.text or raw_text
            except Exception:
                pass
        elif vkind == VideoKind.knowledge:
            try:
                page = await fetch_knowledge_topic(raw_text, language)
                title = page.title or title
                extract = page.text or raw_text
            except Exception:
                pass
        prompt_name = "news_script.txt" if vkind == VideoKind.news else "knowledge_script.txt"
        script_text, provider, note = await write_knowledge_script(
            title,
            extract,
            language,
            float(target_seconds or 90),
            topic=raw_text or title,
            script_brief=script_brief or "",
            prompt_name=prompt_name,
        )
        story = StoryInput(
            mode=StoryMode.script,
            kind=vkind,
            text=script_text if len(script_text) >= 8 else (raw_text or title),
            target_seconds=max(15, min(600, int(target_seconds or 90))),
            genre=Genre.knowledge if vkind == VideoKind.knowledge else Genre.news,
            language=language,
            source_url=url or None,
            script_brief=script_brief or None,
        )
        bible, structure = fallback_analyze(story)
        return {
            "title": title,
            "kind": vkind.value,
            "provider": provider,
            "note": note,
            "text": "\n\n".join(
                [
                    structure.hook,
                    structure.conflict,
                    structure.rising_action,
                    structure.twist,
                    structure.ending,
                ]
            ),
            "structure": structure.model_dump(mode="json"),
            "bible": bible.model_dump(mode="json"),
        }

    story = StoryInput(
        mode=StoryMode.script,
        kind=VideoKind.drama,
        text=raw_text if len(raw_text) >= 8 else "Một bí mật bất ngờ được hé lộ lúc nửa đêm.",
        target_seconds=max(15, min(600, int(target_seconds or 60))),
        genre=Genre.drama,
        language=language,
        script_brief=script_brief or None,
    )
    bible, structure, provider = await analyze_story(story)
    return {
        "title": title,
        "kind": VideoKind.drama.value,
        "provider": provider,
        "note": "",
        "text": "\n\n".join(
            [
                structure.hook,
                structure.conflict,
                structure.rising_action,
                structure.twist,
                structure.ending,
            ]
        ),
        "structure": structure.model_dump(mode="json"),
        "bible": bible.model_dump(mode="json"),
    }


async def rewrite_content_beats(
    current: dict[str, object],
    *,
    kind: str = "knowledge",
    language: str = "vi",
    target_seconds: int = 90,
    beat: str = "all",
    instruction: str = "",
    title: str = "",
) -> tuple[dict[str, object], str]:
    """Use ChatGPT / LLM (or smart editorial polish) to rewrite one beat or all 5 beats."""
    system = (
        "You are a senior documentary & viral short-video script editor for 1080x1920 shorts.\n"
        "Return ONLY valid JSON with keys: hook, conflict, rising_action, twist, ending.\n"
        "Follow the 5-part Viral Documentary Storytelling Arc:\n"
        "- hook (Mở đầu gây tò mò): striking paradox, surprising number, or vivid cold open.\n"
        "- conflict (Vấn đề cốt lõi & Tác động): real-world stakes and urgency.\n"
        "- rising_action (Giải mã & Câu chuyện thực tế): concrete step-by-step narrative or mechanism with vivid examples.\n"
        "- twist (Góc khuất bất ngờ & Phản trực giác): counter-intuitive truth or common misconception.\n"
        "- ending (Đúc kết & Ứng dụng): memorable takeaway or actionable conclusion.\n"
        "If target_beat is a single beat (not 'all'), rewrite ONLY that beat to be sharper and keep the other four beats unchanged.\n"
        "Each beat must be 3-5 natural spoken sentences in the requested language."
    )
    user_lines = [
        f"kind={kind}",
        f"title={title}",
        f"language={language}",
        f"target_seconds={target_seconds}",
        f"target_beat={beat}",
    ]
    if instruction.strip():
        user_lines.append(f"EDITOR_INSTRUCTION={instruction.strip()}")
    user_lines.append("CURRENT_STRUCTURE:")
    for key in _SCRIPT_KEYS:
        user_lines.append(f"{key}: {current.get(key) or ''}")
    from omaishort.providers.tts import ensure_spoken_stops

    raw, src, _err = await complete_json_result(system, "\n".join(user_lines))
    updated = dict(current)
    if isinstance(raw, dict):
        src_obj = raw.get("structure") if isinstance(raw.get("structure"), dict) else raw
        keys_to_update = _SCRIPT_KEYS if beat == "all" else tuple(k for k in _SCRIPT_KEYS if k == beat)
        changed = False
        for k in keys_to_update:
            val = re.sub(r"\s+", " ", str(src_obj.get(k) or "")).strip()
            if len(val.split()) >= 5:
                updated[k] = ensure_spoken_stops(val)
                changed = True
        if changed:
            return updated, src or "llm"

    # Smart local polish when LLM/ChatGPT is offline:
    # NEVER inject meta-instructions/hints verbatim into spoken dialogue.
    # Instead, clean cliché intros/fillers, split long run-on sentences for crisp karaoke captions,
    # and enforce spoken stops.
    _weak_intro_re = re.compile(
        r"^(?:xin chào(?: mọi người| các bạn)?|chào mừng(?: các bạn)?|hôm nay chúng ta(?: sẽ| cùng)?|"
        r"trong video này(?: chúng ta sẽ| mình sẽ| tôi sẽ)?|bài viết này|thuyết minh về|"
        r"hello everyone|welcome back|in this video|today we (?:are going to|will)|let'?s talk about)"
        r"[\s,:–—-]+",
        re.I,
    )
    _filler_tail_re = re.compile(
        r"(?:\s*(?:đó là nội dung chính|như vậy chúng ta đã thấy|tổng kết lại là|in conclusion|that is the main content)[.!?…]*)+$",
        re.I,
    )

    def _polish_spoken(text: str, *, is_hook: bool) -> str:
        clean = re.sub(r"https?://\S+", "", text)
        clean = re.sub(r"^\s*[-*#•]+\s*", "", clean, flags=re.M)
        clean = re.sub(r"\s+", " ", clean).strip()
        if is_hook:
            stripped = _weak_intro_re.sub("", clean).strip()
            if len(stripped.split()) >= 4:
                clean = stripped[0].upper() + stripped[1:]
        clean = _filler_tail_re.sub("", clean).strip() or clean
        # Split run-on sentences (>24 words) at natural comma/semicolon pauses for punchier rhythm.
        out_sents: list[str] = []
        for sent in re.split(r"(?<=[.!?…])\s+", clean):
            s = sent.strip()
            if not s:
                continue
            words = s.split()
            if len(words) > 24 and "," in s:
                mid = len(s) // 2
                comma_positions = [m.start() for m in re.finditer(r",\s+", s)]
                if comma_positions:
                    best = min(comma_positions, key=lambda pos: abs(pos - mid))
                    left = s[:best].strip().rstrip(",")
                    right = s[best + 1 :].strip()
                    if len(left.split()) >= 6 and len(right.split()) >= 6:
                        right = right[0].upper() + right[1:] if right else right
                        out_sents.append(f"{left}.")
                        out_sents.append(right)
                        continue
            out_sents.append(s)
        return ensure_spoken_stops(" ".join(out_sents))

    keys_to_update = _SCRIPT_KEYS if beat == "all" else tuple(k for k in _SCRIPT_KEYS if k == beat)
    for k in keys_to_update:
        orig = re.sub(r"\s+", " ", str(updated.get(k) or "")).strip()
        if not orig:
            continue
        updated[k] = _polish_spoken(orig, is_hook=(k == "hook"))
    return updated, "local-polish"
