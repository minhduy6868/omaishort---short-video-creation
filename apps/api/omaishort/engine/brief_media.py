from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from PIL import Image, ImageOps

from omaishort.providers.placeholder import HEIGHT, WIDTH

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
# Wikimedia requires a descriptive UA; browser UA is fine for publisher CDNs.
_WIKI_UA = (
    "omaishort/0.1 (https://github.com/minhduy6868/omaishort---short-video-creation; "
    "brief stills) python-httpx"
)
_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
_SKIP = (
    "logo",
    "sprite",
    "favicon",
    "emoji",
    "avatar",
    "icon",
    "pixel",
    "tracking",
    "1x1",
    "72x72",
    "114x114",
    "57x57",
    "nguonuutien",
    "restruct/i/",
    "placeholder",
    "default-image",
    "spinner",
)
_SKIP_HOST = ("doubleclick", "facebook.com", "google", "scorecard")
_SKIP_WIKI_FILE = (
    "coat of arms",
    "locator map",
    "location map",
    "flag of",
    "logo",
    "icon",
    "signature",
    "diagram",
    "family tree",
    "svg",
)
# pattern → Commons query, optional Wikipedia title (MPVSAP proper-noun B-roll).
_QUERY_ALIASES: tuple[tuple[str, str, str | None], ...] = (
    (r"vĩnh\s*long|\bvinh\s*long\b", "Vinh Long Vietnam", "Vĩnh Long"),
    (r"đồng\s*nai|dong nai", "Dong Nai Vietnam", "Đồng Nai"),
    (r"cần\s*thơ|can tho", "Can Tho Vietnam", "Cần Thơ"),
    (r"hà\s*nội|ha noi|hanoi", "Hanoi Vietnam", "Hà Nội"),
    (r"sài\s*gòn|tp\.?\s*hcm|ho chi minh", "Ho Chi Minh City Vietnam", "Thành phố Hồ Chí Minh"),
    (r"đà\s*nẵng|\bda nang\b", "Da Nang Vietnam", "Đà Nẵng"),
    (r"mekong|cửu\s*long", "Mekong Delta Vietnam", "Đồng bằng sông Cửu Long"),
    (r"thợ\s*điện|tho dien|electrician", "electrician power lines Vietnam", None),
    (r"cô gái nga|người nga|russian woman", "Vietnam countryside river", None),
    (r"yorkshire|dewsbury|bradford", "Yorkshire England town", None),
    (r"nigeria", "Nigeria West Africa", None),
    (r"anh quốc|nước anh|\bengland\b", "England countryside house", None),
    (r"trần hưng đạo|hưng đạo vương", "Tran Hung Dao temple statue Vietnam", "Trần Hưng Đạo"),
    (r"vua hùng|hùng vương|các vua hùng", "Hung Kings temple Vietnam", "Hùng Vương"),
    (r"sự tích vua hùng|đền hùng", "Den Hung temple Phu Tho", "Đền Hùng"),
    (r"lạc long|âu cơ|trăm trứng", "Lac Long Quan Au Co legend Vietnam", "Lạc Long Quân"),
    (r"bạch đằng", "Bach Dang river Vietnam", "Bạch Đằng"),
    (r"nguyên mông|mông cổ", "Mongol cavalry", None),
    (r"ngân hàng trung ương|central bank", "central bank building", None),
)
_VISUAL_ALIASES: tuple[tuple[str, str], ...] = (
    (r"rổ hàng|siêu thị|giá hàng", "grocery supermarket food prices"),
    (r"sức mua|túi tiền|tiền trong túi", "wallet cash buying power"),
    (r"cầu vượt cung|lượng tiền", "busy marketplace demand"),
    (r"xăng|gas station", "gas station fuel pump"),
    (r"chỉ số giá|\bcpi\b|lãi suất", "consumer price index chart"),
    (r"ly hôn|divorce", "divorce empty house"),
    (r"north cyprus|bắc síp", "Northern Cyprus coast"),
    (r"kém \d+\s*tuổi|chênh lệch tuổi|age gap", "age gap couple"),
    (r"kết hôn|cưới|đăng ký kết hôn|wedding", "wedding rings ceremony"),
    (r"hẹn hò|dating app|ứng dụng hẹn hò", "smartphone dating app"),
    (r"máy chủ|\bvps\b|triển khai", "self hosted server rack"),
    (r"inbox|hộp thư|phễu bán|\bfunnel\b", "sales inbox laptop"),
    (r"lead\b|bỏ quên|mất lịch sử", "empty office desk chair"),
    (r"tài sản|giữ tài sản", "house keys property documents"),
    (r"bỏ đi|bỏ rơi", "packed suitcase empty home"),
    (r"thị thực|visa", "passport visa stamp"),
    (r"sinh viên|student visa", "university student"),
    (r"rắn|snake", "snake in grass"),
    (r"5g|phủ sóng", "5G cell tower"),
    (r"github|repository|\brepo\b", "source code editor dark screen"),
    (r"whatsapp|\bwaha\b", "whatsapp chat phone business"),
    (r"\bcrm\b|sales os|intercom|kommo", "crm dashboard sales inbox"),
    (r"self-hosted|self hosted|multi-tenant", "self hosted server rack"),
    (r"\bmcp\b|ai agent", "ai agent laptop dark screen"),
    (r"python|pytorch|tensorflow", "python code laptop"),
    (r"neural|transformer|machine learning|học máy", "neural network diagram"),
    (r"api|http", "api documentation screen"),
    (r"docker|container", "server rack containers"),
    (r"trần hưng đạo|hưng đạo", "Tran Hung Dao statue temple"),
    (r"vua hùng|hùng vương|các vua hùng", "Hung Kings temple Vietnam"),
    (r"sự tích|đền hùng|giỗ tổ", "Den Hung festival Phu Tho"),
    (r"lạc long|âu cơ|trăm trứng", "Lac Long Quan Au Co Vietnam legend"),
    (r"bạch đằng", "Bach Dang river wooden stakes"),
    (r"nguyên mông|mông cổ", "Mongol cavalry horde"),
    (r"kiếp bạc|đền thờ", "Kiep Bac temple Vietnam"),
    (r"cọc gỗ|cọc ngầm", "wooden river stakes"),
    (r"thủy triều", "tidal river estuary"),
    (r"lãi suất|interest rate", "central bank interest rate"),
    (r"tiền giấy|banknotes|currency", "banknotes currency stack"),
    (r"mâu thuẫn|cãi vã", "tense doorway argument still"),
    (r"vé máy bay|máy bay|airport", "airport departure hall"),
    (r"tiền nước|hóa đơn", "utility bill documents"),
)

_SRCSET_SPLIT = re.compile(r"\s*,\s*")


@dataclass
class ArticlePage:
    url: str
    title: str
    text: str
    image_urls: list[str]
    image_captions: dict[str, str] = field(default_factory=dict)


def looks_like_url(value: str) -> bool:
    return value.strip().lower().startswith(("http://", "https://"))


_GITHUB_REPO = re.compile(r"https?://(?:www\.)?github\.com/([^/]+)/([^/#?]+)", re.I)


def looks_like_github(url: str) -> bool:
    match = _GITHUB_REPO.match((url or "").strip())
    if not match:
        return False
    owner = match.group(1).lower()
    return owner not in {"orgs", "settings", "topics", "search", "features", "pricing"}


def github_repo_slug(url: str) -> tuple[str, str] | None:
    match = _GITHUB_REPO.match((url or "").strip())
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    repo = repo.removesuffix(".git").strip()
    if not owner or not repo or not looks_like_github(url):
        return None
    return owner, repo


