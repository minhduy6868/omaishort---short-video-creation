"""Viral retention evaluator, built-in hook formulas, caption style presets, and AI viral booster.

Provides real, deterministic short-form retention scoring (0-100 across 5 dimensions)
aligned with TikTok / Reels / YouTube Shorts completion & shareability craft:
  1. Hook Power (0-25): 0-3s scroll-stopper, concrete numbers/contrast, zero cliché intros
  2. Curiosity & Twist Arc (0-20): open loops, midpoint re-hook, earned reversal
  3. Pacing & Spoken Rhythm (0-20): crisp spoken sentences (8-18 words), target-second fit
  4. Value & Payoff (0-20): specific facts/examples/stakes + memorable ending takeaway
  5. Visual Specificity (0-15): camera-filmable nouns/actions for strong stills & I2V
"""

from __future__ import annotations

import re
from typing import Any

from omaishort.engine.analyzer import rewrite_content_beats
from omaishort_schema.models import SubtitleStyle

_BEAT_KEYS = ("hook", "conflict", "rising_action", "twist", "ending")

_WEAK_OPENERS = re.compile(
    r"^(?:xin chào|chào mừng|hôm nay chúng ta|trong video này|bài viết này|thuyết minh về|"
    r"hello everyone|welcome back|in this video|today we (?:are going to|will)|let'?s talk about)\b",
    re.I,
)
_CURIOSITY_MARKERS = re.compile(
    r"(?:\?|nhưng|tuy nhiên|sự thật|ít ai biết|bất ngờ|không ngờ|bí mật|lầm tưởng|sai lầm|ngược lại|"
    r"trái ngược|hóa ra|đến khi|cho đến khi|đột nhiên|lật ngược|nghịch lý|tại sao|vì sao|"
    r"\b(?:but|however|until|suddenly|truth|secret|mistake|wrong|actually|turns out|nobody|never|why|plot twist)\b)",
    re.I,
)
_STAKES_VALUE_MARKERS = re.compile(
    r"(?:\d+[%$₫kKmMbB]?|\b(?:triệu|tỷ|nghìn|giờ|phút|giây|năm|ngày|bước|cách|bài học|kết quả|mất|lãi|lỗ|"
    r"hệ lụy|nguy cơ|bí quyết|ứng dụng|chứng minh|quyết định|million|billion|percent|hours|minutes|years|"
    r"steps|lesson|result|cost|save|rule|proof|secret)\b)",
    re.I,
)
_VISUAL_ANCHORS = re.compile(
    r"\b(?:điện thoại|màn hình|cửa|bàn|ghế|xe|phòng|sảnh|đêm|mưa|ánh đèn|gương|nhẫn|thẻ đen|hồ sơ|"
    r"tiền|nhà|đường|bệnh viện|tòa án|máy chủ|biểu đồ|bản đồ|sông|đền|chợ|bếp|khách sạn|mắt|tay|bước|"
    r"phone|screen|door|counter|table|car|lobby|night|rain|lamp|mirror|ring|card|file|money|house|street|"
    r"court|server|chart|map|river|kitchen|hotel|eyes|hands|shadow|window|camera)\b",
    re.I,
)
_FILLER_CLICHES = re.compile(
    r"(?:đó là nội dung chính|như vậy chúng ta đã thấy|hệ thống được thiết kế để|tổng kết lại là|"
    r"in conclusion|that is the main content|as we can see)",
    re.I,
)


