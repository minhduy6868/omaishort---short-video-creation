# Chương 7 — Tái cấu trúc và review mã cùng AI (case study: diff ảnh tin)

Đề cương hỏi chất lượng mã, tái cấu trúc, code smell, và review bằng AI. Bài này đọc diff chương 6 trên `brief_media.py`. Không thêm màn hình. Không biến tin thành drama. Những smell còn lại được liệt kê để sửa dần, không bịa một đợt refactor trong cùng bài.

## Mục lục

| Mục | File |
| --- | --- |
| 7.1 Chất lượng mã | [7.1-chat-luong-ma.md](7.1-chat-luong-ma.md) |
| 7.2 Tái cấu trúc | [7.2-tai-cau-truc.md](7.2-tai-cau-truc.md) |
| 7.3 Code smells | [7.3-code-smells.md](7.3-code-smells.md) |
| 7.4 Review | [7.4-code-review.md](7.4-code-review.md) |
| Bài thực hành 7 | [bai-thuc-hanh-7.md](bai-thuc-hanh-7.md) |

## Báo cáo thiếu hụt

1. Không có bot review trên GitHub (CodeQL, review app) trong `.github/workflows`. Review chương này là đọc diff và test.
2. Không tách `brief_media.py` trong bài này. File vẫn ôm fetch, scrub, search, chấm điểm.
3. `external_terms_for_beat` đã chặn cụm tên riêng ngắn khi câu đã có alias vật thể. `_EXPLAINER_PACKS` và trần sáu từ của credit vẫn để sau.
