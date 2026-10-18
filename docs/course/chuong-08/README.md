# Chương 8 — AI trong kiểm thử (case study: pytest và tsc của omaishort)

Đề cương: đơn vị, tích hợp, hệ thống, tự động hoá, thiết kế bài test. Repo không dùng AI để sinh test trong CI. Test là file người viết trong `tests/`. AI có thể đề xuất assert; cổng vẫn là `pytest -q` và `npx tsc --noEmit`.

Số liệu phiên viết bài này (máy local, 18/10/2026):

| Lệnh | Kết quả |
| --- | --- |
| `apps\api\.venv\Scripts\python.exe -m pytest -q` | **135 passed**, 1 warning Starlette/httpx (không phải fail) |
| `npx tsc --noEmit` trong `apps/web` | sạch, exit 0, không in lỗi |

CI (`.github/workflows/ci.yml`) chạy đúng hai lệnh đó, không cần API key.

## Mục lục

| Mục | File | File test |
| --- | --- | --- |
| 8.1 Đơn vị | [8.1-don-vi.md](8.1-don-vi.md) | `test_schema.py`, `test_brief_media.py`, phần lớn `test_engine.py` |
| 8.2 Tích hợp | [8.2-tich-hop.md](8.2-tich-hop.md) | `test_auth.py`, `test_attachments.py`, `test_desktop.py` |
| 8.3 Hệ thống | [8.3-he-thong.md](8.3-he-thong.md) | `test_render.py` (FFmpeg local). Không có test trình duyệt |
| 8.4 Tự động hoá | [8.4-tu-dong-hoa.md](8.4-tu-dong-hoa.md) | `ci.yml` |
| 8.5 Thiết kế bài test | [8.5-thiet-ke-test.md](8.5-thiet-ke-test.md) | Cách một assert chương 6 được chọn |
| Bài thực hành 8 | [bai-thuc-hanh-8.md](bai-thuc-hanh-8.md) | Hai lệnh |

## Báo cáo thiếu hụt

1. Không có test gọi Comfy, ElevenLabs, ChatGPT, Wikimedia, hay VnExpress. Đúng chủ đích.
2. Không có coverage gate, không có mutation test, không có Playwright trên studio.
3. Không có model sinh test rồi tự merge. Test mới vào repo chỉ khi người commit.
4. Dry-run MP4 mẫu không nằm trên CI (runner không có FFmpeg bắt buộc). `test_render.py` cần FFmpeg trên máy chạy pytest.
