# Chương 4 — AI trong thiết kế sản phẩm (case study: omaishort)

Bám mục 4.1–4.4. Không vẽ mockup mới. Luồng và khung dưới đây là route và component đang chạy.

## Mục lục

| Mục | File | Trong repo |
| --- | --- | --- |
| 4.1 Luồng người dùng | [4.1-user-flow.md](4.1-user-flow.md) | `main.tsx`, `App.tsx`, `desktop.py` |
| 4.2 Bố cục khung | [4.2-wireframe.md](4.2-wireframe.md) | Landing sections + shell studio. Không có file Figma |
| 4.3 Bản mẫu | [4.3-prototype.md](4.3-prototype.md) | Studio Vite là prototype chạy được |
| 4.4 AI đánh giá thiết kế | [4.4-ai-design-review.md](4.4-ai-design-review.md) | Không có model chấm UI. Luật nằm ở `.cursor/rules/frontend.mdc` |
| Bài thực hành 4 | [bai-thuc-hanh-4.md](bai-thuc-hanh-4.md) | Đối chiếu route |

## Báo cáo thiếu hụt

1. Không có Figma, không có bộ wireframe tách khỏi CSS.
2. Không có prototype click-through riêng (InVision, v.v.). Bản chạy là app.
3. Không có bước "đưa ảnh màn hình cho model rồi sửa UI theo góp ý" trong pipeline.
4. Ảnh và MP4 không lên D1. Thiết kế cố ý tách metadata và file.
