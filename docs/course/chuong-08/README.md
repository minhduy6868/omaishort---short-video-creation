# Chương 8 — AI trong kiểm thử (case study: pytest, tsc và một test trình duyệt của omaishort)

Đề cương: đơn vị, tích hợp, hệ thống, tự động hoá, thiết kế bài test. Repo không dùng AI để sinh test trong CI. Test là file người viết trong `tests/`. AI có thể đề xuất assert; cổng vẫn là `pytest -q` và `npx tsc --noEmit`.

Số liệu phiên cập nhật (máy local, 06/11/2026, nhánh `feat/ui-themes`):

| Lệnh | Kết quả |
| --- | --- |
| `apps\api\.venv\Scripts\python.exe -m pytest -q` | **144 passed**, 1 warning Starlette/httpx (không phải fail) |
| `npx tsc --noEmit` trong `apps/web` | sạch, exit 0, không in lỗi |
| `pytest -q tests/test_studio_e2e.py` (sau `npm run build`) | **3 passed** trong ~8 s, Chrome headless |

Phiên 18/10 là 135 passed. Chín test thêm từ đó: route desktop, chờ API, theme admin, và ba test trình duyệt.

CI (`.github/workflows/ci.yml`) chạy `pytest -q` và `npx tsc --noEmit`, không cần API key. Trên CI không có `apps/web/dist`, nên `test_studio_e2e.py` tự skip.

## Mục lục

| Mục | File | File test |
| --- | --- | --- |
| 8.1 Đơn vị | [8.1-don-vi.md](8.1-don-vi.md) | `test_schema.py`, `test_brief_media.py`, phần lớn `test_engine.py` |
| 8.2 Tích hợp | [8.2-tich-hop.md](8.2-tich-hop.md) | `test_auth.py`, `test_attachments.py`, `test_desktop.py` |
| 8.3 Hệ thống | [8.3-he-thong.md](8.3-he-thong.md) | `test_render.py` (FFmpeg), `test_studio_e2e.py` (Playwright + Chrome) |
| 8.4 Tự động hoá | [8.4-tu-dong-hoa.md](8.4-tu-dong-hoa.md) | `ci.yml` |
| 8.5 Thiết kế bài test | [8.5-thiet-ke-test.md](8.5-thiet-ke-test.md) | Credit chương 6, route desktop, quyền đổi theme |
| Bài thực hành 8 | [bai-thuc-hanh-8.md](bai-thuc-hanh-8.md) | Hai lệnh CI, test trình duyệt, và một lần "cố tình làm đỏ" |

## Báo cáo thiếu hụt

1. Không có test gọi Comfy, ElevenLabs, ChatGPT, Wikimedia, hay VnExpress. Đúng chủ đích.
2. Không có coverage gate, không có mutation test tự động. Bài thực hành làm mutation bằng tay trên một dòng.
3. Test trình duyệt chỉ chạy trên máy có bản build và Chrome/Edge. CI chưa chạy nó.
4. Phía web chưa có test đơn vị (không có Vitest). Vòng thử lại `/auth/me` khi API tắt chỉ được kiểm tay trong trình duyệt.
5. Không có model sinh test rồi tự merge. Test mới vào repo chỉ khi người commit.
6. Dry-run MP4 mẫu không nằm trên CI. `test_render.py` cần FFmpeg trên máy chạy pytest.