_TOPIC_PREFIX = re.compile(
    r"^\s*(?:tiêu đề:\s*)?(?:"
    r"hãy\s+tạo(?:\s+một)?(?:\s+video)?(?:\s+thuyết\s+minh)?(?:\s+về)?|"
    r"làm(?:\s+một)?(?:\s+video)?(?:\s+thuyết\s+minh)?(?:\s+về)?|"
    r"video\s+thuyết\s+minh(?:\s+về)?|"
    r"soạn\s+lời(?:\s+về)?|"
    r"kể(?:\s+về)?|"
    r"thuyết minh(?:\s+về)?|giải thích(?:\s+về)?|"
    r"tóm tắt(?:\s+về)?|tìm hiểu(?:\s+về)?|hướng dẫn(?:\s+về)?|"
    r"explain(?:ing)?(?:\s+(?:how|what))?|what\s+is|how\s+(?:does|do|is)"
    r")\s+",
    re.I,
)
_TOPIC_TAIL = re.compile(
    r"\s+và\s+cách\s+(?:nó|chúng)\s+(?:vận hành|hoạt động).*$|"
    r"\s+and\s+how\s+(?:it|they)\s+works?.*$",
    re.I,
)


def topic_query(text: str) -> str:
    line = (text or "").strip().split("\n")[0]
    line = _TOPIC_PREFIX.sub("", line)
    line = _TOPIC_TAIL.sub("", line)
    return re.sub(r"\s+", " ", line).strip(" .:?！？")


def is_knowledge_topic(text: str) -> bool:
    """True when the paste is a topic request, not an article or five authored beats."""
    blob = (text or "").strip()
    if not blob or looks_like_url(blob):
        return False
    paras = [p for p in re.split(r"\n\s*\n", blob) if p.strip()]
    if len(paras) == 5 and all(len(p.split()) >= 8 for p in paras):
        return False
    if _TOPIC_PREFIX.search(blob) or _TOPIC_TAIL.search(blob):
        return True
    words = blob.split()
    sentences = [p for p in re.split(r"(?<=[.!?…])\s+", blob) if p.strip()]
    return len(words) <= 40 and len(sentences) <= 3


def _keep_short_fence(match: re.Match) -> str:
    body = match.group(1) or ""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if 1 <= len(lines) <= 3 and all(len(ln) < 140 for ln in lines):
        return " " + " ".join(lines) + " "
    return " "


