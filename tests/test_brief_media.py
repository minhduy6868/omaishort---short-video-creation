import asyncio
from pathlib import Path

from PIL import Image

from omaishort.engine.brief_media import (
    brief_search_queries,
    collect_brief_photos,
    extract_article_text,
    extract_image_urls,
    looks_like_url,
    unique_image_urls,
    visual_terms_for_beat,
    wikipedia_titles,
    knowledge_spoken_from_readme,
)


def test_extract_article_images_skips_logos():
    html = """
    <html><head>
    <title>Nguyễn Đức Anh nói dối đi đòi nợ - Báo VnExpress</title>
    <meta name="twitter:image" content="https://i2-vnexpress.vnecdn.net/2026/09/05/suspect.jpg?w=1200&amp;h=675">
    </head><body>
    <img src="https://scdn.vnecdn.net/vnexpress/restruct/i/v48/logos/72x72.png">
    <img data-src="https://vcdn1-vnexpress.vnecdn.net/2026/09/04/arrest.jpg">
    <p>Công an Đồng Nai đã khởi tố, bắt tạm giam nghi phạm 21 tuổi về tội giết người.</p>
    </body></html>
    """
    page = "https://vnexpress.net/story.html"
    urls = extract_image_urls(html, page)
    assert urls[0].startswith("https://i2-vnexpress.vnecdn.net/2026/09/05/suspect.jpg")
    assert "w=1200" in urls[0]
    assert urls[1] == "https://vcdn1-vnexpress.vnecdn.net/2026/09/04/arrest.jpg"
    text = extract_article_text(html)
    assert "khởi tố" in text
    assert "72x72" not in text


def test_extract_article_skips_scripts_and_related_meta():
    html = """
    <html><head>
    <title>Cô gái Nga và mối tình với anh thợ điện Vĩnh Long - Báo VnExpress</title>
    <meta name="description" content="Đà Nẵng- Vượt qua rào cản ngôn ngữ và khác biệt văn hóa">
    <script>localStorage.setItem("ttf","woff"); function loadCSS(){}</script>
    </head><body>
    <article class="fck_detail">
    <p>Nguyên Anh, chàng thợ điện quê Vĩnh Long Đà Nẵng- Vượt qua rào cản ngôn ngữ và khác biệt văn hóa, và cô gái Nga Nastya đã nên duyên vợ chồng sau 8 tháng quen biết.</p>
    <p>if(('serviceWorker'in navigator)&&isBot===false){window.addEventListener('load',function(){});}</p>
    </article>
    </body></html>
    """
    text = extract_article_text(html)
    assert "Nastya" in text
    assert "Nguyên Anh" in text
    assert "localStorage" not in text
    assert "serviceWorker" not in text
    assert "Đà Nẵng" not in text


def test_scrub_brief_vo_cuts_javascript():
    from omaishort.engine.brief_media import scrub_brief_vo

    vo = (
        "Nguyên Anh quê Vĩnh Long lấy Nastya. "
        'localStorage.setItem(formatStorageKey,format)}return format}();var fonts=document.querySelectorAll(".webfont");'
    )
    cleaned = scrub_brief_vo(vo, "vi")
    assert "Vĩnh Long" in cleaned
    assert "localStorage" not in cleaned
    assert looks_like_url("https://vnexpress.net/a.html")
    assert not looks_like_url("samples/brief-60s.md")


def test_extract_srcset_urls():
    html = """
    <img srcset="https://vcdn1-giadinh.vnecdn.net/2026/09/04/couple.jpg?w=1020&amp;s=abc 1x,
                 https://vcdn1-giadinh.vnecdn.net/2026/09/04/couple.jpg?w=2040&amp;s=def 2x">
    """
    urls = extract_image_urls(html, "https://vnexpress.net/story.html")
    assert urls
    assert "s=def" in urls[0] or "s=abc" in urls[0]


