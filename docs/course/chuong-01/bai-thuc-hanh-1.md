# Bài thực hành 1 — Chỉ ra chỗ AI nói và chỗ AI nói sai

Không cần gọi model nếu máy chưa login. Việc là đọc file thật.

1. Mở `README.md` mục Pipeline và Providers. Viết một câu: stage nào sinh chữ, stage nào chỉ ghép file.
2. Mở `apps/api/omaishort/pipeline.py`, chỗ `_dump(..., "script.json", ...)`. Ba field bắt buộc phải chỉ được: `text`, `provider`, `note`.
3. Nếu trên máy còn `data/jobs/<id>/script.json` của một tin:
   - `provider` là `chatgpt-web` hay `wiki`?
   - `note` có nhắc login không?
   - Câu VO của một nhịp có cùng vật với tên file still không?
4. Nếu không còn job đó, dùng test làm chứng cứ thay thế: `tests/test_brief_media.py`, hàm `test_visual_terms_for_beat_follow_the_vo_not_the_headline` và `test_photo_credit_keeps_the_next_sentence_intact`.

Xong khi nói được: omaishort native ở script/plan/still/TTS; người vẫn phải dán bài và login; ảo giác gara cháy là lời đúng chủ đề nhưng từ khoá ảnh sai.
