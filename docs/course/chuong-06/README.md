# Chương 6 — AI lập trình (case study: sửa ảnh tin lệch lời)

Đề cương hỏi cách sinh mã, gợi ý, sửa lỗi, lập trình cặp, và quy trình khi ngồi với AI. Bài này lấy **một thay đổi thật** trong `engine/brief_media.py`, không lấy một demo todo-app.

Việc sản phẩm của tuần này, một lớp engine:

1. Từ khoá ảnh tin là vật trong lời (gara, cháy, xe cứu hoả), không phải chữ chức năng.
2. Ảnh trong bài được cộng điểm khi caption khớp lời, nên đứng trước một query Wikimedia lệch.
3. Credit `Ảnh: Minh Bằng` không còn bị cắt thành `Ằng` dính vào câu sau.

## Mục lục

| Mục | File |
| --- | --- |
| 6.1 Sinh mã | [6.1-code-generation.md](6.1-code-generation.md) |
| 6.2 Hoàn thành mã | [6.2-code-completion.md](6.2-code-completion.md) |
| 6.3 Sửa lỗi | [6.3-debugging.md](6.3-debugging.md) |
| 6.4 Lập trình cặp | [6.4-pair-programming.md](6.4-pair-programming.md) |
| 6.5 Quy trình | [6.5-quy-trinh.md](6.5-quy-trinh.md) |
| Bài thực hành 6 | [bai-thuc-hanh-6.md](bai-thuc-hanh-6.md) |

## Báo cáo thiếu hụt

1. Chưa render lại một URL VnExpress sống trong phiên này. Kiểm chứng là pytest trên HTML mẫu cùng cấu trúc bài gara (credit `Ảnh: Minh Bằng` rồi câu `Ít phút sau`). Job thật còn phụ thuộc mạng và provider ảnh.
2. Script tin khi chưa login ChatGPT vẫn là đường `wiki` (chép câu). Chương 6 không biến fallback thành model.
3. Không có plugin "AI hoàn thành mã" bên trong sản phẩm omaishort. 6.2 nói về cách làm bài, không nói về một API mới.
