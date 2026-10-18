# Bài thực hành 5 — Chỉ ra tầng

Với mỗi dòng, mở file và ghi một câu "cái này sống ở đây":

| Câu hỏi | File cần mở |
| --- | --- |
| Route `/news` do ai render? | `apps/web/src/main.tsx`, `App.tsx` |
| Ai tạo hàng job? | `apps/api/omaishort/main.py` `POST /jobs`, `db.create_job` |
| Ảnh still ghi vào đâu? | `apps/api/omaishort/paths.py` `stills_dir` |
| MP4 có trong bảng `jobs` không? | `db.py` — cột JSON metadata; file là `render/short.mp4` |
| D1 có nhận byte ảnh không? | `d1.py` — body là `sql` + `params` |

Xong khi sơ đồ trong [5.1](5.1-kien-truc.md) không có mũi tên MP4 tới Worker.