def test_brief_search_queries_vinh_long():
    title = "Cô gái Nga và mối tình với anh thợ điện Vĩnh Long"
    queries = brief_search_queries(title)
    joined = " ".join(queries).lower()
    assert "vinh long" in joined
    assert "electrician" in joined
    assert "da nang" not in joined
    assert wikipedia_titles(title) == ["Vĩnh Long"]
    related = brief_search_queries(title, "Đà Nẵng- Vượt qua rào cản ngôn ngữ và khác biệt.")
    assert "da nang" not in " ".join(related).lower()


def test_unique_image_urls_keeps_longer_query():
    urls = unique_image_urls(
        [
            "https://cdn.example/a.jpg?w=100",
            "https://cdn.example/a.jpg?w=1200&h=675",
            "https://cdn.example/b.jpg",
        ]
    )
    assert len(urls) == 2
    assert "w=1200" in urls[0]


def test_collect_fills_thin_article_gallery(tmp_path, monkeypatch):
    async def fake_wiki(query: str, limit: int = 4) -> list[str]:
        slug = query.split()[0].lower()
        return [f"https://upload.wikimedia.org/wikipedia/commons/{slug}.jpg"]

    async def fake_openverse(query: str, limit: int = 6) -> list[str]:
        return []

    async def fake_wikipedia(title: str) -> list[str]:
        return [f"https://upload.wikimedia.org/wikipedia/{title}.jpg"]

    async def fake_download(url: str, dest: Path, referer: str | None = None) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), (30, 40, 50)).save(dest, "PNG")
        return dest

    monkeypatch.setattr("omaishort.engine.brief_media.search_wikimedia", fake_wiki)
    monkeypatch.setattr("omaishort.engine.brief_media.search_openverse", fake_openverse)
    monkeypatch.setattr("omaishort.engine.brief_media.search_wikipedia_original", fake_wikipedia)
    monkeypatch.setattr("omaishort.engine.brief_media.download_photo", fake_download)

    photos, provider = asyncio.run(
        collect_brief_photos(
            source_url=None,
            query="Cô gái Nga và mối tình với anh thợ điện Vĩnh Long",
            dest_dir=tmp_path,
            count=5,
            article_urls=[
                "https://vcdn1-giadinh.vnecdn.net/a.jpg?w=1200",
                "https://vcdn1-giadinh.vnecdn.net/b.jpg?w=1020",
            ],
            extra_text="Vĩnh Long",
        )
    )
    assert len(photos) == 5
    assert "article" in provider
    assert "wikipedia" in provider or "wikimedia" in provider


def test_assign_retries_cc_when_article_download_fails(tmp_path, monkeypatch):
    class _Scene:
        def __init__(self, still_id: str, vo: str) -> None:
            self.still_id = still_id
            self.dialogue_or_vo = vo

    async def fake_wiki(query: str, limit: int = 4) -> list[str]:
        return ["https://upload.wikimedia.org/wikipedia/commons/cyprus.jpg"]

    async def fake_openverse(query: str, limit: int = 6) -> list[str]:
        return []

    async def fake_wikipedia(title: str) -> list[str]:
        return []

    async def fake_download(url: str, dest: Path, referer: str | None = None) -> Path | None:
        if "bad" in url:
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 64), (20, 80, 90)).save(dest, "PNG")
        return dest

    monkeypatch.setattr("omaishort.engine.brief_media.search_wikimedia", fake_wiki)
    monkeypatch.setattr("omaishort.engine.brief_media.search_openverse", fake_openverse)
    monkeypatch.setattr("omaishort.engine.brief_media.search_wikipedia_original", fake_wikipedia)
    monkeypatch.setattr("omaishort.engine.brief_media.download_photo", fake_download)

    from omaishort.engine.brief_media import assign_editorial_stills

    out, provider = asyncio.run(
        assign_editorial_stills(
            scenes=[
                _Scene("still_01", "Quen trên ứng dụng hẹn hò."),
                _Scene("still_02", "Bà đến Bắc Síp, nơi Bright đang sống bằng thị thực sinh viên."),
            ],
            source_url=None,
            article_urls=["https://cdn.example/good.jpg", "https://cdn.example/bad.jpg"],
            dest_dir=tmp_path,
            title="Trái đắng lấy chồng kém 37 tuổi",
        )
    )
    assert set(out) == {"still_01", "still_02"}
    assert out["still_01"].exists()
    assert out["still_02"].exists()
    assert "wikimedia" in provider


