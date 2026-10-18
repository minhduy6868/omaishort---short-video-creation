# Chương 5 — AI trong thiết kế và kiến trúc (case study: omaishort)

Bám mục 5.1–5.6. Sơ đồ chỉ vẽ chỗ code đang đặt dữ liệu. MP4 không nằm trên Worker.

## Mục lục

| Mục | File | Trong repo |
| --- | --- | --- |
| 5.1 Thiết kế kiến trúc | [5.1-kien-truc.md](5.1-kien-truc.md) | Studio, API, engine, D1, `data/jobs` |
| 5.2 Mô hình kiến trúc | [5.2-architecture-patterns.md](5.2-architecture-patterns.md) | Pipeline stage + chuỗi provider |
| 5.3 UML | [5.3-uml.md](5.3-uml.md) | Sơ đồ từ schema. Không có file UML công cụ |
| 5.4 Cơ sở dữ liệu | [5.4-database.md](5.4-database.md) | Bảng jobs/users/tokens/attachments |
| 5.5 Thiết kế API | [5.5-api.md](5.5-api.md) | Route trong `main.py` |
| 5.6 Mẫu thiết kế | [5.6-design-patterns.md](5.6-design-patterns.md) | Protocol provider, adapter D1, fallback |
| Bài thực hành 5 | [bai-thuc-hanh-5.md](bai-thuc-hanh-5.md) | Chỉ ra file từng tầng |

## Báo cáo thiếu hụt

1. Không có sơ đồ C4/UML check-in (PlantUML, draw.io). Sơ đồ trong chương này là mermaid bám file.
2. Không có microservice. Một process API.
3. Không có hàng đợi Redis/Celery. Job chạy trong process API.
4. Planner không import SDK nhà cung cấp. Đó là luật kiến trúc, không phải một service riêng.