def markdown_to_spoken(md: str) -> str:
    text = md or ""
    text = re.sub(r"```[^\n]*\n(.*?)```", _keep_short_fence, text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\[[ xX]\]\s+", "", text, flags=re.M)
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"[\U0001F300-\U0001FAFF]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:12000]


_SKIP_README_HEAD = re.compile(
    r"special thanks|特别感谢|another open-source|作者的另一个|gallery|作品展示|"
    r"license|许可证|feedback|反馈|star history|sponsor|screenshot|界面预览",
    re.I,
)
_KEEP_README_HEAD = re.compile(
    r"feature|功能|requirement|配置|quick start|快速开始|install|部署|faq|"
    r"common question|常见问题|how it works|overview|介绍",
    re.I,
)
_README_CHROME = re.compile(
    r"\b(English|简体中文|日本語|Releases|Issues|Screenshots|WebUI|API)\b",
    re.I,
)


def _readme_without_skipped(md: str) -> str:
    parts: list[str] = []
    for part in re.split(r"(?=^##\s+)", md or "", flags=re.M):
        head = part.split("\n", 1)[0]
        if _SKIP_README_HEAD.search(head):
            continue
        parts.append(part)
    return "\n".join(parts)


def _readme_section(md: str, pattern: str) -> str:
    for part in re.split(r"(?=^##\s+)", md or "", flags=re.M):
        head = part.split("\n", 1)[0]
        if re.search(pattern, head, flags=re.I) and not _SKIP_README_HEAD.search(head):
            return part
    return ""


def _trim_words(text: str, limit: int) -> str:
    words = [w for w in text.split() if w]
    return " ".join(words[:limit]).strip()


_README_NOISE = re.compile(
    r"\b(item|minimum|recommended|keys? scripts|model providers|english|简体中文|日本語)\b",
    re.I,
)


def _first_heading(md: str) -> str:
    match = re.search(r"^#\s+(.+)$", md or "", flags=re.M)
    if not match:
        return ""
    return _README_CHROME.sub(" ", markdown_to_spoken(match.group(1))).strip()


def _drop_title(text: str, title: str) -> str:
    blob = (text or "").strip()
    if title:
        blob = re.sub(rf"^{re.escape(title)}\b[\s:—,-]*", "", blob, flags=re.I).strip()
    return blob


def _spoken_bit(md: str, sentences: int, words: int) -> str:
    blob = _README_CHROME.sub(" ", markdown_to_spoken(md or ""))
    blob = _README_NOISE.sub(" ", blob)
    blob = re.sub(
        r"^(Features|Creation Workflows|System Requirements|Quick Start Paths?)\b[:\s]*",
        "",
        blob,
        flags=re.I,
    )
    blob = re.sub(r"-{2,}", " ", blob)
    blob = re.sub(r"\s+", " ", blob).replace("**", "").strip()
    parts = [p.strip(" -") for p in re.split(r"(?<=[.!?])\s+", blob) if p.strip()]
    kept: list[str] = []
    for part in parts:
        if len(part.split()) < 5 and not re.search(r"/[A-Za-z][\w-]+", part):
            continue
        if _README_NOISE.search(part):
            continue
        if not re.search(r"[.!?]$", part):
            part = part.rstrip(",;:") + "."
        kept.append(part)
        if len(kept) >= sentences:
            break
    if kept:
        return _trim_words(" ".join(kept), words)
    return _trim_words(blob, words)


_README_NOTE_HEADS = (
    r"why|exist|problem|purpose|about",
    r"feature|how it works|workflow|overview|reference|engineering|skills",
    r"install|quick start|getting started|setup|usage|installation",
    r"whatsapp|waha|agent|crm|sales|mcp|architecture|self-host",
)


def github_readme_notes(md: str, *, name: str = "", description: str = "") -> str:
    """Fact notes from a README for ChatGPT. Not a video-factory template."""
    raw = md or ""
    title = (name or "").strip() or _first_heading(raw)
    desc = _drop_title((description or "").strip().rstrip("."), title)
    desc = re.sub(r"[\u4e00-\u9fff]+", " ", desc)
    desc = re.sub(r"[，。、；：]", " ", desc)
    desc = re.sub(r"\s+", " ", desc).strip(" .")
    chunks: list[str] = []
    lead = " ".join(bit for bit in (title, desc) if bit).strip()
    if lead:
        chunks.append(lead.rstrip(".") + ".")
    intro_md = re.split(r"(?=^##\s+)", raw, flags=re.M)[0]
    intro_md = re.sub(r"^#\s+.*$", "", intro_md, count=1, flags=re.M)
    intro = _spoken_bit(intro_md, 5, 110)
    if intro and (not chunks or intro.lower() not in chunks[0].lower()):
        chunks.append(intro)
    seen: set[str] = set()
    for pattern in _README_NOTE_HEADS:
        sec = _readme_section(raw, pattern)
        key = (sec[:80] if sec else "").lower()
        if not sec or key in seen:
            continue
        seen.add(key)
        bit = _spoken_bit(sec, 10, 140)
        if bit:
            chunks.append(bit)
    blob = "\n\n".join(chunks).strip()
    if len(blob.split()) < 80:
        rest = _trim_words(markdown_to_spoken(_readme_without_skipped(raw)), 220)
        if rest and rest.lower() not in blob.lower():
            blob = (blob + "\n\n" + rest).strip()
    return re.sub(r"[ \t]+", " ", blob).strip()[:8000]


def github_project_notes(
    readme: str,
    *,
    name: str = "",
    description: str = "",
    topics: list[str] | None = None,
    extras: list[str] | None = None,
    homepage_text: str = "",
) -> str:
    """Merge README, repo meta, extra docs, and homepage copy for ChatGPT."""
    chunks: list[str] = []
    tags = [t.strip() for t in (topics or []) if t.strip()]
    if tags:
        chunks.append("Topics: " + ", ".join(tags[:12]) + ".")
    home = re.sub(r"\s+", " ", (homepage_text or "").strip())
    if len(home.split()) >= 20:
        chunks.append(_trim_words(home, 160))
    for extra in extras or []:
        bit = github_readme_notes(extra, name=name)
        if bit and bit.lower() not in " ".join(chunks).lower():
            chunks.append(bit)
    core = github_readme_notes(readme, name=name, description=description)
    blob = "\n\n".join(part for part in (*chunks, core) if part).strip()
    return re.sub(r"[ \t]+", " ", blob).strip()[:12000]


def knowledge_spoken_from_notes(extract: str, *, name: str = "") -> str:
    """Five spoken beats from README notes. Does not invent a short-video factory."""
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", extract or "") if p.strip()]
    if not paras:
        title = (name or "This project").strip()
        paras = [f"{title} is a software project. Read the README, then install and try the main command."]
    sentences: list[str] = []
    for para in paras:
        bits = [p.strip(" -") for p in re.split(r"(?<=[.!?])\s+", para) if p.strip()]
        sentences.extend(bits or [para])
    if len(sentences) < 5:
        sentences.extend([sentences[-1]] * (5 - len(sentences)))
    n = len(sentences)
    cuts = [0, max(1, n // 5), max(2, (2 * n) // 5), max(3, (3 * n) // 5), max(4, (4 * n) // 5), n]
    beats = [" ".join(sentences[cuts[i] : cuts[i + 1]]).strip() for i in range(5)]
    title = (name or "").strip()
    if title and title.lower() not in beats[0].lower():
        beats[0] = f"{title}. {beats[0]}"
    spoken = "\n\n".join(beats)
    return re.sub(r"[ \t]+", " ", spoken).strip()[:4000]


def knowledge_spoken_from_readme(md: str, *, name: str = "", description: str = "") -> str:
    """Five tutorial beats from the README itself. Fallback when ChatGPT is missing."""
    notes = github_readme_notes(md, name=name, description=description)
    return knowledge_spoken_from_notes(notes, name=name or _first_heading(md))


_BIO_NOISE = re.compile(
    r"chữ hán|tước hiệu|phần lớn tài liệu|chú thích|xem thêm|tham khảo|"
    r"là con của|cháu nội|mẹ nuôi|cáo cấp|công chúa biết|tên húy|niên hiệu|"
    r"sửa đổi|external links|disambiguation|có thể đề cập",
    flags=re.I,
)


def _wiki_sentences(extract: str) -> list[str]:
    text = _scrub_wiki_prose(extract)
    parts = re.split(r"(?<=[.!?…])\s+|\n+", text)
    out: list[str] = []
    for part in parts:
        part = part.strip(" ,;:-")
        if len(part.split()) < 5:
            continue
        if _BIO_NOISE.search(part):
            continue
        if re.search(r"^(see also|tham khảo|chú thích|external links)\b", part, flags=re.I):
            continue
        out.append(part)
    return out[:80]


def _scrub_wiki_prose(text: str) -> str:
    blob = text or ""
    blob = re.sub(r"\[[^\]]+\]", " ", blob)
    for _ in range(8):
        nxt = re.sub(
            r"\([^()]*(?:[\u2E80-\u9FFF]|chữ hán|tiếng anh|english|latin|ipa|pinyin)[^()]*\)",
            " ",
            blob,
            flags=re.I,
        )
        if nxt == blob:
            break
        blob = nxt
    blob = re.sub(r"[\u2E80-\u9FFF]+", " ", blob)
    blob = re.sub(r"chữ hán\s*:", " ", blob, flags=re.I)
    blob = re.sub(r"tước hiệu là [^,.]{0,80}", " ", blob, flags=re.I)
    blob = re.sub(
        r"\b(\d{3,4})\?\s*[-–]\s*\d{1,2} tháng \d{1,2} năm (\d{3,4})",
        r"sinh khoảng \1, mất năm \2",
        blob,
    )
    blob = re.sub(r"trong kinh tế vĩ mô,\s*", "", blob, flags=re.I)
    blob = re.sub(r"in macroeconomics,\s*", "", blob, flags=re.I)
    blob = re.sub(r"\(\s*\)", " ", blob)
    blob = re.sub(r"\s+([,;:])", r"\1", blob)
    return re.sub(r"\s+", " ", blob).strip(" ,;:-")


def _spoken_clause(text: str, limit: int = 24) -> str:
    blob = _scrub_wiki_prose(text)
    if not blob or _BIO_NOISE.search(blob):
        return ""
    role = re.search(r"là (?:một )?(?:nhà|danh tướng|tướng) [^.]{6,70}", blob, flags=re.I)
    if role and re.search(r"[\u2E80-\u9FFF]|tên thật|sinh khoảng", blob, flags=re.I):
        head = re.split(r"[,;]", blob, maxsplit=1)[0].strip()
        if 2 <= len(head.split()) <= 8:
            blob = f"{head} {role.group(0).rstrip(',.;')}"
    words = blob.split()
    if len(words) > limit:
        chosen = ""
        for sep in (", ", " và ", " hoặc ", "; "):
            head = blob.split(sep, 1)[0].strip()
            if 8 <= len(head.split()) <= limit:
                chosen = head
                break
        if not chosen:
            chosen = " ".join(words[:limit])
        blob = chosen
    blob = re.sub(r"\s+(và|hoặc|của|theo|so với|các|một|sự|and|or|the|of)$", "", blob, flags=re.I).strip()
    if len(blob.split()) < 6:
        return ""
    if blob[-1:] not in ".!?":
        blob += "."
    return blob


_EXPLAINER_PACKS: tuple[tuple[str, dict[str, dict[str, str]]], ...] = (
    (
        r"lạm phát|\binflation\b",
        {
            "vi": {
                "hook": "Cùng một tờ tiền, mỗi năm mua được ít hơn.",
                "conflict": "Lương có thể tăng mà sức mua vẫn giảm. Tiền trong túi đang bị bào.",
                "rising": "Nó chạy khi cầu vượt cung, chi phí đội, hoặc lượng tiền tăng nhanh hơn hàng hóa.",
                "twist": "Một cơn sốt xăng chưa phải lạm phát. Phải nhìn cả rổ hàng ở siêu thị.",
                "ending": "Đo bằng chỉ số giá theo thời gian. Ngân hàng trung ương hãm cầu bằng lãi suất.",
            },
            "en": {
                "hook": "The same bill buys less every year.",
                "conflict": "Wages can rise while purchasing power still falls.",
                "rising": "It runs when demand outruns supply, costs jump, or money grows faster than goods.",
                "twist": "A spike in gas is not inflation. Watch the whole grocery basket.",
                "ending": "Measure it with a price index over time. Central banks slow demand with rates.",
            },
        },
    ),
    (
        r"trần hưng đạo|hưng đạo vương|trần quốc tuấn",
        {
            "vi": {
                "hook": "Người ta gọi ông Trần Hưng Đạo. Tên thật Trần Quốc Tuấn, tướng nhà Trần, sinh khoảng 1228.",
                "conflict": "Ba lần quân Nguyên Mông kéo vào Đại Việt. Cả nước đứng trước mất còn.",
                "rising": "Ông không thắng bằng hô hào. Ông thắng bằng trận địa và thủy quân.",
                "twist": "Bạch Đằng: cọc gỗ đóng ngầm dưới sông. Thủy triều rút, thuyền giặc mắc cạn. Đó là kế, không phải phép màu.",
                "ending": "Đền Kiếp Bạc còn thờ ông. Nhớ trận Bạch Đằng: cọc gỗ và thủy triều.",
            },
            "en": {
                "hook": "They called him Tran Hung Dao. Born Tran Quoc Tuan, a Tran-dynasty general around 1228.",
                "conflict": "Mongol armies hit Dai Viet three times. The country could have vanished.",
                "rising": "He did not win by slogans. He won with river war and field works.",
                "twist": "Bach Dang: hidden stakes. When the tide fell, the fleet sat on wood. A trap, not magic.",
                "ending": "Remember him because the country survived. Kiep Bac temple is still there.",
            },
        },
    ),
    (
        r"hùng vương|vua hùng|các vua hùng|đền hùng|lạc long|âu cơ",
        {
            "vi": {
                "hook": "Âu Cơ đẻ trăm trứng. Một nửa theo cha xuống biển, một nửa theo mẹ lên núi. Đó là chuyện mở nước Văn Lang.",
                "conflict": "Các bộ lạc Lạc Việt còn rời rạc. Cần một dòng vua để giữ đất, giữ ruộng, giữ lễ.",
                "rising": "Các vua Hùng đóng đô ở Phong Châu. Mười tám đời cùng xưng một hiệu, truyền ruộng và hội.",
                "twist": "Hùng Vương không phải một người. Là cả một dòng. Sử đời sau mới chép thành quốc tổ.",
                "ending": "Giỗ Tổ mùng mười tháng ba. Đền Hùng ở Phú Thọ còn đó. Nhớ trứng, nhớ rừng biển, nhớ nước Văn Lang.",
            },
            "en": {
                "hook": "Au Co laid a hundred eggs. Half followed their father to the sea, half followed their mother to the mountains.",
                "conflict": "The Lac Viet clans were scattered. They needed a line of kings to hold Van Lang.",
                "rising": "The Hung kings sat at Phong Chau. Eighteen reigns shared one title, fields, and rites.",
                "twist": "Hung Vuong is not one man. Later histories named the whole line the national ancestors.",
                "ending": "The Hung temple in Phu Tho still stands. Remember the eggs, the mountains, and Van Lang.",
            },
        },
    ),
)


def _explainer_pack(title: str, language: str, extract: str = "") -> dict[str, str]:
    lang = "vi" if (language or "vi").lower().startswith("vi") else "en"
    blob = f"{title or ''}\n{(extract or '')[:240]}"
    for pattern, pack in _EXPLAINER_PACKS:
        if re.search(pattern, blob, flags=re.I):
            return pack.get(lang) or pack.get("en") or {}
    return {}


def _fresh_clause(sents: list[str], used: set[str], pattern: str | None = None, limit: int = 22) -> str:
    candidates = sents
    if pattern:
        matched = [sent for sent in sents if re.search(pattern, sent, flags=re.I)]
        if matched:
            candidates = matched + [sent for sent in sents if sent not in matched]
    for sent in candidates:
        key = sent[:48]
        if key in used:
            continue
        clause = _spoken_clause(sent, limit)
        if not clause:
            continue
        used.add(key)
        return clause
    return ""


def _looks_like_person(title: str, extract: str) -> bool:
    blob = f"{title}\n{(extract or '')[:900]}"
    return bool(
        re.search(
            r"sinh năm|sinh ngày|sinh tại|sinh ở|tên thật|tước hiệu|nhà quân sự|nhà chính trị|"
            r"tôn thất|danh tướng|tướng quân|anh hùng dân tộc|công thần|"
            r"was born|national hero|military commander|chỉ huy quân|xâm lược|"
            r"\(\d{3,4}\s*[-–]|\d{3,4}\s*\?\s*[-–]|mất năm \d{3,4}",
            blob,
            flags=re.I,
        )
    )


def _gather_beat(
    sents: list[str],
    used: set[str],
    pattern: str | None,
    *,
    n: int = 2,
    limit: int = 32,
    min_words: int = 24,
) -> str:
    bits: list[str] = []
    for i in range(n):
        clause = _fresh_clause(sents, used, pattern if i == 0 else None, limit)
        if not clause:
            break
        bits.append(clause)
    body = " ".join(bits).strip()
    while len(body.split()) < min_words:
        extra = _fresh_clause(sents, used, None, limit)
        if not extra:
            break
        body = f"{body} {extra}".strip()
    return body


def _knowledge_frames(name: str, vi: bool, person: bool) -> dict[str, str]:
    if person and vi:
        return {
            "hook": f"{name} bước vào sử bằng việc đã xảy ra, bằng năm tháng và trận.",
            "conflict": "Thế nước lúc đó không yên. Có giặc, có mất đất, có người phải đánh.",
            "rising": "Chuyện nằm ở cách họ làm, từng việc một, không ở tước hiệu.",
            "twist": "Phần hay thường là kế, là trận, là điều sử chép mà người ta hay bỏ.",
            "ending": f"Còn lại đền, đất, và chuyện kể về {name}.",
        }
    if person:
        return {
            "hook": f"{name} enters the record through deeds, dates, and a fight.",
            "conflict": "The country was at risk. There was an invasion to meet.",
            "rising": "The story is what they did, step by step, not the title.",
            "twist": "The part people skip is usually the trick or the battle plan.",
            "ending": f"What remains is a place, a record, and the story of {name}.",
        }
    if vi:
        return {
            "hook": f"{name} là một cơ chế, không phải tin đồn.",
            "conflict": f"Hệ quả của {name} đụng vào đời sống thường ngày.",
            "rising": f"{name} chạy qua nguyên nhân, chuỗi hệ quả, và cách người ta đo nó.",
            "twist": f"Một ví dụ lẻ không đủ để nói đã hiểu {name}.",
            "ending": f"Đo {name} theo cả hệ thống, không theo cảm giác một sự kiện.",
        }
    return {
        "hook": f"{name} is a mechanism, not a rumor.",
        "conflict": f"{name} changes everyday outcomes, not just a definition.",
        "rising": f"{name} has causes, a chain of effects, and a way to measure it.",
        "twist": f"One anecdote is not a model of {name}.",
        "ending": f"Measure {name} as a system, not a one-off shock.",
    }


def knowledge_spoken_from_wiki(title: str, extract: str, language: str = "vi") -> str:
    """Five spoken beats that fill a short (~90s), not a one-line encyclopedia lead."""
    sents = _wiki_sentences(extract)
    vi = (language or "vi").lower().startswith("vi")
    name = (title or "").strip() or ("chủ đề này" if vi else "this topic")
    pack = _explainer_pack(name, language, extract)
    person = _looks_like_person(name, extract)
    frames = pack or _knowledge_frames(name, vi, person)
    used: set[str] = set()
    if person:
        patterns = {
            "hook": r"sinh|tên thật|quê|trăm trứng|âu cơ|lạc long|văn lang|was born|childhood",
            "conflict": r"xâm lược|mông cổ|nguyên|giặc|chiến tranh|bộ lạc|invade|war |mongol",
            "rising": r"trận|chỉ huy|đánh|chiến|thủy quân|phong châu|mười tám|18 đời|battle|command",
            "twist": r"bạch đằng|cọc|thủy triều|kế|không phải một|dòng vua|stake|tide|trick",
            "ending": r"đền|di sản|suy tôn|kiếp bạc|giỗ tổ|phú thọ|mất năm|temple|legacy|died",
        }
        extra_n, extra_min = (1, 0) if pack else (2, 22)
    else:
        patterns = {
            "hook": r"là sự|is the |tăng mức giá|mất giá trị",
            "conflict": r"sức mua|tác động|hệ quả|chi phí|effect",
            "rising": r"cầu|cung|nguyên nhân|lãi suất|ngân hàng|cause|when ",
            "twist": r"ngược lại|không phải|giảm phát|however|not ",
            "ending": r"chỉ số|đo|cpi|trung ương|measure",
        }
        extra_n, extra_min = (2, 24)
    beats = []
    for key in ("hook", "conflict", "rising", "twist", "ending"):
        body = _gather_beat(sents, used, patterns[key], n=extra_n, min_words=extra_min)
        frame = frames.get(key) or ""
        if pack:
            line = frame
            if body and len(frame.split()) < 14 and body.lower()[:24] not in line.lower():
                line = f"{line} {body}".strip()
        elif len(body.split()) >= 16:
            line = body
        else:
            line = " ".join(part for part in (frame, body) if part).strip()
        beats.append(_trim_words(re.sub(r"\s+", " ", line), 70))
    return "\n\n".join(beats)[:8000]


def extract_markdown_images(md: str, base: str = "") -> list[str]:
    urls: list[str] = []
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+)\)", md or ""):
        raw = match.group(1).strip().split()[0]
        if raw.startswith("http") and not raw.lower().endswith(".svg"):
            urls.append(raw)
        elif base and not raw.startswith("data:"):
            joined = urljoin(base.rstrip("/") + "/", raw.lstrip("./"))
            if not joined.lower().endswith(".svg"):
                urls.append(joined)
    return unique_image_urls(urls)


def _headers(referer: str | None = None, *, wiki: bool = False) -> dict[str, str]:
    headers = {
        "User-Agent": _WIKI_UA if wiki else _UA,
        "Accept": "text/html,image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def _normalize_image_url(raw: str, base: str) -> str | None:
    raw = html_lib.unescape(raw.strip().strip("'\""))
    if not raw or raw.startswith("data:"):
        return None
    if raw.startswith("//"):
        raw = "https:" + raw
    joined = urljoin(base, raw)
    parsed = urlparse(joined)
    if parsed.scheme not in {"http", "https"}:
        return None
    path = parsed.path.lower()
    if not any(path.endswith(ext) for ext in _IMG_EXT) and "image" not in path and "photo" not in path:
        if "vnecdn.net" in parsed.netloc or "vcdn" in parsed.netloc:
            pass
        else:
            return None
    host = parsed.netloc.lower()
    blob = f"{host}{path}"
    if any(bit in blob for bit in _SKIP):
        return None
    if any(bit in host for bit in _SKIP_HOST):
        return None
    clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))
    return clean