def test_visual_terms_for_beat_follow_the_vo_not_the_headline():
    terms = visual_terms_for_beat(
        "Chồng bỏ đi Nigeria. Họ ly hôn. Cô mất tài sản.",
        "Trái đắng của người phụ nữ lấy chồng kém 37 tuổi",
    )
    joined = " ".join(terms).lower()
    assert "divorce" in joined
    assert "nigeria" in joined
    assert "trái đắng" not in joined
    hung = visual_terms_for_beat("Lạc Long Quân và Âu Cơ nở trăm trứng. Các vua Hùng dựng nước.", "Sử Việt")
    hung_join = " ".join(hung).lower()
    assert "hùng" in hung_join or "hung" in hung_join or "lac long" in hung_join
    crm = visual_terms_for_beat(
        "DeskcommCRM đưa lead vào inbox WhatsApp. Máy chủ self-hosted thay SaaS.",
        "DeskcommCRM",
    )
    crm_join = " ".join(crm).lower()
    assert "inbox" in crm_join or "whatsapp" in crm_join or "server" in crm_join
    assert "dating" not in crm_join
    app = " ".join(visual_terms_for_beat("Cài ứng dụng CRM trên máy chủ.", "CRM")).lower()
    assert "dating" not in app
    from omaishort.engine.brief_media import beat_search_nouns

    nouns = [n.lower() for n in beat_search_nouns("Một lead bị bỏ quên. Khách mất lịch sử.")]
    assert "khách" not in nouns


def test_extract_keeps_article_ending():
    middle = "".join(f"<p>Đoạn giữa số {i} kể chuyện dài hơn mười chữ.</p>" for i in range(30))
    html = (
        "<html><head><title>Trái đắng lấy chồng kém 37 tuổi - Báo VnExpress</title></head>"
        f'<body><article class="fck_detail">{middle}'
        "<p>Chồng bỏ đi Nigeria và họ ly hôn sau khi mất nhà.</p>"
        "</article></body></html>"
    )
    text = extract_article_text(html)
    assert "ly hôn" in text
    assert "Nigeria" in text


def test_github_readme_becomes_spoken_prose():
    from omaishort.engine.brief_media import github_repo_slug, looks_like_github, markdown_to_spoken

    assert looks_like_github("https://github.com/harry0703/MoneyPrinterTurbo")
    assert github_repo_slug("https://github.com/harry0703/MoneyPrinterTurbo.git") == (
        "harry0703",
        "MoneyPrinterTurbo",
    )
    spoken = markdown_to_spoken(
        "# MoneyPrinterTurbo\n\n![ci](https://img.shields.io/badge.svg)\n\n"
        "Generate a short from a topic.\n\n```\npip install -r requirements.txt\n```\n"
        "```python\ndef unused():\n    return 1\n    return 2\n    return 3\n    return 4\n```\n"
    )
    assert "MoneyPrinterTurbo" in spoken
    assert "Generate a short" in spoken
    assert "pip install" in spoken
    assert "def unused" not in spoken
    assert "```" not in spoken
    tutorial = knowledge_spoken_from_readme(
        "# MoneyPrinterTurbo\n\nAn all-in-one AI short video generator.\n\n"
        "## Special Thanks\nKimi sponsor blurb.\n\n"
        "## Features\nProvide a topic and it writes a script, matches footage, and muxes a short.\n\n"
        "## License\nMIT.\n",
        name="MoneyPrinterTurbo",
        description="利用 AI 大模型 Generate HD short videos from a topic.",
    )
    assert "all-in-one" in tutorial.lower() or "HD short" in tutorial or "script" in tutorial.lower()
    assert "Kimi" not in tutorial
    assert "MIT" not in tutorial
    assert "Stop stitching" not in tutorial
    assert "character bible" not in tutorial.lower()
    assert "利用" not in tutorial
    assert tutorial.count("\n\n") == 4


