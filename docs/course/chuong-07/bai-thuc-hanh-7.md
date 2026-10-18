# Bài thực hành 7 — Đọc diff, không thêm màn

```powershell
git show 2df51f9 --stat
git show 2df51f9 -- apps/api/omaishort/engine/brief_media.py
apps\api\.venv\Scripts\python.exe -m pytest -q tests/test_brief_media.py -k "visual_terms or photo_credit or article_caption"
```

Việc:

1. Trong diff, tìm `_BEAT_STOP` và nói một từ đã bị cấm vì nó không phải vật trong ảnh.
2. Tìm test cấm chuỗi `Ằng`.
3. Mở `external_terms_for_beat`. Câu có hai tên ngắn và đã nói gara cháy thì cụm tìm không còn `Phong` / `Minh`. File `brief_media.py` vẫn chưa tách.
4. Xác nhận diff không có file trong `apps/web`.

Xong khi hai test tên trong lộ trình vẫn xanh: `test_visual_terms_for_beat_follow_the_vo_not_the_headline` và các assert cháy gara trong cùng hàm đó.