VIRAL_PRESETS: dict[str, list[dict[str, str]]] = {
    "drama": [
        {
            "id": "drama-karma-reveal",
            "name": "Coi thường → Lật thân phận → Quả báo",
            "tag": "Viral Top",
            "summary": "Mở màn sỉ nhục công khai trong 3s đầu, giữ bình tĩnh đẩy căng thẳng, lật thân phận sốc và chốt 1 câu lạnh lùng.",
            "brief": (
                "Cấu trúc drama giữ chân cực cao: 3 giây đầu cắt thẳng vào câu sỉ nhục hoặc hành động coi thường gây sốc "
                "trước đám đông; nhân vật chính im lặng tạo sự tò mò; giữa clip cài chi tiết chuyển ngoặt (cuộc gọi, thẻ đen, người chứng kiến); "
                "cú twist lật thân phận thật rõ ràng; kết bằng 1 câu chốt lạnh lùng khiến người xem muốn chia sẻ."
            ),
        },
        {
            "id": "drama-midnight-secret",
            "name": "Bí mật 2 giờ sáng (Tâm lý & Plot Twist)",
            "tag": "Giữ chân cao",
            "summary": "Mở đầu bằng vật chứng cụ thể lúc nửa đêm (màn hình điện thoại, hóa đơn), đẩy nghi ngờ lên đỉnh rồi lật ngược hoàn toàn.",
            "brief": (
                "Mở đầu bằng một chi tiết vật chứng cận cảnh lúc nửa đêm kèm mốc giờ cụ thể; nhịp câu ngắn, căng thẳng kiểu kể chuyện thì thầm; "
                "nửa sau bẻ lái bằng một sự thật hoàn toàn trái ngược suy đoán ban đầu của người xem; kết mở sắc bén để kích thích bình luận."
            ),
        },
        {
            "id": "drama-dialogue-clash",
            "name": "Đối thoại căng thẳng 1-1",
            "tag": "Đối đáp sắc",
            "summary": "Nhịp thoại ngắn, phản đòn trực diện từng câu, cắt cảnh liên tục giữa hai biểu cảm đối lập.",
            "brief": (
                "Giữ câu thoại ngắn gọn, mỗi câu tối đa 14 từ, đối đáp sắc bén trực diện không giải thích dài dòng; "
                "mỗi lượt thoại phải nâng mức căng thẳng cao hơn lượt trước và chốt bằng câu phản đòn không thể cãi."
            ),
        },
    ],
    "knowledge": [
        {
            "id": "know-curiosity-myth",
            "name": "Phá bỏ lầm tưởng 90% người mắc phải",
            "tag": "Viral Top",
            "summary": "Mở đầu bằng nghịch lý + con số bất ngờ, giải mã cơ chế dễ hiểu bằng ví dụ đời thường, chốt bài học áp dụng ngay.",
            "brief": (
                "Mở đầu 3 giây đầu bằng 1 nghịch lý hoặc con số gây sốc khiến người xem phải dừng lướt, tuyệt đối không chào hỏi dài dòng. "
                "Dùng giọng người dẫn thông minh, ví dụ đời thường dễ hình dung, cài câu chuyển nhịp ở giữa ('Nhưng sự thật ít ai biết là...'), "
                "bóc tách lầm tưởng phổ biến nhất ở phần Twist và chốt 1 quy tắc ứng dụng ngay."
            ),
        },
        {
            "id": "know-story-documentary",
            "name": "Kể chuyện lịch sử / tài liệu cuốn hút",
            "tag": "Tài liệu điện ảnh",
            "summary": "Dẫn chuyện như phim tài liệu ngắn: bối cảnh sống động, mốc thời gian cụ thể, bước ngoặt bất ngờ và di sản đọng lại.",
            "brief": (
                "Viết theo giọng phim tài liệu điện ảnh giàu hình ảnh: mở ngay bằng khoảnh khắc kịch tính nhất của sự kiện/nhân vật, "
                "dẫn mạch theo trình tự thời gian rõ ràng bằng động từ mạnh, cài bước ngoặt ít người để ý ở phần Twist, "
                "và kết nối bài học về hiện tại ở phần Kết để người xem muốn lưu lại."
            ),
        },
        {
            "id": "know-tech-breakdown",
            "name": "Giải mã công cụ / AI trong 60 giây",
            "tag": "Giá trị thực chiến",
            "summary": "Nêu thẳng nỗi đau tốn thời gian, chỉ 3 bước hoạt động thực tế của sản phẩm, điểm khác biệt thật và cách bắt đầu.",
            "brief": (
                "Không liệt kê tech-stack khô khan. Mở đầu bằng vấn đề thực tế ai cũng gặp, mô tả quy trình chạy trong 3 bước ngắn gọn "
                "có thể quay cận cảnh màn hình, chỉ rõ 1 điểm mạnh khác biệt bất ngờ so với cách làm cũ, và chốt lời khuyên bắt đầu ngay."
            ),
        },
    ],
    "news": [
        {
            "id": "news-fast-impact",
            "name": "Tiêu điểm nhanh & Tác động sát sườn",
            "tag": "Tin nóng",
            "summary": "Vào thẳng con số/sự kiện chính trong 2 giây đầu, nêu ngay tác động thực tế tới người xem và kết cục mới nhất.",
            "brief": (
                "Mở ngay bằng sự kiện và con số đắt giá nhất của bài báo trong câu đầu tiên; cắt bỏ lời rào đón bản tin; "
                "nhấn mạnh tác động trực tiếp đến đời sống/túi tiền người xem ở phần 2, làm rõ chi tiết bước ngoặt dễ bị bỏ sót ở phần 4 "
                "và kết bằng diễn biến thực tế mới nhất."
            ),
        },
        {
            "id": "news-investigation",
            "name": "Bóc tách vụ việc theo mốc thời gian",
            "tag": "Giữ chân cao",
            "summary": "Kể lại chuỗi sự kiện rõ ràng từng mốc, chỉ ra nút thắt tiền bạc/pháp lý và bài học cảnh tỉnh ở cuối.",
            "brief": (
                "Tường thuật khách quan, bám sát sự thật bài báo theo trình tự thời gian sắc gọn; mỗi đoạn gắn với một hình ảnh hiện trường cụ thể; "
                "tạo điểm nhấn bất ngờ ở chi tiết bước ngoặt và kết thúc bằng phán quyết/hiện trạng rõ ràng."
            ),
        },
    ],
}


