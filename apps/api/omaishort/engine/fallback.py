from __future__ import annotations

import math
import re

from omaishort.engine.brief_media import (
    is_spoken_prose,
    scrub_brief_vo,
    strip_byline,
    strip_photo_credit,
    strip_related_kicker,
    visual_terms_for_beat,
)
from omaishort.engine.rescale import repair_scene_shots
from omaishort_schema.models import (
    AssetRef,
    Camera,
    Character,
    CharacterBible,
    Motion,
    Scene,
    Shot,
    Storyboard,
    StoryInput,
    StoryStructure,
    VideoKind,
    is_editorial,
)

BEAT_ORDER = ("hook", "conflict", "rising_action", "twist", "ending")
# Wind Comic: hook→push-in, conflict→tight, rising→pan, twist→punch-in, ending→pull-out.
_BEAT_LENSES: dict[str, tuple[tuple[Camera, Motion], tuple[Camera, Motion]]] = {
    "hook": ((Camera.medium, Motion.zoom_in), (Camera.close_up, Motion.zoom_in)),
    "conflict": ((Camera.medium, Motion.hold), (Camera.close_up, Motion.zoom_in)),
    "rising_action": ((Camera.wide, Motion.pan_right), (Camera.medium, Motion.zoom_in)),
    "twist": ((Camera.close_up, Motion.hold), (Camera.close_up, Motion.zoom_in)),
    "ending": ((Camera.medium, Motion.hold), (Camera.wide, Motion.zoom_out)),
}
# News/knowledge stills are already 9:16 (often letterboxed screenshots). Skip close_up punch-ins.
_BEAT_LENSES_EDITORIAL: dict[str, tuple[tuple[Camera, Motion], tuple[Camera, Motion]]] = {
    "hook": ((Camera.medium, Motion.hold), (Camera.medium, Motion.zoom_in)),
    "conflict": ((Camera.medium, Motion.hold), (Camera.medium, Motion.zoom_in)),
    "rising_action": ((Camera.wide, Motion.pan_right), (Camera.medium, Motion.hold)),
    "twist": ((Camera.medium, Motion.hold), (Camera.medium, Motion.zoom_in)),
    "ending": ((Camera.medium, Motion.hold), (Camera.wide, Motion.zoom_out)),
}

LOCATION_CATALOG: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("kitchen", "kitchen at night", "galley kitchen, white cabinets, under-cabinet lights, dark window, tile floor", ("kitchen", "counter")),
    ("hallway", "dim apartment hallway", "narrow apartment hall, warm wall sconce, scuffed wood floor, beige walls", ("hallway", "corridor")),
    ("bedroom", "bedroom doorway", "small bedroom, rumpled white sheets, doorway frame, night lamp", ("bedroom", "bed")),
    ("bathroom", "bathroom mirror", "bathroom vanity, round mirror, warm bulb, tiled wall", ("bathroom", "mirror")),
    ("living_room", "living room couch", "living room, grey sofa, table lamp, dark tv", ("living room", "couch", "sofa")),
    ("street", "rain-wet street", "wet asphalt street at night, sodium streetlights, parked cars", ("street", "outside")),
    ("door", "front door", "apartment front door, peephole, deadbolt, dim porch light", ("front door", "changed the locks", "deadbolt")),
]

BRIEF_LOCATION_CATALOG: list[tuple[str, str, str, tuple[str, ...]]] = [
    ("studio", "news desk", "dark news desk, LED wall, microphone, 9:16 broadcast lighting", ("studio", "desk", "broadcast")),
    ("graphic", "stat graphic", "bold typography poster, one giant number, dark charcoal, no people", ("percent", "mp", "stat", "số", "200")),
    ("product", "product hero", "editorial product photograph, clean backlight, no fashion models", ("iphone", "camera", "device", "sản phẩm")),
    ("newsroom", "newsroom", "newsroom monitors, cool light, no readable text on screens", ("news", "bản tin", "tin")),
    ("city", "city night", "wide city night establishing shot, no crowd close-up", ("city", "thành phố", "ra mắt")),
]

# HyperFrames typed frames, as generated stills (not HTML templates).
BRIEF_TREATMENTS: dict[str, tuple[str, str]] = {
    "hook": (
        "studio",
        "uninhabited broadcast desk, dark LED wall, empty chair, zero people zero faces",
    ),
    "conflict": (
        "graphic",
        "uninhabited typographic stat poster, one giant number on charcoal, zero people",
    ),
    "rising_action": (
        "city",
        "uninhabited wide city night establishing shot, empty streets, zero pedestrians",
    ),
    "twist": (
        "product",
        "uninhabited product hero on black, one device only, no hands no model",
    ),
    "ending": (
        "studio",
        "uninhabited empty news desk outro, lights down, zero people, no readable logo",
    ),
}

_BRIEF_LEAD = re.compile(r"^(?:tiêu đề|headline|title|kicker|tin nóng)\s*[:\-–]\s*", re.I)
# Spoken short: never above 10 minutes, even if TTS would read the whole article.
MAX_SHORT_SEC = 600
_BRIEF_WORDS_PER_SEC = {"vi": 3.15, "en": 2.7}