def test_github_readme_notes_keep_agent_skills_not_video_factory():
    from omaishort.engine.brief_media import github_readme_notes, knowledge_spoken_from_readme

    md = """
# Skills For Real Engineers

My agent skills that I use every day to do real engineering - not vibe coding.

## Installation (30-second setup)

### Claude Code
```bash
claude plugins install mattpocock-skills
```

### Codex, and other agents
```bash
npx skills@latest add mattpocock/skills
```

## Why These Skills Exist

The most common failure mode is misalignment. Use `/grill-me` and `/grill-with-docs`
before the agent writes code. Build a shared language in CONTEXT.md and ADRs.
Use `/tdd` for a red-green-refactor loop and `/diagnosing-bugs` for hard bugs.
`/improve-codebase-architecture` surveys a codebase for deepening opportunities.

## License
MIT.
"""
    notes = github_readme_notes(md, name="skills", description="Skills for Real Engineers")
    assert "vibe coding" in notes.lower()
    assert "grill-me" in notes.lower()
    assert "CONTEXT.md" in notes or "shared language" in notes.lower()
    assert "npx skills@latest" in notes or "claude plugins install" in notes
    assert "MIT" not in notes
    tutorial = knowledge_spoken_from_readme(md, name="skills")
    blob = tutorial.lower()
    assert "grill" in blob or "agent" in blob
    assert "stock clips" not in blob
    assert "muxes a vertical short" not in blob
    assert "character bible" not in blob
    assert tutorial.count("\n\n") == 4


def test_github_project_notes_merge_topics_docs_homepage():
    from omaishort.engine.brief_media import github_project_notes

    notes = github_project_notes(
        "# DeskcommCRM\n\nSelf-hosted AI sales OS.\n\n## Features\nWhatsApp via WAHA and native AI agents.\n",
        name="DeskcommCRM",
        description="Open-source AI sales OS",
        topics=["crm", "whatsapp", "ai-agents"],
        extras=["## Architecture\nMulti-tenant inbox with MCP tools for sales agents.\n"],
        homepage_text=(
            "Deskcomm is a self-hosted CRM alternative to Kommo and Intercom. "
            "Teams run WhatsApp agents on their own server without renting a SaaS inbox. "
            "LGPD-ready multi-tenant workspaces."
        ),
    )
    blob = notes.lower()
    assert "topics:" in blob
    assert "whatsapp" in blob
    assert "kommo" in blob or "intercom" in blob
    assert "mcp" in blob or "multi-tenant" in blob