CAPTION_PRESETS: list[dict[str, Any]] = [
    {
        "id": "tiktok-gold",
        "name": "TikTok Vàng Nổi Bật",
        "tag": "Đọc nhanh",
        "description": "Chữ trắng đậm viền đen dày, karaoke vàng sáng bắt mắt — dễ đọc trên mọi nền.",
        "subtitle": SubtitleStyle(
            font="Arial",
            font_size=68,
            primary_hex="#FFFFFF",
            highlight_hex="#FFE000",
            outline_hex="#101010",
            outline=6,
            margin_v=140,
        ).model_dump(mode="json"),
    },
    {
        "id": "editorial-clean",
        "name": "Tài Liệu Sạch Sắc Nét",
        "tag": "Tin & Kiến thức",
        "description": "Cỡ chữ cân đối, điểm nhấn xanh ngọc hiện đại, phù hợp video phân tích và tin tức.",
        "subtitle": SubtitleStyle(
            font="Arial",
            font_size=60,
            primary_hex="#F8FAFC",
            highlight_hex="#38BDF8",
            outline_hex="#0B1120",
            outline=5,
            margin_v=130,
        ).model_dump(mode="json"),
    },
    {
        "id": "drama-amber",
        "name": "Điện Ảnh Cam Ấm",
        "tag": "Drama kịch tính",
        "description": "Tương phản cao với điểm nhấn cam rực giữ cảm xúc điện ảnh cho short drama.",
        "subtitle": SubtitleStyle(
            font="Arial",
            font_size=64,
            primary_hex="#FFF8E7",
            highlight_hex="#FF6B35",
            outline_hex="#120B08",
            outline=6,
            margin_v=135,
        ).model_dump(mode="json"),
    },
    {
        "id": "high-contrast-lime",
        "name": "Viral Neon Xanh Chanh",
        "tag": "Tốc độ cao",
        "description": "Cỡ chữ lớn, karaoke xanh neon nổi bật mạnh trong 3 giây đầu cuộn feed.",
        "subtitle": SubtitleStyle(
            font="Arial",
            font_size=72,
            primary_hex="#FFFFFF",
            highlight_hex="#A3E635",
            outline_hex="#09090B",
            outline=6,
            margin_v=150,
        ).model_dump(mode="json"),
    },
]


def _split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return []
    parts = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", cleaned) if s.strip()]
    return parts or [cleaned]


def _extract_beats(text: str, structure: dict[str, Any] | None) -> dict[str, str]:
    if isinstance(structure, dict):
        out = {k: str(structure.get(k) or "").strip() for k in _BEAT_KEYS}
        if any(out.values()):
            return out
    paras = [p.strip() for p in re.split(r"\n\s*\n", (text or "").strip()) if p.strip()]
    if len(paras) >= 5:
        return {k: paras[i] for i, k in enumerate(_BEAT_KEYS)}
    sents = _split_sentences(text)
    if not sents:
        return {k: "" for k in _BEAT_KEYS}
    chunks = [""] * 5
    for idx, sent in enumerate(sents):
        slot = min(4, int(idx / max(1, len(sents)) * 5))
        chunks[slot] = f"{chunks[slot]} {sent}".strip()
    return {k: chunks[i] for i, k in enumerate(_BEAT_KEYS)}