def unique_image_urls(urls: list[str], *, limit: int = 24) -> list[str]:
    by_path: dict[str, str] = {}
    order: list[str] = []
    for url in urls:
        parsed = urlparse(url)
        key = f"{parsed.netloc}{parsed.path}".lower()
        prev = by_path.get(key)
        if prev is None:
            by_path[key] = url
            order.append(key)
        elif parsed.query and len(parsed.query) > len(urlparse(prev).query):
            by_path[key] = url
    return [by_path[key] for key in order[:limit]]


def _urls_from_srcset(srcset: str, base: str) -> list[str]:
    found: list[str] = []
    for part in _SRCSET_SPLIT.split(srcset):
        token = part.strip().split()[0] if part.strip() else ""
        url = _normalize_image_url(token, base)
        if url:
            found.append(url)
    return found


def extract_image_urls(html: str, page_url: str) -> list[str]:
    found: list[str] = []
    for pattern in (
        r'<meta[^>]+(?:property|name)="(?:og:image|twitter:image)"[^>]+content="([^"]+)"',
        r'<meta[^>]+content="([^"]+)"[^>]+(?:property|name)="(?:og:image|twitter:image)"',
        r'<img[^>]+(?:src|data-src|data-original|data-lazy-src)="([^"]+)"',
        r'https://[^"\s<>]+\.(?:jpg|jpeg|png|webp)',
    ):
        for match in re.findall(pattern, html, flags=re.I):
            url = _normalize_image_url(match, page_url)
            if url:
                found.append(url)
    for srcset in re.findall(r'(?:srcset|data-srcset)="([^"]+)"', html, flags=re.I):
        found.extend(_urls_from_srcset(srcset, page_url))
    return unique_image_urls(found, limit=12)


