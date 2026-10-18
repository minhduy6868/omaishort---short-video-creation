# Bảo vệ — tuần 10

Đề cương xếp buổi này là thi kết thúc, không có mục 10.1. Tờ này là việc mang theo. Không có ba MP4 trong git.

## Mang gì

Ba thư mục job local, mỗi thứ một kind:

| Kind | `render/motion.json` → `mode` | `script.json` → `provider` |
| --- | --- | --- |
| drama | `i2v` hoặc `mixed` nếu có key video; `kenburns` nếu không có key | analyze không ghi `script.json` theo đường tin. Lời nằm trong storyboard |
| news | `kenburns` | `chatgpt-web`, `llm`, hoặc `wiki` |
| knowledge | `kenburns` | cùng ba giá trị. README kỳ vọng `chatgpt-web` sau khi đã login |

Mở still `still_01.png` … `still_05.png` cạnh câu VO cùng nhịp. Nếu ảnh tin vẫn là chân dung trong khi lời nói gara cháy, nói đó là lỗi ảnh chưa xong, không gọi là demo cố ý.

## Câu trả không cần slide mới

- Sản phẩm: một short 1080×1920 từ một lần dán. Hợp đồng: `docs/REQUIREMENTS.md`.
- Tài khoản và file: `docs/AUTH.md`. D1 giữ hàng. Byte ở `data/jobs`.
- Prompt và fallback: `docs/course/chuong-02/`.
- Test: `pytest -q` (135 passed ở phiên viết chương 8) và `npx tsc --noEmit`. CI: `.github/workflows/ci.yml`.
- Chỗ còn yếu: chưa login thì lời tin là wiki; smell ở `docs/course/chuong-07/7.3-code-smells.md`.

## Không mang

- File `.env`.
- Job người khác.
- Bản kể P3 (duyệt từng ảnh) hoặc P6 (sửa một câu, render lại) như thể đã có trong sản phẩm.
