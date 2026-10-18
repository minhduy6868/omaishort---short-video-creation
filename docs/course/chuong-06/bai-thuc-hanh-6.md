# Bài thực hành 6 — Sửa có test, không gọi model sống

Từ thư mục repo:

```powershell
apps\api\.venv\Scripts\python.exe -m pytest -q tests/test_brief_media.py tests/test_engine.py
```

Việc sau khi xanh:

1. Mở `test_visual_terms_for_beat_follow_the_vo_not_the_headline`. Chỉ ra assert nào cấm `nguyên` và `khoảng`, assert nào cấm `phong` khi câu đã nói gara cháy.
2. Mở `test_photo_credit_keeps_the_next_sentence_intact`. Giải thích vì sao `Ảnh: Minh Bằng` không được để lại `ằng`.
3. Mở `test_article_caption_match_beats_an_unrelated_wiki_query`. Caption gara phải điểm cao hơn query chân dung.

Không chạy Comfy, ElevenLabs, hay ChatGPT trong các test này.

Job URL thật (tự chọn, cần mạng), không bắt buộc để nộp phần code:

```powershell
cd apps\api
.\.venv\Scripts\python.exe -m omaishort "https://vnexpress.net/<bai>" --kind news --language vi
```

Sau job, `script.json` không chứa `Ằng`, và `render/motion.json` có `"mode": "kenburns"`. Nếu `provider` trong `script.json` vẫn là `wiki`, đó là chưa login ChatGPT (chương 2), không phải hồi quy của chương 6.