_JUNK_RE = re.compile(
    r"localStorage|document\.|function\s*\(|navigator\.|stylesheet|loadCSS|"
    r"serviceWorker|querySelector|fontFormat|webfont|decodeURIComponent|"
    r"ttf\\?:|onloadcssdefined",
    re.I,
)
_GLUED_RELATED = re.compile(
    r"(?:^|[\s,])([A-ZÀ-ỴĐ][\wÀ-ỹ]*(?:\s+[A-ZÀ-ỴĐ][\wÀ-ỹ]*){0,2})\s*[-–]\s+[A-ZÀ-ỴĐ][^,]{8,80},",
)
_SKIP_PHRASE = (
    "cookie",
    "trở lại pháp luật",
    "nguồn ưu tiên",
    "subscribe",
    "đăng nhập",
    "bình luận",
)


def is_spoken_prose(text: str, language: str = "") -> bool:
    blob = html_lib.unescape(re.sub(r"\s+", " ", text or "")).strip()
    if len(blob) < 12:
        return False
    if _JUNK_RE.search(blob):
        return False
    lowered = blob.lower()
    if any(token in lowered for token in _SKIP_PHRASE):
        return False
    if blob.count("{") + blob.count("}") >= 2:
        return False
    if blob.count(";") >= 5:
        return False
    letters = sum(ch.isalpha() for ch in blob)
    if letters < 20 or letters / max(1, len(blob)) < 0.42:
        return False
    lang = (language or "").lower()
    if lang.startswith("vi") and len(blob.split()) > 8:
        if not re.search(
            r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
            blob,
            flags=re.I,
        ):
            return False
    return True


_START_CITY = re.compile(
    r"^(Đà Nẵng|Hà Nội|Hải Phòng|Cần Thơ|Huế|Sài Gòn|TP\.?\s*HCM|Nha Trang|Quảng Ninh|Đồng Nai)\b",
    re.I,
)


def strip_glued_related(text: str) -> str:
    cleaned = _GLUED_RELATED.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def strip_photo_credit(text: str) -> str:
    cleaned = re.sub(r"\s*(?:Ảnh|Photo|Nguồn)\s*:\s*[A-Za-z0-9 .,&/-]{2,40}", " ", text or "", flags=re.I)
    return re.sub(r"\s+", " ", cleaned).strip()


_BYLINE_TAIL = re.compile(
    r"\s+[A-ZÀ-ỴĐ][\w.]*(?:\s+[A-ZÀ-ỴĐ][\w.]*){0,2}\s*\(\s*Theo\b[^)]*\)\s*$",
    flags=re.I,
)


def strip_byline(text: str) -> str:
    cleaned = _BYLINE_TAIL.sub("", text or "")
    return re.sub(r"\s+", " ", cleaned).strip()


def strip_related_kicker(text: str, title: str) -> str:
    blob = strip_glued_related(text)
    match = _START_CITY.match(blob)
    if not match:
        return blob
    city = match.group(1)
    if city.lower() in (title or "").lower():
        return blob
    if _overlaps_title(title, blob[:80]):
        return blob
    comma = blob.find(",")
    if 10 < comma < 100:
        return blob[comma + 1 :].strip()
    return blob


def scrub_brief_vo(text: str, language: str = "") -> str:
    blob = html_lib.unescape(re.sub(r"\s+", " ", text or "")).strip()
    blob = strip_byline(strip_photo_credit(strip_glued_related(blob)))
    if not blob:
        return blob
    if is_spoken_prose(blob, language):
        return blob
    cut = _JUNK_RE.search(blob)
    if cut:
        blob = blob[: cut.start()].strip(" -–,:;\"'")
    parts = re.split(r"(?<=[.!?])\s+", blob)
    kept = [part.strip() for part in parts if is_spoken_prose(part.strip(), language)]
    if kept:
        return " ".join(kept)
    return blob if blob and not _JUNK_RE.search(blob) else ""


def _strip_chrome(html: str) -> str:
    html = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style\b[^>]*>.*?</style>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return html


def _article_fragment(html: str) -> str:
    for pattern in (
        r'<article[^>]*class="[^"]*fck_detail[^"]*"[^>]*>(.*?)</article>',
        r'<div[^>]*class="[^"]*fck_detail[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*itemprop="articleBody"[^>]*>(.*?)</div>',
    ):
        match = re.search(pattern, html, flags=re.I | re.S)
        if match and len(re.findall(r"<p", match.group(1), flags=re.I)) >= 1:
            return match.group(1)
    return html


def _overlaps_title(title: str, other: str) -> bool:
    title_words = {w for w in re.findall(r"\w{4,}", title.lower()) if w not in {"với", "và", "của", "this", "that"}}
    other_words = set(re.findall(r"\w{4,}", other.lower()))
    return len(title_words & other_words) >= 2