def evaluate_viral_script(
    text: str,
    *,
    structure: dict[str, Any] | None = None,
    kind: str = "drama",
    language: str = "vi",
    target_seconds: int = 60,
) -> dict[str, Any]:
    """Deterministically score a script's viral retention potential (0-100) + actionable tips."""
    beats = _extract_beats(text, structure)
    full_text = "\n\n".join(v for v in beats.values() if v) or (text or "").strip()
    words = re.findall(r"\S+", full_text)
    word_count = len(words)
    sentences = _split_sentences(full_text)
    wps = 3.1 if str(language).lower().startswith("vi") else 2.7
    est_sec = round(word_count / wps, 1) if word_count else 0.0

    hook_text = beats["hook"] or (sentences[0] if sentences else "")
    hook_first = _split_sentences(hook_text)[0] if hook_text else ""
    hook_words = len(re.findall(r"\S+", hook_first))

    tips: list[str] = []

    # 1. Hook Power (0..25)
    hook_score = 0
    if hook_words >= 4:
        hook_score += 8
        if hook_words <= 18:
            hook_score += 5
        else:
            tips.append("Câu mở đầu hơi dài — rút gọn dưới 16 từ để người xem nắm ý ngay trong 2 giây đầu.")
        if _WEAK_OPENERS.search(hook_first):
            hook_score = max(3, hook_score - 8)
            tips.append("Tránh mở đầu kiểu 'Hôm nay chúng ta...', 'Xin chào...' — vào thẳng nghịch lý, con số hoặc tình huống sốc.")
        else:
            hook_score += 4
        if _CURIOSITY_MARKERS.search(hook_text) or _STAKES_VALUE_MARKERS.search(hook_text):
            hook_score += 5
        else:
            tips.append("Thêm con số cụ thể, câu hỏi hoặc chi tiết tương phản ngay ở Hook để tạo khoảng trống tò mò (Curiosity Gap).")
        if _VISUAL_ANCHORS.search(hook_text):
            hook_score += 3
    else:
        tips.append("Cần câu mở đầu rõ ràng ít nhất 6-14 từ đánh trúng sự tò mò ngay 3 giây đầu.")
    hook_score = min(25, hook_score)

    # 2. Curiosity & Twist Arc (0..20)
    curiosity_hits = len(_CURIOSITY_MARKERS.findall(full_text))
    twist_words = len(re.findall(r"\S+", beats["twist"]))
    curiosity_score = 0
    curiosity_score += min(10, curiosity_hits * 3)
    if twist_words >= 8:
        curiosity_score += 6
        if _CURIOSITY_MARKERS.search(beats["twist"]):
            curiosity_score += 4
    else:
        tips.append("Bổ sung phần Twist (cú lật / sự thật phản trực giác) rõ nét để giữ người xem tới cuối.")
    if curiosity_hits < 2:
        tips.append("Cài thêm 1 câu chuyển nhịp giữa clip ('Nhưng sự thật ít ai biết là…') để kéo giữ chân đoạn giữa (Re-Hook).")
    curiosity_score = min(20, curiosity_score)

    # 3. Pacing & Spoken Rhythm (0..20)
    pacing_score = 0
    if sentences:
        avg_len = word_count / max(1, len(sentences))
        if 8 <= avg_len <= 18:
            pacing_score += 10
        elif 6 <= avg_len <= 24:
            pacing_score += 7
        else:
            pacing_score += 3
            tips.append("Chia nhỏ các câu dài (>22 từ) thành câu ngắn một hơi đọc để phụ đề karaoke nhảy mượt hơn.")
        # Check target duration fit
        target = max(15.0, float(target_seconds or 60))
        ratio = est_sec / target if target else 1.0
        if 0.65 <= ratio <= 1.35:
            pacing_score += 6
        elif 0.4 <= ratio <= 1.65:
            pacing_score += 3
        else:
            tips.append(
                f"Độ dài lời ước tính ~{est_sec:.0f}s so với mục tiêu {int(target)}s — nên cân chỉnh lượng chữ sát thời lượng."
            )
        # Clean spoken style (no URLs/markdown/cliché endings)
        if not re.search(r"https?://|```|^\s*[-*#]", full_text, re.M) and not _FILLER_CLICHES.search(full_text):
            pacing_score += 4
        else:
            tips.append("Loại bỏ câu đệm sách giáo khoa ('đó là nội dung chính'), gạch đầu dòng hoặc đường link trong lời đọc.")
    pacing_score = min(20, pacing_score)

    # 4. Value & Payoff (0..20)
    value_hits = len(_STAKES_VALUE_MARKERS.findall(full_text))
    filled_beats = sum(1 for k in _BEAT_KEYS if len(re.findall(r"\S+", beats[k])) >= 6)
    ending_words = len(re.findall(r"\S+", beats["ending"]))
    value_score = 0
    value_score += min(8, value_hits * 2)
    value_score += min(6, filled_beats + 1)
    if ending_words >= 8:
        value_score += 6
    else:
        tips.append("Làm sắc đoạn Kết bằng 1 bài học đắt giá, câu chốt lạnh hoặc lời kêu gọi suy ngẫm để tăng lượt lưu & chia sẻ.")
    if value_hits < 2 and kind in {"knowledge", "news"}:
        tips.append("Đưa thêm số liệu, mốc thời gian hoặc ví dụ đời thực cụ thể để tăng giá trị thông tin cho người xem.")
    value_score = min(20, value_score)

    # 5. Visual Specificity (0..15)
    visual_hits = len(set(m.lower() for m in _VISUAL_ANCHORS.findall(full_text)))
    visual_score = min(15, visual_hits * 3 + (3 if filled_beats >= 4 else 0))
    if visual_hits < 2:
        tips.append("Thêm vật thể/bối cảnh cụ thể nhìn thấy được (màn hình, cánh cửa, biểu đồ, khuôn mặt, ánh đèn) để AI vẽ still sắc nét hơn.")

    total = max(0, min(100, hook_score + curiosity_score + pacing_score + value_score + visual_score))
    grade = "S" if total >= 86 else "A" if total >= 74 else "B" if total >= 58 else "C"

    # Deduplicate tips while preserving priority order
    dedup_tips: list[str] = []
    for tip in tips:
        if tip not in dedup_tips:
            dedup_tips.append(tip)

    return {
        "score": total,
        "grade": grade,
        "word_count": word_count,
        "estimated_seconds": est_sec,
        "filled_beats": filled_beats,
        "metrics": {
            "hook": {"score": hook_score, "max": 25, "label": "Hook 0–3s"},
            "curiosity": {"score": curiosity_score, "max": 20, "label": "Tò mò & Twist"},
            "pacing": {"score": pacing_score, "max": 20, "label": "Nhịp nói & Thời lượng"},
            "value": {"score": value_score, "max": 20, "label": "Giá trị & Kết đọng"},
            "visual": {"score": visual_score, "max": 15, "label": "Độ giàu hình ảnh"},
        },
        "tips": dedup_tips[:4],
    }