HUSBAND_ON_CAMERA = (
    "he kissed",
    "he stood",
    "he walked",
    "his back",
    "he turned",
    "beside him",
    "he sat",
    "he asked if i slept",
)
OTHER_ON_CAMERA = ("she stood", "she walked", "mara in the", "the other woman")

INSERT_MARKERS = (
    "phone screen",
    "screen close",
    "close-up of phone",
    "lock screen",
    "insert",
    "hands only",
    "messages on",
)

DIALOGUE_RE = re.compile(
    r"^([A-Za-zÀ-ỹ][A-Za-zÀ-ỹ0-9_' ]{0,28}?)(?:\s*\(([^)]+)\))?\s*[:：]\s+(.+)$",
    re.UNICODE,
)
SPEAKER_ALIASES: dict[str, tuple[str, ...]] = {
    "wife": ("wife", "vo", "vợ", "em", "chi", "chị", "nàng"),
    "husband": ("husband", "chong", "chồng", "anh", "hắn"),
    "other_woman": ("other_woman", "mara", "lover", "cô ta", "người ấy", "co ta"),
}


def parse_dialogue_cues(text: str) -> list[tuple[str, str, str]]:
    """Return (speaker_label, place_hint, spoken_line) for Name: line scripts."""
    cues: list[tuple[str, str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = DIALOGUE_RE.match(line)
        if match:
            cues.append((match.group(1).strip(), (match.group(2) or "").strip(), match.group(3).strip()))
    return cues


def is_dialogue_script(text: str, cues: list[tuple[str, str, str]] | None = None) -> bool:
    cues = cues if cues is not None else parse_dialogue_cues(text)
    nonempty = [ln for ln in text.splitlines() if ln.strip()]
    if len(cues) >= 4:
        return True
    return bool(nonempty) and len(cues) >= 2 and len(cues) >= 0.4 * len(nonempty)


def _speaker_slug(label: str) -> str:
    key = re.sub(r"\s+", " ", label.strip().lower())
    for cid, aliases in SPEAKER_ALIASES.items():
        if key in aliases:
            return cid
    slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_")
    return slug[:40] or "narrator"


def resolve_speaker_id(label: str, bible: CharacterBible) -> str:
    slug = _speaker_slug(label)
    by_id = {char.id.lower(): char.id for char in bible.characters}
    if slug in by_id:
        return by_id[slug]
    if slug in {char.id for char in bible.characters}:
        return slug
    return bible.characters[0].id


def _character_stub(cid: str, label: str) -> Character:
    if cid == "husband":
        return Character(
            id="husband",
            age=32,
            gender="male",
            appearance="early-thirties man, short black hair, faint stubble, sharp jaw",
            clothing="charcoal office shirt, sleeves rolled, watch on left wrist",
            personality="smooth, then cornered",
        )
    if cid == "other_woman":
        return Character(
            id="other_woman",
            age=26,
            gender="female",
            appearance="mid-twenties woman, long straight black hair, red lip",
            clothing="red coat, gold hoop earrings",
            personality="unapologetic",
        )
    return Character(
        id=cid if cid != "narrator" else "wife",
        age=29,
        gender="female",
        appearance="late-twenties woman, dark brown hair in a low knot, tired eyes, small gold stud earrings",
        clothing="black silk robe over a white tank, no jewelry except a thin wedding band",
        personality=f"speaking as {label}",
    )


def _merge_dialogue_cues(cues: list[tuple[str, str, str]], limit: int) -> list[tuple[str, str, str]]:
    merged: list[tuple[str, str, str]] = []
    for label, place, spoken in cues:
        if (
            merged
            and _speaker_slug(merged[-1][0]) == _speaker_slug(label)
            and len(merged[-1][2].split()) + len(spoken.split()) <= 16
        ):
            prev_label, prev_place, prev_spoken = merged[-1]
            merged[-1] = (prev_label, place or prev_place, f"{prev_spoken} {spoken}")
        else:
            merged.append((label, place, spoken))
    while len(merged) > limit:
        idx = min(range(len(merged) - 1), key=lambda i: len(merged[i][2].split()) + len(merged[i + 1][2].split()))
        a, b = merged[idx], merged[idx + 1]
        merged[idx] = (a[0], a[1] or b[1], f"{a[2]} {b[2]}")
        merged.pop(idx + 1)
    return merged[:limit]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


_END_PUNCT = re.compile(r"[.!?…]$")


def ensure_spoken_punct(text: str, language: str = "") -> str:
    """Give VO real sentence stops so edge-tts pauses; capitalize clause starts."""
    blob = re.sub(r"\s+", " ", (text or "").strip())
    if not blob:
        return blob
    parts = [part.strip() for part in re.split(r"(?<=[.!?…])\s+", blob) if part.strip()]
    out: list[str] = []
    for part in parts:
        part = part.strip(" ;,")
        if not part:
            continue
        first = part[0]
        if first.isalpha() and first.islower():
            part = first.upper() + part[1:]
        if not _END_PUNCT.search(part):
            part = part + "."
        out.append(part)
    return " ".join(out) or blob


def _strip_brief_lead(text: str) -> str:
    return _BRIEF_LEAD.sub("", text.strip()).strip()


def brief_word_budget(target_seconds: float, language: str = "en") -> int:
    seconds = max(15, min(int(target_seconds or 60), MAX_SHORT_SEC))
    lang = (language or "en").lower()
    rate = _BRIEF_WORDS_PER_SEC["vi"] if lang.startswith("vi") else _BRIEF_WORDS_PER_SEC["en"]
    return max(48, int(seconds * rate))


def _trim_to_word_budget(text: str, max_words: int) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if max_words <= 0 or not text:
        return text
    parts = _sentences(text) or [text]
    kept: list[str] = []
    count = 0
    for part in parts:
        words = part.split()
        if not words:
            continue
        if kept and count + len(words) > max_words:
            break
        if not kept and len(words) > max_words:
            cut = " ".join(words[:max_words])
            if "," in cut:
                cut = cut.rsplit(",", 1)[0]
            return cut.rstrip(" ,;:") + "."
        kept.append(part)
        count += len(words)
        if count >= max_words:
            break
    return " ".join(kept).strip()


def clamp_brief_vo_blocks(blocks: list[str], max_words: int) -> list[str]:
    cleaned = [re.sub(r"\s+", " ", (block or "").strip()) for block in blocks]
    total = sum(len(block.split()) for block in cleaned)
    if total <= max_words:
        return cleaned
    out: list[str] = []
    used = 0
    for i, block in enumerate(cleaned):
        remaining = max(1, len(cleaned) - i)
        room = max(4, max_words - used)
        share = room if remaining == 1 else max(4, room // remaining)
        first = (_sentences(block) or [block])[0]
        piece = _trim_to_word_budget(block, share) or first
        if len(piece.split()) < 4:
            piece = first
        out.append(piece)
        used += len(piece.split())
    return out


def clamp_brief_storyboard(board: Storyboard, target_seconds: float | None = None, language: str | None = None) -> Storyboard:
    if not is_editorial(board.kind):
        return board
    budget = brief_word_budget(target_seconds or board.target_seconds, language or board.language)
    raw = [scene.dialogue_or_vo for scene in board.scenes]
    if board.kind == VideoKind.knowledge:
        budget = max(budget, int(budget * 1.3))
        total = sum(len((vo or "").split()) for vo in raw)
        if total <= budget:
            for scene in board.scenes:
                scene.dialogue_or_vo = ensure_spoken_punct(scene.dialogue_or_vo, language or board.language)
            return board
    vos = clamp_brief_vo_blocks(raw, budget)
    filler = "Một bản tin ngắn." if (language or board.language or "").lower().startswith("vi") else "A news brief."
    for scene, vo in zip(board.scenes, vos):
        spoken = ensure_spoken_punct(vo if len(vo.split()) >= 4 else (vo or filler), language or board.language)
        scene.dialogue_or_vo = spoken
    return board


def _norm_brief_unit(text: str) -> str:
    return re.sub(r"\W+", " ", (text or "").lower()).strip()


def _dedupe_brief_units(units: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for unit in units:
        key = _norm_brief_unit(unit)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(unit)
    return out


def _drop_title_echo(units: list[str]) -> list[str]:
    if len(units) < 2:
        return units
    title_words = set(_norm_brief_unit(units[0]).split())
    next_words = set(_norm_brief_unit(units[1]).split())
    if title_words and len(title_words & next_words) / len(title_words) >= 0.5:
        return units[1:]
    return units


def _hook_score(text: str) -> int:
    blob = text.lower()
    score = 0
    if re.search(r"\d+", text):
        score += 3
    if any(token in blob for token in ("nên duyên", "kết hôn", "lấy ", "yêu", "hẹn hò", "gặp")):
        score += 4
    if any(token in blob for token in ("tháng", "ngày", "năm")):
        score += 2
    return score


def _pick_lede(units: list[str]) -> tuple[str, list[str]]:
    if not units:
        return "Một bản tin ngắn.", []
    window = units[:6]
    best = max(window, key=_hook_score)
    rest = [unit for unit in units if unit != best]
    return best, rest


def _fill_brief_units(units: list[str], budget: int, *, keep_tail: bool = False) -> list[str]:
    if keep_tail:
        selected: list[str] = []
        count = 0
        for unit in reversed(units):
            words = len(unit.split())
            if selected and count >= budget:
                break
            if selected and count + words > budget + 12:
                break
            selected.append(unit)
            count += words
        selected.reverse()
        return selected or units[-1:]
    selected: list[str] = []
    count = 0
    for unit in units:
        words = len(unit.split())
        if selected and count >= budget:
            break
        if selected and count + words > budget + 12:
            break
        selected.append(unit)
        count += words
    return selected or units[:1]


def _halve_vo(text: str) -> tuple[str, str]:
    parts = _sentences(text)
    if len(parts) >= 2:
        mid = max(1, len(parts) // 2)
        return " ".join(parts[:mid]), " ".join(parts[mid:])
    words = text.split()
    if len(words) < 14:
        return text, ""
    mid = len(words) // 2
    return " ".join(words[:mid]), " ".join(words[mid:])


def _ensure_brief_groups(groups: list[str], n: int) -> list[str]:
    groups = [group for group in groups if group.strip()]
    while len(groups) < n:
        idx = max(range(len(groups)), key=lambda i: len(groups[i].split()))
        left, right = _halve_vo(groups[idx])
        if not right:
            break
        groups[idx] = left
        groups.insert(idx + 1, right)
    while len(groups) > n:
        tail = groups.pop()
        groups[-1] = f"{groups[-1]} {tail}"
    while len(groups) < n:
        groups.append(groups[-1] if groups else "Một bản tin ngắn.")
    return groups[:n]


def _brief_units(text: str, language: str = "") -> list[str]:
    title = _strip_brief_lead(text.strip().split("\n")[0]) if text.strip() else ""
    units: list[str] = []
    for line in text.replace("\r", "").split("\n"):
        line = _strip_brief_lead(line.strip())
        if not line:
            continue
        parts = _sentences(line) or [line]
        for part in parts:
            part = strip_byline(strip_photo_credit(strip_related_kicker(part.strip(), title)))
            if part and is_spoken_prose(part, language):
                units.append(part)
    fallback = ["A news brief."] if not (language or "").startswith("vi") else ["Một bản tin ngắn."]
    return _drop_title_echo(_dedupe_brief_units(units)) or fallback


def _quintile_units(units: list[str], n: int = 5) -> list[list[str]]:
    buckets: list[list[str]] = [[] for _ in range(n)]
    if not units:
        return buckets
    last = units[-1]
    for i, unit in enumerate(units):
        idx = min(n - 1, int(i * n / max(1, len(units))))
        buckets[idx].append(unit)
    if last not in buckets[-1]:
        for bucket in buckets[:-1]:
            if last in bucket:
                bucket.remove(last)
        buckets[-1].append(last)
    return buckets


def _authored_brief_beats(text: str, language: str) -> list[str] | None:
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]
    if len(paras) != 5:
        return None
    if any(len(p.split()) < 8 for p in paras):
        return None
    return [ensure_spoken_punct(_strip_brief_lead(p), language) for p in paras]


def _brief_spoken_beats(text: str, target: int, language: str) -> list[str]:
    authored = _authored_brief_beats(text, language)
    if authored:
        return authored
    budget = brief_word_budget(target, language)
    share = max(16, budget // 5)
    units = _brief_units(text, language)
    buckets = _quintile_units(units, 5)
    lead = _strip_brief_lead(text.strip().split("\n")[0]) if text.strip() else ""
    title_key = _norm_brief_unit(lead)
    if buckets[0]:
        hook = max(buckets[0], key=_hook_score)
        buckets[0] = [hook] + [unit for unit in buckets[0] if unit != hook]
    vos: list[str] = []
    last = len(buckets) - 1
    for i, bucket in enumerate(buckets):
        filled = _fill_brief_units(bucket, share, keep_tail=i == last) if bucket else []
        if title_key and len(filled) > 1:
            trimmed = [unit for unit in filled if _norm_brief_unit(unit) != title_key]
            if trimmed:
                filled = trimmed
        vos.append(ensure_spoken_punct(" ".join(filled).strip(), language))
    return [ensure_spoken_punct(item, language) for item in _ensure_brief_groups(vos, 5)]


def _distribute_brief_vo(units: list[str], n: int = 5) -> list[str]:
    if not units:
        return ["A news brief."] * n
    weights = [max(1, len(unit.split())) for unit in units]
    total = sum(weights)
    target = total / n
    groups: list[str] = []
    buf: list[str] = []
    weight = 0
    for unit, w in zip(units, weights):
        if buf and weight >= target and len(groups) < n - 1:
            groups.append(" ".join(buf))
            buf = [unit]
            weight = w
        else:
            buf.append(unit)
            weight += w
    if buf:
        groups.append(" ".join(buf))
    while len(groups) < n:
        groups.append(groups[-1] if groups else "A news brief.")
    while len(groups) > n:
        tail = groups.pop()
        groups[-1] = f"{groups[-1]} {tail}"
    return groups


def _chunk_sentences(sentences: list[str], target_scenes: int) -> list[list[str]]:
    if not sentences:
        return [["A quiet confession begins."]]
    target = max(8, min(15, target_scenes))
    n = len(sentences)
    if n <= 15:
        groups: list[list[str]] = []
        buf: list[str] = []
        for sentence in sentences:
            words = len(sentence.split())
            if buf and (len(" ".join(buf).split()) + words) <= 7:
                buf.append(sentence)
                continue
            if buf:
                groups.append(buf)
            buf = [sentence]
        if buf:
            groups.append(buf)
        while len(groups) > 15:
            tail = groups.pop()
            groups[-1].extend(tail)
        return groups
    size = max(1, math.ceil(n / target))
    groups = [sentences[i : i + size] for i in range(0, n, size)]
    while len(groups) > 15:
        tail = groups.pop()
        groups[-1].extend(tail)
    return groups


def _guess_locations(kind: VideoKind = VideoKind.drama) -> list[AssetRef]:
    catalog = BRIEF_LOCATION_CATALOG if is_editorial(kind) else LOCATION_CATALOG
    return [
        AssetRef(id=loc_id, description=desc, appearance=appearance)
        for loc_id, desc, appearance, _keys in catalog
    ]


def _guess_props(text: str) -> list[AssetRef]:
    lowered = text.lower()
    props: list[AssetRef] = []
    if any(w in lowered for w in ("phone", "messages", "lock screen", "texted")):
        props.append(
            AssetRef(
                id="phone",
                description="husband's smartphone",
                appearance="black glass smartphone, lock-screen couple photo, faint fingerprint smudge",
            )
        )
    return props


def _guess_characters(text: str, kind: VideoKind = VideoKind.drama) -> CharacterBible:
    if is_editorial(kind):
        return CharacterBible(
            characters=[
                Character(
                    id="narrator",
                    age=None,
                    gender=None,
                    appearance="not on camera",
                    clothing="n/a",
                    personality="clear news VO",
                )
            ],
            locations=_guess_locations(kind),
            props=[],
        )
    cues = parse_dialogue_cues(text)
    if is_dialogue_script(text, cues):
        chars: list[Character] = []
        seen: set[str] = set()
        for label, _place, _spoken in cues:
            cid = _speaker_slug(label)
            if cid in seen:
                continue
            seen.add(cid)
            chars.append(_character_stub(cid, label))
            if len(chars) >= 5:
                break
        if not chars:
            chars.append(_character_stub("wife", "wife"))
        return CharacterBible(characters=chars, locations=_guess_locations(), props=_guess_props(text))
    lowered = text.lower()
    first_person = bool(re.search(r"\bi\b", lowered))
    husband_cues = ("husband", "he left", "his phone", "he said", "he typed", "he kissed", "he called", "his mother")
    protagonist = "wife" if first_person and any(w in lowered for w in husband_cues) else "narrator"
    chars: list[Character] = [
        Character(
            id=protagonist,
            age=29,
            gender="female",
            appearance="late-twenties woman, dark brown hair in a low knot, tired eyes, small gold stud earrings",
            clothing="black silk robe over a white tank, no jewelry except a thin wedding band",
            personality="controlled, then cracking",
        )
    ]
    if any(w in lowered for w in husband_cues):
        chars.append(
            Character(
                id="husband",
                age=32,
                gender="male",
                appearance="early-thirties man, short black hair, faint stubble, sharp jaw",
                clothing="charcoal office shirt, sleeves rolled, watch on left wrist",
                personality="smooth, then cornered",
            )
        )
    if any(w in lowered for w in ("her name", "the other woman", "her lipstick", "mistress", "mara")):
        chars.append(
            Character(
                id="other_woman",
                age=26,
                gender="female",
                appearance="mid-twenties woman, long straight black hair, red lip",
                clothing="red coat, gold hoop earrings",
                personality="unapologetic",
            )
        )
    return CharacterBible(characters=chars, locations=_guess_locations(), props=_guess_props(text))


def _guess_structure(text: str, target: int) -> StoryStructure:
    sentences = _sentences(text)
    n = max(5, len(sentences))
    def at(frac: float) -> str:
        idx = min(len(sentences) - 1, int(frac * n))
        return sentences[idx]
    return StoryStructure(
        hook=at(0.02),
        conflict=at(0.22),
        rising_action=at(0.5),
        twist=at(0.78),
        ending=at(0.96),
        hook_sec=round(target * 0.10, 2),
        conflict_sec=round(target * 0.20, 2),
        rising_sec=round(target * 0.33, 2),
        twist_sec=round(target * 0.23, 2),
        ending_sec=round(target * 0.14, 2),
    )


def _guess_structure_brief(text: str, target: int, language: str = "vi") -> StoryStructure:
    vos = _brief_spoken_beats(text, target, language)
    secs = (0.14, 0.22, 0.28, 0.22, 0.14)
    return StoryStructure(
        hook=vos[0],
        conflict=vos[1],
        rising_action=vos[2],
        twist=vos[3],
        ending=vos[4],
        hook_sec=round(target * secs[0], 2),
        conflict_sec=round(target * secs[1], 2),
        rising_sec=round(target * secs[2], 2),
        twist_sec=round(target * secs[3], 2),
        ending_sec=round(target * secs[4], 2),
    )


def infer_beat(scene: Scene, index: int = 0, total: int = 1) -> str:
    blob = f"{scene.emotion} {scene.mood}".lower().replace("-", " ")
    aliases = (
        ("rising_action", ("rising_action", "rising dread", "rising")),
        ("hook", ("hook",)),
        ("conflict", ("conflict",)),
        ("twist", ("twist",)),
        ("ending", ("ending", "ending beat", "end beat")),
    )
    for beat, keys in aliases:
        if any(key in blob for key in keys):
            return beat
    span = max(1, total)
    return BEAT_ORDER[min(len(BEAT_ORDER) - 1, int(index / span * 5))]


def beat_shots(still_id: str, duration: float, beat: str, *, editorial: bool = False) -> list[Shot]:
    table = _BEAT_LENSES_EDITORIAL if editorial else _BEAT_LENSES
    first, second = table.get(beat, table["hook"])
    if duration < 3.2:
        return [
            Shot(camera=first[0], motion=first[1], t_start=0, t_end=duration, still_id=still_id),
        ]
    split = round(duration * 0.45, 2)
    return [
        Shot(camera=first[0], motion=first[1], t_start=0, t_end=split, still_id=still_id),
        Shot(camera=second[0], motion=second[1], t_start=split, t_end=duration, still_id=still_id),
    ]


def apply_beat_lenses(board: Storyboard) -> Storyboard:
    total = max(1, len(board.scenes))
    editorial = is_editorial(board.kind)
    for i, scene in enumerate(board.scenes):
        beat = infer_beat(scene, i, total)
        scene.shots = beat_shots(scene.still_id, scene.duration_sec, beat, editorial=editorial)
        repair_scene_shots(scene)
    return board


def _keyword_hit(text: str, keys: tuple[str, ...]) -> bool:
    lowered = text.lower()
    for key in keys:
        if " " in key:
            if key in lowered:
                return True
        elif re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", lowered):
            return True
    return False


def visible_character_ids(vo: str, bible: CharacterBible) -> list[str]:
    ids = [char.id for char in bible.characters]
    if not ids:
        return []
    present = [ids[0]]
    lowered = vo.lower()
    if "husband" in ids and any(cue in lowered for cue in HUSBAND_ON_CAMERA):
        present.append("husband")
    if "other_woman" in ids and any(cue in lowered for cue in OTHER_ON_CAMERA):
        present.append("other_woman")
    return present


def is_insert_scene(location: str, vo: str) -> bool:
    blob = f"{location} {vo}".lower()
    if not any(marker in blob for marker in INSERT_MARKERS):
        return False
    sents = [s for s in re.split(r"(?<=[.!?])\s+", vo.strip()) if s.strip()] or [vo]
    insert_sents = sum(1 for sent in sents if any(marker in sent.lower() for marker in INSERT_MARKERS))
    if len(vo.split()) <= 16:
        return True
    return insert_sents >= max(1, math.ceil(len(sents) / 2))


def _slug_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:40] or "place"


def _match_location(blob: str, locations: list[AssetRef]) -> AssetRef | None:
    by_id = {loc.id: loc for loc in locations}
    for catalog in (LOCATION_CATALOG, BRIEF_LOCATION_CATALOG):
        for loc_id, _desc, _appearance, keys in catalog:
            if _keyword_hit(blob, keys) and loc_id in by_id:
                return by_id[loc_id]
    for loc in locations:
        tokens = tuple([loc.id] + [w for w in loc.description.lower().split() if len(w) > 4])
        if _keyword_hit(blob, tokens):
            return loc
    return None


def pick_location(
    vo: str,
    index: int,
    locations: list[AssetRef],
    previous: AssetRef | None = None,
) -> AssetRef:
    if not locations:
        loc_id, desc, appearance, _keys = LOCATION_CATALOG[(index - 1) % len(LOCATION_CATALOG)]
        return AssetRef(id=loc_id, description=desc, appearance=appearance)
    matched = _match_location(vo, locations)
    if matched:
        return matched
    if previous and previous.id in {loc.id for loc in locations}:
        return previous
    return locations[0]


def replan_locations(board: Storyboard, bible: CharacterBible) -> None:
    """Re-bind location_id from VO so leftover catalog rotation does not invent a street."""
    locations = list(bible.locations) or _guess_locations()
    previous: AssetRef | None = None
    for i, scene in enumerate(board.scenes, start=1):
        loc = pick_location(scene.dialogue_or_vo, i, locations, previous=previous)
        insert = is_insert_scene(scene.location, scene.dialogue_or_vo)
        if insert and previous:
            loc = previous
            scene.use_location_ref = False
        scene.location_id = loc.id
        if not insert:
            scene.location = loc.description
        previous = loc


def bind_scene_assets(board: Storyboard, bible: CharacterBible) -> None:
    if is_editorial(board.kind):
        by_id = {loc.id: loc for loc in bible.locations}
        for scene in board.scenes:
            scene.use_face_ref = False
            scene.use_location_ref = False
            if scene.location_id and scene.location_id in by_id and not scene.location:
                scene.location = by_id[scene.location_id].description
        return
    by_id = {loc.id: loc for loc in bible.locations}
    reused: dict[str, str] = {}
    for loc in bible.locations:
        reused[loc.description.strip().lower()] = loc.id
        reused[loc.id] = loc.id
    prop_ids = {prop.id for prop in bible.props}
    for scene in board.scenes:
        if scene.location_id and scene.location_id in by_id:
            if not scene.location:
                scene.location = by_id[scene.location_id].description
        else:
            key = (scene.location or "").strip().lower()
            if key in reused:
                scene.location_id = reused[key]
            else:
                matched = _match_location(f"{scene.location} {scene.dialogue_or_vo}", bible.locations)
                if matched:
                    scene.location_id = matched.id
                    if key:
                        reused[key] = matched.id
                else:
                    slug = _slug_id(scene.location or f"place_{scene.index}")
                    scene.location_id = slug
                    if key:
                        reused[key] = slug
        if is_insert_scene(scene.location, scene.dialogue_or_vo):
            scene.use_location_ref = False
            if "phone" in f"{scene.location} {scene.dialogue_or_vo}".lower() and len(scene.dialogue_or_vo.split()) <= 16:
                scene.use_face_ref = False
        if "phone" in prop_ids and "phone" in scene.dialogue_or_vo.lower() and "phone" not in scene.prop_ids:
            scene.prop_ids.append("phone")


def normalize_storyboard(board: Storyboard, bible: CharacterBible) -> Storyboard:
    valid = {char.id for char in bible.characters}
    default = bible.characters[0].id if bible.characters else "narrator"
    used_visuals: list[str] = []
    for scene in board.scenes:
        if is_editorial(board.kind):
            scene.use_face_ref = False
            scene.use_location_ref = False
            scene.speaker_id = None
            scene.characters = []
            scene.dialogue_or_vo = scrub_brief_vo(_strip_brief_lead(scene.dialogue_or_vo), board.language)
            beat = infer_beat(scene, max(0, scene.index - 1), max(1, len(board.scenes)))
            loc_id, action = BRIEF_TREATMENTS.get(beat, BRIEF_TREATMENTS["hook"])
            scene.action = _editorial_action(scene.dialogue_or_vo, action, used_visuals)
            scene.location_id = loc_id
            loc = next((item for item in bible.locations if item.id == loc_id), None)
            if loc:
                scene.location = loc.description
        elif scene.speaker_id and scene.speaker_id in valid:
            extras = [cid for cid in scene.characters if cid in valid and cid != scene.speaker_id]
            scene.characters = [scene.speaker_id] + extras[:1]
        else:
            scene.characters = [cid for cid in visible_character_ids(scene.dialogue_or_vo, bible) if cid in valid] or [default]
        if scene.duration_sec <= 0:
            scene.duration_sec = 4.0
        repair_scene_shots(scene)
    apply_beat_lenses(board)
    bind_scene_assets(board, bible)
    if is_editorial(board.kind):
        clamp_brief_storyboard(board)
    return board


def fallback_analyze(story: StoryInput) -> tuple[CharacterBible, StoryStructure]:
    bible = _guess_characters(story.text, story.kind)
    if is_editorial(story.kind):
        return bible, _guess_structure_brief(story.text, story.target_seconds, story.language)
    return bible, _guess_structure(story.text, story.target_seconds)


def _scale_scenes(scenes: list[Scene], target: float) -> None:
    scale = target / max(0.1, sum(s.duration_sec for s in scenes))
    for scene in scenes:
        scene.duration_sec = round(scene.duration_sec * scale, 2)
        for shot in scene.shots:
            shot.t_start = round(shot.t_start * scale, 2)
            shot.t_end = round(shot.t_end * scale, 2)
        repair_scene_shots(scene)


def _plan_dialogue(
    story: StoryInput,
    bible: CharacterBible,
    structure: StoryStructure,
    cues: list[tuple[str, str, str]],
) -> Storyboard:
    groups = _merge_dialogue_cues(cues, max(4, min(15, round(story.target_seconds / 5))))
    total_words = sum(len(item[2].split()) for item in groups) or 1
    locations = list(bible.locations) or _guess_locations()
    scenes: list[Scene] = []
    prev_speaker: str | None = None
    for i, (label, place, spoken) in enumerate(groups, start=1):
        speaker = resolve_speaker_id(label, bible)
        duration = max(2.8, story.target_seconds * (len(spoken.split()) / total_words))
        still_id = f"still_{i:02d}"
        beat_name = BEAT_ORDER[min(len(BEAT_ORDER) - 1, int((i - 1) / max(1, len(groups)) * 5))]
        previous = next((item for item in locations if item.id == scenes[-1].location_id), None) if scenes else None
        loc = pick_location(f"{place} {spoken}", i, locations, previous=previous)
        other = prev_speaker if prev_speaker and prev_speaker != speaker else None
        action = (
            f"{speaker} speaking to {other} in {loc.description}"
            if other
            else f"{speaker} speaking in {loc.description}"
        )
        scenes.append(
            Scene(
                index=i,
                duration_sec=round(duration, 2),
                location=loc.description,
                location_id=loc.id,
                characters=[speaker],
                prop_ids=["phone"] if "phone" in spoken.lower() and any(p.id == "phone" for p in bible.props) else [],
                emotion=beat_name if beat_name != "rising_action" else "rising dread",
                action=action,
                dialogue_or_vo=spoken,
                lighting="practical lamps, cinematic contrast, 9:16",
                mood=beat_name,
                consistency_notes="same wardrobe; reverse shot on the speaker",
                still_id=still_id,
                shots=beat_shots(still_id, round(duration, 2), beat_name),
                use_face_ref=True,
                use_location_ref=True,
                speaker_id=speaker,
            )
        )
        prev_speaker = speaker
    _scale_scenes(scenes, float(story.target_seconds))
    title = f"{groups[0][0]}: {groups[0][2]}"[:72] if groups else "Untitled short"
    board = Storyboard(
        title=title,
        target_seconds=float(story.target_seconds),
        language=story.language,
        kind=story.kind,
        scenes=scenes,
    )
    return normalize_storyboard(board, bible)


def _editorial_action(vo: str, fallback: str, used: list[str] | None = None) -> str:
    terms = visual_terms_for_beat(vo)
    used = used if used is not None else []
    term = next((item for item in terms if item not in used), None) or (terms[0] if terms else None)
    if not term:
        return fallback
    used.append(term)
    return f"uninhabited editorial photograph of {term}, zero people zero faces"


def _plan_brief(story: StoryInput, bible: CharacterBible, structure: StoryStructure) -> Storyboard:
    vos = _brief_spoken_beats(story.text, story.target_seconds, story.language)
    durations = [
        structure.hook_sec,
        structure.conflict_sec,
        structure.rising_sec,
        structure.twist_sec,
        structure.ending_sec,
    ]
    locations = list(bible.locations) or _guess_locations(story.kind)
    by_id = {loc.id: loc for loc in locations}
    scenes: list[Scene] = []
    for i, beat_name in enumerate(BEAT_ORDER, start=1):
        loc_id, treatment = BRIEF_TREATMENTS[beat_name]
        loc = by_id.get(loc_id) or locations[(i - 1) % len(locations)]
        vo = vos[i - 1]
        duration = max(4.0, float(durations[i - 1] or 8))
        still_id = f"still_{i:02d}"
        scenes.append(
            Scene(
                index=i,
                duration_sec=round(duration, 2),
                location=loc.description,
                location_id=loc.id,
                characters=[],
                prop_ids=[],
                emotion=beat_name,
                action=_editorial_action(vo, treatment),
                dialogue_or_vo=vo,
                lighting="broadcast contrast, 9:16, no on-image text",
                mood=beat_name,
                consistency_notes="editorial brief; uninhabited still",
                still_id=still_id,
                shots=beat_shots(still_id, round(duration, 2), beat_name, editorial=True),
                use_face_ref=False,
                use_location_ref=False,
            )
        )
    _scale_scenes(scenes, float(story.target_seconds))
    title = _strip_brief_lead(story.text.strip().split("\n")[0])[:72] or "Untitled brief"
    board = Storyboard(
        title=title,
        target_seconds=float(story.target_seconds),
        language=story.language,
        kind=story.kind,
        scenes=scenes,
    )
    return normalize_storyboard(board, bible)


def fallback_plan(story: StoryInput, bible: CharacterBible, structure: StoryStructure) -> Storyboard:
    if is_editorial(story.kind):
        return _plan_brief(story, bible, structure)
    cues = parse_dialogue_cues(story.text)
    if is_dialogue_script(story.text, cues):
        return _plan_dialogue(story, bible, structure, cues)
    target_scenes = max(8, min(15, round(story.target_seconds / 6)))
    groups = _chunk_sentences(_sentences(story.text), target_scenes)
    total_words = sum(len(" ".join(g).split()) for g in groups) or 1
    locations = list(bible.locations) or _guess_locations()
    scenes: list[Scene] = []
    beats = [structure.hook, structure.conflict, structure.rising_action, structure.twist, structure.ending]
    for i, group in enumerate(groups, start=1):
        vo = " ".join(group)
        duration = max(3.5, story.target_seconds * (len(vo.split()) / total_words))
        still_id = f"still_{i:02d}"
        beat_name = BEAT_ORDER[min(len(BEAT_ORDER) - 1, int((i - 1) / max(1, len(groups)) * 5))]
        back = any(w in vo.lower() for w in ("walked away", "his back", "turned away"))
        present = visible_character_ids(vo, bible)
        previous = next((item for item in locations if item.id == scenes[-1].location_id), None) if scenes else None
        loc = pick_location(vo, i, locations, previous=previous)
        insert = is_insert_scene(loc.description, vo)
        if insert and scenes:
            prev = next((item for item in locations if item.id == scenes[-1].location_id), None)
            if prev:
                loc = prev
        location_label = "phone screen close" if insert else loc.description
        scenes.append(
            Scene(
                index=i,
                duration_sec=round(duration, 2),
                location=location_label,
                location_id=loc.id,
                characters=present,
                prop_ids=["phone"] if (insert or "phone" in vo.lower()) and any(p.id == "phone" for p in bible.props) else [],
                emotion=beat_name if beat_name != "rising_action" else "rising dread",
                action=vo[:140],
                dialogue_or_vo=vo,
                lighting="practical lamps, cinematic contrast, 9:16",
                mood=beats[min(i - 1, len(beats) - 1)][:80],
                consistency_notes="keep narrator wardrobe and wedding band",
                still_id=still_id,
                shots=beat_shots(still_id, round(duration, 2), beat_name),
                use_face_ref=not back and not (insert and len(vo.split()) <= 16),
                use_location_ref=not insert,
            )
        )
    scale = story.target_seconds / max(0.1, sum(s.duration_sec for s in scenes))
    for scene in scenes:
        scene.duration_sec = round(scene.duration_sec * scale, 2)
        for shot in scene.shots:
            shot.t_start = round(shot.t_start * scale, 2)
            shot.t_end = round(shot.t_end * scale, 2)
        repair_scene_shots(scene)
    title = story.text.strip().split("\n")[0][:72] or "Untitled short"
    board = Storyboard(
        title=title,
        target_seconds=float(story.target_seconds),
        language=story.language,
        kind=story.kind,
        scenes=scenes,
    )
    return normalize_storyboard(board, bible)