def extract_article_text(html: str, fallback_title: str = "") -> str:
    html = _strip_chrome(html)
    title = fallback_title
    match = re.search(r"<title>([^<]+)</title>", html, flags=re.I)
    if match:
        title = html_lib.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
        title = re.sub(r"\s*[-|]\s*Báo VnExpress.*$", "", title, flags=re.I).strip()
        if title and title[-1] not in ".!?":
            title = title + "."
    desc = ""
    match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html, flags=re.I)
    if match:
        desc = html_lib.unescape(match.group(1)).strip()
        if title and not _overlaps_title(title, desc):
            desc = ""
    fragment = _article_fragment(html)
    paragraphs: list[str] = []
    for raw in re.findall(r"<p[^>]*>(.*?)</p>", fragment, flags=re.I | re.S):
        text = re.sub(r"<[^>]+>", " ", raw)
        text = strip_byline(strip_photo_credit(strip_related_kicker(html_lib.unescape(re.sub(r"\s+", " ", text)).strip(), title)))
        if not is_spoken_prose(text):
            continue
        paragraphs.append(text)
    body = strip_byline(strip_photo_credit(strip_related_kicker(" ".join(paragraphs[:80]), title)))
    chunks = [part for part in (title, desc, body) if part]
    return "\n\n".join(chunks)[:16000] or title


def extract_title(html: str) -> str:
    match = re.search(r"<title>([^<]+)</title>", html, flags=re.I)
    if not match:
        return ""
    title = html_lib.unescape(re.sub(r"\s+", " ", match.group(1))).strip()
    return re.sub(r"\s*[-|]\s*Báo VnExpress.*$", "", title, flags=re.I).strip()


def brief_search_queries(title: str, text: str = "") -> list[str]:
    """English Commons/Openverse queries from Vietnamese headlines (not Pexels)."""
    lead = f"{title}\n{(text or '')[:400]}"
    queries: list[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        cleaned = re.sub(r"\s+", " ", query).strip()
        key = cleaned.lower()
        if len(cleaned) < 4 or key in seen:
            return
        seen.add(key)
        queries.append(cleaned)

    for pattern, query, wiki in _QUERY_ALIASES:
        blob = title if wiki else lead
        if re.search(pattern, blob, flags=re.I):
            add(query)
    if not queries and title.strip():
        add(title)
    return queries[:8]


def visual_terms_for_beat(vo: str, title: str = "") -> list[str]:
    """Per-beat search terms (MoneyPrinter match-to-script). Wikimedia/Openverse, not Pexels."""
    terms: list[str] = []
    seen: set[str] = set()

    def add(query: str) -> None:
        cleaned = re.sub(r"\s+", " ", query).strip()
        key = cleaned.lower()
        if len(cleaned) < 4 or key in seen:
            return
        seen.add(key)
        terms.append(cleaned)

    for pattern, query in _VISUAL_ALIASES:
        if re.search(pattern, vo, flags=re.I):
            generic = bool(re.search(r"lạm phát|\binflation\b", pattern, flags=re.I))
            if generic:
                continue
            add(query)
    for pattern, query in _VISUAL_ALIASES:
        if re.search(pattern, vo, flags=re.I):
            add(query)
    for pattern, query, _wiki in _QUERY_ALIASES:
        if re.search(pattern, vo, flags=re.I):
            add(query)
    for noun in beat_search_nouns(vo):
        add(noun)
    if not terms:
        for term in brief_search_queries(title, vo):
            add(term)
            if len(terms) >= 4:
                break
    return terms[:4]


_BEAT_STOP = {
    "that", "this", "with", "from", "they", "them", "have", "been", "were", "when",
    "what", "your", "their", "about", "after", "before", "into", "then", "than",
    "một", "những", "các", "của", "trong", "với", "và", "cho", "khi", "như",
    "không", "được", "này", "đó", "còn", "đã", "là", "ở", "từ", "đến", "theo",
    "người", "việc", "rằng", "nhưng", "cũng", "rất", "để", "hay", "nên",
    "khách", "chuyện",
}


def beat_search_nouns(vo: str) -> list[str]:
    """Proper names and content words from this beat's VO — not the job title."""
    tokens = re.findall(r"[A-ZÀ-Ỹ][\wÀ-ỹ]{2,}|[\wÀ-ỹ]{5,}", vo or "")
    out: list[str] = []
    seen: set[str] = set()
    for raw in tokens:
        key = raw.lower()
        if key in _BEAT_STOP or key in seen:
            continue
        seen.add(key)
        out.append(raw)
        if len(out) >= 4:
            break
    return out


STILL_OVERLAP = 0.15


def overlap_score(caption: str, vo: str) -> float:
    left = set(re.findall(r"\w{4,}", (caption or "").lower()))
    right = set(re.findall(r"\w{4,}", (vo or "").lower()))
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def extract_image_captions(html: str, page_url: str) -> dict[str, str]:
    captions: dict[str, str] = {}
    for tag in re.findall(r"<img\b[^>]*>", html, flags=re.I):
        src_match = re.search(r'(?:src|data-src|data-original)="([^"]+)"', tag, flags=re.I)
        alt_match = re.search(r'alt="([^"]*)"', tag, flags=re.I)
        if not src_match:
            continue
        url = _normalize_image_url(src_match.group(1), page_url)
        alt = html_lib.unescape(alt_match.group(1)).strip() if alt_match else ""
        if url and alt:
            captions[url] = alt
    return captions


def wikipedia_titles(title: str, text: str = "") -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pattern, _query, wiki in _QUERY_ALIASES:
        if not wiki or not re.search(pattern, title, flags=re.I):
            continue
        key = wiki.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(wiki)
    return found[:4]


def _skip_wiki_file(title: str, mime: str | None) -> bool:
    blob = f"{title} {mime or ''}".lower()
    if mime and not mime.startswith("image/"):
        return True
    if mime in {"image/svg+xml", "image/gif"}:
        return True
    return any(bit in blob for bit in _SKIP_WIKI_FILE)


async def fetch_article(url: str) -> ArticlePage:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=_headers()) as client:
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
    title = extract_title(html)
    urls = extract_image_urls(html, url)
    return ArticlePage(
        url=url,
        title=title,
        text=extract_article_text(html, title),
        image_urls=urls,
        image_captions=extract_image_captions(html, url),
    )


_GITHUB_DOC_FILES = (
    "docs/README.md",
    "docs/index.md",
    "docs/getting-started.md",
    "docs/architecture.md",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "AGENTS.md",
    "INSTALL.md",
)


async def _github_raw_text(
    client: httpx.AsyncClient, owner: str, repo: str, refs: tuple[str, ...], path: str
) -> tuple[str, str]:
    for ref in refs:
        try:
            response = await client.get(f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}")
            if response.status_code < 400 and (response.text or "").strip():
                return response.text, ref
        except Exception:
            continue
    return "", ""


async def fetch_github_project(url: str) -> ArticlePage:
    slug = github_repo_slug(url)
    if not slug:
        raise ValueError("not a GitHub repository URL")
    owner, repo = slug
    headers = {"User-Agent": _WIKI_UA, "Accept": "application/vnd.github+json"}
    description = ""
    topics: list[str] = []
    homepage = ""
    branch = "main"
    display = f"{owner}/{repo}"
    readme = ""
    extras: list[str] = []
    homepage_text = ""
    raw_base = ""
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True, headers=headers) as client:
        try:
            response = await client.get(f"https://api.github.com/repos/{owner}/{repo}")
            if response.status_code < 400:
                data = response.json()
                description = (data.get("description") or "").strip()
                topics = [str(t) for t in (data.get("topics") or []) if t]
                homepage = (data.get("homepage") or "").strip()
                branch = data.get("default_branch") or "main"
                display = data.get("full_name") or display
        except Exception:
            pass
        refs = (branch, "main", "master")
        filenames = ("README-en.md", "README.en.md", "README_EN.md", "README.md", "readme.md")
        for filename in filenames:
            readme, used_ref = await _github_raw_text(client, owner, repo, refs, filename)
            if readme:
                raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/{used_ref}/"
                break
        extra_paths = list(_GITHUB_DOC_FILES)
        try:
            listing = await client.get(f"https://api.github.com/repos/{owner}/{repo}/contents/docs")
            if listing.status_code < 400:
                payload = listing.json()
                for item in payload if isinstance(payload, list) else []:
                    name = str(item.get("name") or "")
                    if name.lower().endswith((".md", ".txt")) and item.get("type") == "file":
                        extra_paths.append(f"docs/{name}")
        except Exception:
            pass
        seen_docs: set[str] = set()
        for path in extra_paths:
            key = path.lower()
            if key in seen_docs:
                continue
            seen_docs.add(key)
            extra, _ref = await _github_raw_text(client, owner, repo, refs, path)
            if extra and extra != readme:
                extras.append(extra)
            if len(extras) >= 4:
                break
        if homepage.startswith("http") and "github.com" not in homepage.lower():
            try:
                page = await client.get(homepage, headers=_headers())
                if page.status_code < 400 and (page.text or "").strip():
                    homepage_text = extract_article_text(page.text, repo)
            except Exception:
                homepage_text = ""
    title = (description or display).rstrip(".") + "."
    notes = github_project_notes(
        readme,
        name=repo,
        description=description,
        topics=topics,
        extras=extras,
        homepage_text=homepage_text,
    )
    text = (notes or f"{display}. {description}".strip())[:12000]
    images = [
        url
        for url in extract_markdown_images(readme, raw_base)
        if "opengraph.githubassets.com" not in url
    ]
    extra_imgs, _src = await _fill_broll_urls(
        " ".join(part for part in (repo, description, *topics[:6]) if part),
        f"{description} {' '.join(topics)}",
        len(images),
        6,
    )
    return ArticlePage(
        url=url,
        title=title.rstrip("."),
        text=text,
        image_urls=unique_image_urls([*images, *extra_imgs]),
        image_captions={},
    )