def test_conform_photo_letterboxes_wide_stills(tmp_path):
    from omaishort.engine.brief_media import conform_photo
    from omaishort.providers.placeholder import HEIGHT, WIDTH

    src = tmp_path / "wide.png"
    Image.new("RGB", (1920, 800), (220, 40, 40)).save(src)
    dest = tmp_path / "still.png"
    conform_photo(src, dest)
    out = Image.open(dest)
    assert out.size == (WIDTH, HEIGHT)
    assert out.getpixel((8, 8))[0] < 40
    assert out.getpixel((WIDTH // 2, HEIGHT // 2))[0] > 180


def test_knowledge_topic_query_strips_request_shell():
    from omaishort.engine.brief_media import is_knowledge_topic, knowledge_spoken_from_wiki, topic_query

    prompt = "thuyết minh về lạm phát và cách nó vận hành"
    assert is_knowledge_topic(prompt)
    assert topic_query(prompt) == "lạm phát"
    long_ask = (
        "Hãy tạo một video thuyết minh về Phan Bội Châu, tập trung vào cuộc đời "
        "và những đóng góp quan trọng của ông đối với lịch sử Việt Nam."
    )
    assert is_knowledge_topic(long_ask)
    assert "phan bội châu" in topic_query(long_ask).lower()
    assert is_knowledge_topic("kể về sự tích vua Hùng")
    assert not is_knowledge_topic((Path(__file__).resolve().parents[1] / "samples" / "brief-60s.md").read_text(encoding="utf-8"))
    extract = (
        "Lạm phát là sự tăng mức giá chung một cách liên tục. "
        "Tiền trong túi mua được ít hàng hơn khi giá tăng kéo dài. "
        "Nó có thể đến từ cầu vượt cung hoặc chi phí sản xuất tăng. "
        "Lượng tiền tăng nhanh hơn hàng hóa cũng đẩy giá. "
        "Ngân hàng trung ương dùng lãi suất để hãm cầu. "
        "Chỉ số giá tiêu dùng đo mặt bằng giá theo thời gian. "
        "Một mặt hàng đắt lên chưa đủ để gọi là lạm phát. "
        "Cần nhìn cả rổ hàng hóa chứ không một cú sốc xăng. "
        "Sức mua thực mới là thứ người lao động cảm nhận. "
        "Nhớ đo theo hệ thống, không theo cảm giác một quầy."
    )
    spoken = knowledge_spoken_from_wiki("Lạm phát", extract, "vi")
    assert "thuyết minh về" not in spoken.lower()
    assert spoken.count("\n\n") == 4
    assert "tiếng anh" not in spoken.lower()
    assert "Bắt đầu từ điều dễ hiểu sai" not in spoken
    assert "Cùng một tờ tiền" in spoken
    assert "rổ hàng" in spoken or "xăng" in spoken
    assert "Lạm phát là sự tăng" in spoken
    terms = visual_terms_for_beat(spoken, "Lạm phát")
    joined = " ".join(terms).lower()
    assert any(bit in joined for bit in ("grocery", "wallet", "gas", "price index", "marketplace", "inflation", "money"))


def test_knowledge_spoken_hung_kings_is_a_legend_not_a_statue_slogan():
    from omaishort.engine.brief_media import knowledge_spoken_from_wiki, related_wiki_titles

    spoken = knowledge_spoken_from_wiki(
        "Hùng Vương",
        "Hùng Vương là các vua nước Văn Lang. Truyền thuyết Âu Cơ và Lạc Long Quân đẻ trăm trứng.",
        "vi",
    )
    low = spoken.lower()
    assert "bức tượng" not in low
    assert "bài vị" not in low
    assert "đừng nhớ mỗi ngày giỗ" not in low
    assert "trăm trứng" in low or "âu cơ" in low
    assert "mười tám" in low or "văn lang" in low
    assert {t.lower() for t in related_wiki_titles("sự tích vua Hùng")} >= {
        "hùng vương",
        "lạc long quân",
        "âu cơ",
    }


def test_knowledge_spoken_biography_fills_five_beats():
    from omaishort.engine.brief_media import knowledge_spoken_from_wiki, visual_terms_for_beat

    extract = (
        "Trần Hưng Đạo sinh năm 1228, là danh tướng nhà Trần. "
        "Ông chỉ huy quân dân chống quân Nguyên Mông xâm lược Đại Việt. "
        "Thế nước lúc đó đứng trước mất còn khi kỵ binh phương Bắc kéo xuống. "
        "Ông không thắng bằng hô hào mà bằng trận địa và thủy quân. "
        "Trận Bạch Đằng dùng cọc gỗ đóng ngầm dưới lòng sông. "
        "Khi thủy triều rút, thuyền giặc mắc cạn và bị đánh úp. "
        "Đó là kế dựa vào nước, không phải phép màu. "
        "Người ta hay nhớ tượng đài hơn là cách ông thắng. "
        "Đền Kiếp Bạc còn thờ ông như di sản. "
        "Ông mất năm 1300 nhưng bài học thủy triều vẫn được kể. "
        "Anh hùng dân tộc được tôn vì nước còn, không vì bài vị. "
        "Nhớ ông là nhớ trận, nhớ cọc, nhớ thủy triều."
    )
    spoken = knowledge_spoken_from_wiki("Trần Hưng Đạo", extract, "vi")
    paras = spoken.split("\n\n")
    assert len(paras) == 5
    assert "cơ chế" not in spoken.lower()
    assert "sinh năm" in spoken.lower() or "sinh khoảng" in spoken.lower()
    assert "bạch đằng" in spoken.lower() or "cọc" in spoken.lower()
    assert "thủy triều" in spoken.lower() or "đền" in spoken.lower()
    assert sum(len(p.split()) for p in paras) >= 70
    assert all(len(p.split()) >= 10 for p in paras)
    joined = " ".join(visual_terms_for_beat(spoken, "Trần Hưng Đạo")).lower()
    assert any(bit in joined for bit in ("statue", "temple", "bach dang", "stakes", "mongol"))


def test_knowledge_spoken_skips_han_encyclopedia_lead():
    from omaishort.engine.brief_media import knowledge_spoken_from_wiki

    extract = (
        "Trần Hưng Đạo (chữ Hán: 陳興道, tên thật là Trần Quốc Tuấn (陳國峻), 1228? – 5 tháng 10 năm 1300) "
        "tước hiệu là Hưng Đạo đại vương, là một nhà chính trị, nhà quân sự thời nhà Trần. "
        "Sau khi qua đời dân gian suy tôn ông thành Đức Thánh Trần. "
        "Ông chỉ huy đánh tan ba cuộc xâm lược của quân Nguyên Mông. "
        "Trận Bạch Đằng dùng cọc gỗ đóng ngầm. Khi thủy triều rút thuyền giặc mắc cạn. "
        "Mẹ nuôi Trần Quốc Tuấn là Thụy Bà công chúa biết chuyện, sợ ông bị hại trong phủ. "
        "Ông là con của tôn thất An Sinh Vương Trần Liễu. "
        "Đền Kiếp Bạc còn thờ ông như di sản."
    )
    spoken = knowledge_spoken_from_wiki("Trần Hưng Đạo", extract, "vi")
    assert "cơ chế" not in spoken.lower()
    assert "陳" not in spoken
    assert "thụy bà" not in spoken.lower()
    assert "bạch đằng" in spoken.lower() or "nguyên mông" in spoken.lower()


def test_write_knowledge_script_prefers_llm():
    from unittest.mock import AsyncMock, patch

    from omaishort.engine.analyzer import write_knowledge_script

    fake = {
        "hook": "Người ta gọi ông Trần Hưng Đạo vì trận ông đánh, không vì tượng đá.",
        "conflict": "Ba lần quân Nguyên Mông kéo vào Đại Việt thì cả nước suýt mất.",
        "rising_action": "Ông thắng bằng thủy quân và trận địa chứ không bằng hô hào suông.",
        "twist": "Bạch Đằng là cọc gỗ và thủy triều, không phải phép màu trên sông.",
        "ending": "Nhớ ông vì nước còn. Đền Kiếp Bạc còn đó cho người sau.",
    }
    with patch("omaishort.engine.analyzer.complete_json_result", new=AsyncMock(return_value=(fake, "llm", ""))):
        text, src, note = asyncio.run(
            write_knowledge_script(
                "Trần Hưng Đạo",
                "extract chữ Hán 陳興道",
                "vi",
                90,
                topic="thuyết minh về Trần Hưng Đạo",
            )
        )
    assert src == "llm"
    assert note == ""
    assert "cơ chế" not in text
    assert "Bạch Đằng" in text
    assert text.count("\n\n") == 4


def test_knowledge_script_user_includes_brief():
    from omaishort.engine.analyzer import knowledge_script_user

    user = knowledge_script_user(
        "Lý Thường Kiệt",
        "SOURCE notes about Khâm Ung Liêm",
        "vi",
        90,
        topic="thuyết minh về Lý Thường Kiệt",
        script_brief="  giọng tài liệu, nhấn trận, đừng kể gia phả  ",
    )
    assert "USER_BRIEF=giọng tài liệu, nhấn trận, đừng kể gia phả" in user
    assert "language=vi" in user
    assert "SOURCE notes about Khâm Ung Liêm" in user
    bare = knowledge_script_user("Lý Thường Kiệt", "notes", "vi", 90)
    assert "USER_BRIEF" not in bare


def test_write_knowledge_script_falls_back_to_wiki():
    from unittest.mock import AsyncMock, patch

    from omaishort.engine.analyzer import write_knowledge_script

    extract = (
        "Trần Hưng Đạo sinh năm 1228, là danh tướng nhà Trần. "
        "Ông chỉ huy quân dân chống quân Nguyên Mông xâm lược Đại Việt. "
        "Trận Bạch Đằng dùng cọc gỗ đóng ngầm dưới lòng sông. "
        "Khi thủy triều rút, thuyền giặc mắc cạn. "
        "Đền Kiếp Bạc còn thờ ông như di sản."
    )
    with patch("omaishort.engine.analyzer.complete_json_result", new=AsyncMock(return_value=(None, "", "no OPENAI_API_KEY"))):
        text, src, note = asyncio.run(write_knowledge_script("Trần Hưng Đạo", extract, "vi", 90))
    assert src == "wiki"
    assert "OPENAI_API_KEY" in note
    assert "cơ chế" not in text.lower()
    assert "bạch đằng" in text.lower() or "cọc" in text.lower()


def test_parse_llm_json_strips_fences():
    from omaishort.providers.llm import parse_llm_json

    raw = '```json\n{"hook": "hello world this is long enough"}\n```'
    assert parse_llm_json(raw)["hook"].startswith("hello")
    with_url = '{"hook": "hello world this is long enough"}\n\nCONVERSATION_URL: https://chatgpt.com/c/abc\n'
    assert parse_llm_json(with_url)["hook"].startswith("hello")


def test_chatgpt_web_profile_is_under_data_dir(tmp_path, monkeypatch):
    from omaishort.providers import chatgpt_web

    monkeypatch.setattr(chatgpt_web, "DATA_DIR", tmp_path)
    assert chatgpt_web.profile_dir() == tmp_path / "chatgpt-web" / "profile"
    assert not chatgpt_web.is_authed()
    cookies = tmp_path / "chatgpt-web" / "profile" / "Default" / "Cookies"
    cookies.parent.mkdir(parents=True)
    cookies.write_bytes(b"x" * 200)
    assert chatgpt_web.is_authed()


def test_chatgpt_launch_can_use_system_chrome(tmp_path, monkeypatch):
    from omaishort.providers import chatgpt_web

    monkeypatch.setattr(chatgpt_web, "DATA_DIR", tmp_path)
    exe = tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"mz")
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.setenv("PROGRAMFILES(X86)", str(tmp_path / "x86"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "roaming"))
    assert chatgpt_web.system_chrome_exe() == exe
    opts = chatgpt_web._launch_args(headed=True)
    assert opts["channel"] == "chrome"
    assert opts["headless"] is False


def test_llm_status_reports_chatgpt_web_slot():
    from omaishort.providers.llm import llm_status

    status = llm_status()
    assert "chatgpt_web" in status
    assert "chatgpt_web_authed" in status
    assert "http" in status
    assert "chatgpt_web_profile" in status
    assert "chatgpt_web_chat" in status


def test_chatgpt_web_reuses_one_chat_url_per_day(tmp_path, monkeypatch):
    from omaishort.providers import chatgpt_web

    monkeypatch.setattr(chatgpt_web, "DATA_DIR", tmp_path)
    monkeypatch.setattr(chatgpt_web, "today_key", lambda: "2026-09-06")
    url = "https://chatgpt.com/c/abc-123?foo=1"
    assert chatgpt_web.conversation_url(url) == "https://chatgpt.com/c/abc-123"
    chatgpt_web.save_daily_chat(url)
    daily = chatgpt_web.load_daily_chat()
    assert daily["url"] == "https://chatgpt.com/c/abc-123"
    assert "temporary-chat" not in chatgpt_web.chat_open_url("gpt-4o", daily)
    assert chatgpt_web.chat_open_url("gpt-4o", daily) == "https://chatgpt.com/c/abc-123"
    monkeypatch.setattr(chatgpt_web, "today_key", lambda: "2026-09-07")
    assert chatgpt_web.load_daily_chat() == {}
    fresh = chatgpt_web.chat_open_url("gpt-4o", {})
    assert "temporary-chat" not in fresh
    assert fresh.startswith("https://chatgpt.com/")


def test_gemini_image_parses_inline_bytes():
    from omaishort.providers.gemini_image import _inline_image

    raw = b"hello-image-bytes-xxxxxxxx"
    import base64

    body = {
        "candidates": [
            {
                "content": {
                    "parts": [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(raw).decode()}}]
                }
            }
        ]
    }
    assert _inline_image(body) == raw
    assert _inline_image({}) == b""