async def boost_viral_script(
    *,
    text: str,
    structure: dict[str, Any] | None = None,
    kind: str = "drama",
    language: str = "vi",
    target_seconds: int = 60,
    instruction: str = "",
    title: str = "",
) -> dict[str, Any]:
    """Evaluate a script, target its weakest viral dimensions, and rewrite for higher retention."""
    before = evaluate_viral_script(
        text,
        structure=structure,
        kind=kind,
        language=language,
        target_seconds=target_seconds,
    )
    beats = _extract_beats(text, structure)
    weak_notes = "; ".join(before["tips"][:3]) if before["tips"] else "Sharpen hook, add midpoint re-hook, and make the ending more quotable."
    directive = (
        f"Tối ưu kịch bản theo chuẩn viral short-video giữ chân cao (Hook 0-3s gây tò mò mạnh -> đẩy cao trào -> "
        f"re-hook giữa clip -> Twist bất ngờ -> Kết đọng lại dễ chia sẻ). "
        f"Khắc phục các điểm yếu: {weak_notes}. "
        f"{instruction.strip()}"
    ).strip()

    updated, provider = await rewrite_content_beats(
        beats,
        kind=kind,
        language=language,
        target_seconds=target_seconds,
        beat="all",
        instruction=directive,
        title=title,
    )
    joined = "\n\n".join(str(updated.get(k) or "").strip() for k in _BEAT_KEYS if str(updated.get(k) or "").strip())
    after = evaluate_viral_script(
        joined,
        structure=updated,
        kind=kind,
        language=language,
        target_seconds=target_seconds,
    )
    return {
        "structure": updated,
        "text": joined,
        "provider": provider,
        "before": before,
        "after": after,
    }