async def _wiki_json(host: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True, headers=_headers(wiki=True)) as client:
        response = await client.get(f"{host.rstrip('/')}/w/api.php", params=params)
        if response.status_code >= 400:
            return {}
        data = response.json()
        return data if isinstance(data, dict) else {}


_RELATED_WIKI: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        r"hùng vương|vua hùng|đền hùng|sự tích vua hùng",
        ("Hùng Vương", "Lạc Long Quân", "Âu Cơ", "Đền Hùng", "Ngày Giỗ Tổ Hùng Vương"),
    ),
    (
        r"trần hưng đạo|hưng đạo vương",
        ("Trần Hưng Đạo", "Trận Bạch Đằng (1288)", "Đền Kiếp Bạc"),
    ),
    (r"lạm phát|\binflation\b", ("Lạm phát", "Chỉ số giá tiêu dùng", "Inflation")),
)


def related_wiki_titles(query: str) -> list[str]:
    blob = (query or "").strip()
    out: list[str] = []
    seen: set[str] = set()
    for pattern, titles in _RELATED_WIKI:
        if not re.search(pattern, blob, flags=re.I):
            continue
        for title in titles:
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(title)
    return out


async def _wiki_page_extract(host: str, hit_title: str) -> ArticlePage | None:
    try:
        page = await _wiki_json(
            host,
            {
                "action": "query",
                "prop": "extracts|info|pageimages",
                "titles": hit_title,
                "explaintext": "1",
                "exsectionformat": "plain",
                "inprop": "url",
                "piprop": "original|thumbnail",
                "pithumbsize": "1280",
                "redirects": "1",
                "format": "json",
                "utf8": "1",
            },
        )
    except Exception:
        return None
    pages = (page.get("query") or {}).get("pages") or {}
    for item in pages.values():
        if item.get("missing") is not None:
            continue
        extract = str(item.get("extract") or "").strip()
        if re.search(r"may refer to|có thể đề cập|disambiguation", extract[:240], flags=re.I):
            continue
        if len(extract.split()) < 20:
            continue
        title = str(item.get("title") or hit_title)
        page_url = str(item.get("fullurl") or f"{host}/wiki/{hit_title.replace(' ', '_')}")
        images: list[str] = []
        original = (item.get("original") or {}).get("source") if isinstance(item.get("original"), dict) else None
        thumb = (item.get("thumbnail") or {}).get("source") if isinstance(item.get("thumbnail"), dict) else None
        for img in (original, thumb):
            if isinstance(img, str) and img.startswith("http"):
                images.append(img)
        return ArticlePage(url=page_url, title=title, text=extract[:8000], image_urls=images)
    return None


async def fetch_knowledge_topic(text: str, language: str = "vi") -> ArticlePage:
    """Turn 'thuyết minh về X' into notes from several encyclopedia pages + CC stills."""
    query = topic_query(text) or (text or "").strip()[:80]
    lang = "vi" if (language or "vi").lower().startswith("vi") else "en"
    hosts = [f"https://{lang}.wikipedia.org", f"https://{'en' if lang == 'vi' else 'vi'}.wikipedia.org"]
    wanted = related_wiki_titles(query)
    images: list[str] = []
    chunks: list[str] = []
    title = query
    page_url = ""
    for host in hosts:
        titles = list(wanted)
        try:
            search = await _wiki_json(
                host,
                {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "srlimit": "3",
                    "format": "json",
                    "utf8": "1",
                },
            )
        except Exception:
            search = {}
        for hit in (search.get("query") or {}).get("search") or []:
            hit_title = str(hit.get("title") or "").strip()
            if hit_title and hit_title not in titles:
                titles.append(hit_title)
        for hit_title in titles[:5]:
            got = await _wiki_page_extract(host, hit_title)
            if not got:
                continue
            if not page_url:
                title = got.title
                page_url = got.url
            chunks.append(f"{got.title}. {got.text}")
            images.extend(got.image_urls)
        if chunks:
            extra_imgs, _src = await _fill_broll_urls(title, " ".join(chunks)[:400], len(images), 6)
            images = unique_image_urls([*images, *extra_imgs])
            break
    extract = "\n\n".join(chunks)[:14000]
    return ArticlePage(
        url=page_url,
        title=title,
        text=extract,
        image_urls=unique_image_urls(images),
        image_captions={},
    )


def prefer_readme_language(text: str, requested: str = "en") -> str:
    req = (requested or "en")[:2]
    if re.search(
        r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]",
        text or "",
        flags=re.I,
    ):
        return "vi" if req in {"vi", "en"} else req
    if req == "vi":
        if re.search(r"[A-Za-z]{12,}", text or ""):
            return "en"
        if re.search(r"[\u4e00-\u9fff]", text or ""):
            return "zh"
    return req or "en"


def conform_photo(src: Path, dest: Path) -> Path:
    """Fit 9:16. Landscape screenshots letterbox instead of cover-cropping off-frame."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.open(src).convert("RGB")
    width, height = img.size
    if width > 0 and height > 0 and width / height >= 1.15:
        fitted = ImageOps.contain(img, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (WIDTH, HEIGHT), (10, 10, 12))
        canvas.paste(fitted, ((WIDTH - fitted.width) // 2, (HEIGHT - fitted.height) // 2))
        canvas.save(dest, "PNG")
        return dest
    ImageOps.fit(img, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS).save(dest, "PNG")
    return dest


async def _download_bytes(url: str, referer: str | None) -> bytes | None:
    try:
        wiki = "wikimedia.org" in url or "wikipedia.org" in url
        async with httpx.AsyncClient(timeout=45.0, follow_redirects=True, headers=_headers(referer, wiki=wiki)) as client:
            response = await client.get(url)
            if response.status_code >= 400:
                return None
            body = response.content
            if len(body) < 8000:
                return None
            if body[:15].lstrip().startswith(b"<!DOCTYPE") or b"<html" in body[:200].lower():
                return None
            return body
    except Exception:
        return None


async def download_photo(url: str, dest: Path, referer: str | None = None) -> Path | None:
    raw = await _download_bytes(url, referer)
    if not raw:
        return None
    tmp = dest.with_suffix(".src")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw)
    try:
        conform_photo(tmp, dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        return None
    tmp.unlink(missing_ok=True)
    return dest


async def search_openverse(query: str, limit: int = 6) -> list[str]:
    q = re.sub(r"\s+", " ", query).strip()[:80]
    if len(q) < 4:
        return []
    params = {"q": q, "page_size": str(max(1, min(limit, 8))), "license": "cc0,by,by-sa"}
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=_headers()) as client:
            response = await client.get("https://api.openverse.org/v1/images/", params=params)
            if response.status_code >= 400:
                return []
            data = response.json()
    except Exception:
        return []
    urls: list[str] = []
    for item in data.get("results") or []:
        url = item.get("url") or item.get("thumbnail")
        if isinstance(url, str) and url.startswith("http"):
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


async def search_wikimedia(query: str, limit: int = 4) -> list[str]:
    q = re.sub(r"\s+", " ", query).strip()[:80]
    if len(q) < 4:
        return []
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": q,
        "gsrnamespace": "6",
        "gsrlimit": str(max(1, min(limit, 8))),
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": "1280",
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=_headers(wiki=True)) as client:
            response = await client.get("https://commons.wikimedia.org/w/api.php", params=params)
            if response.status_code >= 400:
                return []
            data = response.json()
    except Exception:
        return []
    urls: list[str] = []
    pages = (data.get("query") or {}).get("pages") or {}
    for page in pages.values():
        title = str(page.get("title") or "")
        info = (page.get("imageinfo") or [{}])[0]
        mime = info.get("mime") if isinstance(info.get("mime"), str) else None
        if _skip_wiki_file(title, mime):
            continue
        url = info.get("thumburl") or info.get("url")
        if isinstance(url, str) and url.startswith("http"):
            urls.append(url)
        if len(urls) >= limit:
            break
    return urls


async def search_wikipedia_original(title: str) -> list[str]:
    page = title.strip()
    if len(page) < 2:
        return []
    params = {
        "action": "query",
        "format": "json",
        "titles": page,
        "prop": "pageimages",
        "piprop": "original",
    }
    urls: list[str] = []
    for host in ("https://vi.wikipedia.org/w/api.php", "https://en.wikipedia.org/w/api.php"):
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=_headers(wiki=True)) as client:
                response = await client.get(host, params=params)
                if response.status_code >= 400:
                    continue
                data = response.json()
        except Exception:
            continue
        pages = (data.get("query") or {}).get("pages") or {}
        for item in pages.values():
            original = (item.get("original") or {}).get("source")
            if isinstance(original, str) and original.startswith("http"):
                urls.append(original)
        if urls:
            break
    return unique_image_urls(urls, limit=2)


async def _fill_broll_urls(query: str, extra_text: str, have: int, need: int) -> tuple[list[str], list[str]]:
    if have >= need:
        return [], []
    extras: list[str] = []
    sources: list[str] = []
    searches: list[str] = []
    q = re.sub(r"\s+", " ", (query or "")).strip()
    if q:
        searches.append(q)
    for item in brief_search_queries(query, extra_text):
        if item.lower() not in {s.lower() for s in searches}:
            searches.append(item)
    wiki_pages = wikipedia_titles(query, extra_text)
    for page in wiki_pages:
        extras.extend(await search_wikipedia_original(page))
        if extras and "wikipedia" not in sources:
            sources.append("wikipedia")
        if have + len(unique_image_urls(extras)) >= need:
            return extras, sources
    for search in searches:
        extras.extend(await search_wikimedia(search, limit=4))
        if extras and "wikimedia" not in sources:
            sources.append("wikimedia")
        if have + len(unique_image_urls(extras)) >= need:
            return extras, sources
    for search in searches:
        extras.extend(await search_openverse(search, limit=4))
        if extras and "openverse" not in sources:
            sources.append("openverse")
        if have + len(unique_image_urls(extras)) >= need:
            break
    return extras, sources


async def assign_editorial_stills(
    *,
    scenes: list,
    source_url: str | None,
    article_urls: list[str] | None,
    dest_dir: Path,
    title: str = "",
    captions: dict[str, str] | None = None,
) -> tuple[dict[str, Path], str]:
    """One still per beat from article/CC photos. Never Pollinations faces."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    unused = unique_image_urls(list(article_urls or []))
    caps = captions or {}
    out: dict[str, Path] = {}
    tags: list[str] = []
    index = 0
    tried: set[str] = set()

    async def _save(url: str) -> Path | None:
        nonlocal index
        if not url or url in tried:
            return None
        tried.add(url)
        dest = dest_dir / f"src_{index:02d}.png"
        host = urlparse(url).netloc
        referer = source_url if "vnecdn" in host or "vnexpress" in host else None
        path = await download_photo(url, dest, referer=referer)
        if path:
            index += 1
        return path

    async def _candidates(i: int, vo: str) -> list[str]:
        urls: list[str] = []
        if i < 2 and unused:
            urls.append(unused.pop(0))
            if "article" not in tags:
                tags.append("article")
        elif unused:
            scored = sorted(
                unused,
                key=lambda url: overlap_score(caps.get(url, "") + " " + urlparse(url).path, vo),
                reverse=True,
            )
            if scored and overlap_score(caps.get(scored[0], "") + " " + urlparse(scored[0]).path, vo) >= STILL_OVERLAP:
                picked = scored[0]
                unused.remove(picked)
                urls.append(picked)
                if "article" not in tags:
                    tags.append("article")
        for term in visual_terms_for_beat(vo, title):
            extras, extra_tags = await _fill_broll_urls(term, vo, 0, 3)
            tags.extend(extra_tags)
            urls.extend(extras)
        return unique_image_urls(urls)

    for i, scene in enumerate(scenes):
        vo = getattr(scene, "dialogue_or_vo", "") or ""
        still_id = getattr(scene, "still_id", f"still_{i + 1:02d}")
        for url in await _candidates(i, vo):
            path = await _save(url)
            if path:
                out[still_id] = path
                break

    leftovers = list(unused)
    for i, scene in enumerate(scenes):
        still_id = getattr(scene, "still_id", f"still_{i + 1:02d}")
        if still_id in out:
            continue
        vo = getattr(scene, "dialogue_or_vo", "") or ""
        scored = sorted(
            leftovers,
            key=lambda url: overlap_score(caps.get(url, "") + " " + urlparse(url).path, vo),
            reverse=True,
        )
        while scored:
            url = scored.pop(0)
            blob = caps.get(url, "") + " " + urlparse(url).path
            if overlap_score(blob, vo) < STILL_OVERLAP:
                continue
            leftovers.remove(url)
            path = await _save(url)
            if path:
                out[still_id] = path
                if "article" not in tags:
                    tags.append("article")
                break

    provider = "+".join(dict.fromkeys(tags)) if tags else "none"
    return out, provider


async def collect_brief_photos(
    *,
    source_url: str | None,
    query: str,
    dest_dir: Path,
    count: int,
    article_urls: list[str] | None = None,
    extra_text: str = "",
) -> tuple[list[Path], str]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    urls = list(article_urls or [])
    if source_url and not urls:
        try:
            page = await fetch_article(source_url)
            urls = page.image_urls
            extra_text = extra_text or f"{page.title}\n{page.text}"
            query = query or page.title
        except Exception:
            urls = []
    urls = unique_image_urls(urls)
    photos: list[Path] = []
    tags: list[str] = []
    index = 0
    article_cap = min(2, count) if urls else 0

    async def _save(url: str, referer: str | None) -> Path | None:
        nonlocal index
        dest = dest_dir / f"src_{index:02d}.png"
        path = await download_photo(url, dest, referer=referer)
        if path:
            photos.append(path)
            index += 1
        return path

    for url in urls:
        if len(photos) >= article_cap:
            break
        host = urlparse(url).netloc
        referer = source_url if "vnecdn" in host or "vnexpress" in host else None
        await _save(url, referer)
    if photos:
        tags = ["article"]
    if len(photos) < count:
        extras, extra_tags = await _fill_broll_urls(query, extra_text, len(photos), count)
        tags.extend(extra_tags)
        for url in unique_image_urls(extras):
            if len(photos) >= count:
                break
            await _save(url, None)
    if not photos:
        extra = await search_openverse(query, limit=max(2, count))
        if extra:
            tags = ["openverse"]
            for url in unique_image_urls(extra):
                if len(photos) >= count:
                    break
                await _save(url, None)
    if not photos:
        return [], "none"
    provider = "+".join(dict.fromkeys(tags)) if tags else "article"
    return photos, provider
