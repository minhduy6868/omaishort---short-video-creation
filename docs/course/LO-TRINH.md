# Lộ trình đồ án CS2028 — omaishort

Đồ án là sản phẩm thật: dán chuyện hoặc URL, ra MP4 1080×1920 trên máy. Cloudflare D1 chỉ giữ tài khoản và metadata job. Ảnh, thoại, MP4 nằm trong `data/jobs` và không đưa lên server.

Mỗi tuần bám một chương trong đề cương. Làm xong tuần đó rồi mới sang tuần sau. Không viết chương giả cho phần code chưa có.

## Đã có

| Tuần | Chương đề cương | Trong repo |
| --- | --- | --- |
| 1 | AI trong vòng đời, native/assisted, LLM, ảo giác, ngữ cảnh, hệ sinh thái | `docs/course/chuong-01/` |
| 2 | Prompt: kỹ thuật, mẫu, ngữ cảnh, JSON, workflow, thực hành | `docs/course/chuong-02/` |
| 3 | Phân tích yêu cầu, PRD, user story, đặc tả, và file phương pháp 3.0 | `docs/course/chuong-03/` |
| 4 | User flow, khung UI đang chạy, prototype, chỗ không có AI design review | `docs/course/chuong-04/` |
| 5 | Tầng, pattern, UML từ schema, bảng, API, mẫu thiết kế | `docs/course/chuong-05/` |
| 6 | Sửa từ khoá ảnh tin + credit `Ằng`, kèm bài về quy trình lập trình với AI | `brief_media.py`, `tests/test_brief_media.py`, `docs/course/chuong-06/` |
| 7 | Review diff ảnh tin, smell chưa tách file | `docs/course/chuong-07/` |
| 8 | pytest, tsc, CI, cách thiết kế một test | `docs/course/chuong-08/` |
| 9 | Bản đồ tài liệu nộp, không viết lại hợp đồng | `docs/course/chuong-09/` |
| 10 | Việc mang theo buổi bảo vệ | `docs/course/bao-ve.md` |
| — | Pipeline drama / tin / kiến thức, auth, studio, test | `apps/api`, `apps/web`, `tests/` |

## Chưa xong, và đó là phần làm đồ án thật

- Script tin vẫn là bản chép bài khi chưa đăng nhập ChatGPT (`provider` = `wiki`). Login: `python -m omaishort --chatgpt-login`.
- Chưa render lại một URL VnExpress mới trong phiên chương 6. Pytest đã khoá credit `Ảnh: Minh Bằng` và từ khoá gara/cháy. Job sống vẫn cần mạng.
- Bài chương 1–9 và tờ bảo vệ đã có trong `docs/course/`. Smell chương 7.3 và job URL sống vẫn để sửa dần.
- P3 (duyệt từng ảnh), P6 (phim nhiều phần, sửa một câu) nằm ngoài hợp đồng. Không nhét vào đồ án trừ khi giảng viên yêu cầu.

## Mười tuần

### Tuần 1 — Chương 1. AI trong vòng đời phần mềm

Đã nộp `docs/course/chuong-01/` (mục 1.1–1.6). Native ở script, plan, still, TTS. Assisted ở người dán bài và login ChatGPT. Ảo giác gara cháy ghi qua `script.json` (`provider`, `note`) và test chương 6. Job `8f5115a49cdb` không có trong git.

### Tuần 2 — Chương 2. Prompt

Đã nộp `docs/course/chuong-02/` (mục 2.1–2.7, không gộp một file). Login một lần vẫn là việc máy thật: `python -m omaishort --chatgpt-login`. Chưa login thì `script.json` giữ `provider` = `wiki`.

### Tuần 3 — Chương 3. Yêu cầu

Đã nộp trong `docs/course/chuong-03/`, gồm `3.0-ai-trong-tung-buoc.md`. Không viết lại PRD.

### Tuần 4 — Chương 4. Thiết kế sản phẩm

Đã nộp `docs/course/chuong-04/`. Luồng thật: `/en` landing, CTA `/work`, chưa session thì `App.tsx` đẩy `/login`, rồi `/news` → `/watch/{id}`. Desktop mở `/`. Không có mockup mới.

### Tuần 5 — Chương 5. Kiến trúc và dữ liệu

Đã nộp `docs/course/chuong-05/`. Metadata có thể ở D1 (`d1.py`); still, `audio/voiceover.mp3`, `render/short.mp4` ở `data/jobs/<id>/`. Sơ đồ không vẽ MP4 trên Worker.

### Tuần 6 — Chương 6. Sửa cho sản phẩm thật

Đã sửa trong `brief_media.py` và ghi bài `docs/course/chuong-06/`.

1. Từ khóa ảnh tin là vật thể trong lời (gara, cháy, xe cứu hỏa). `_VISUAL_ALIASES`, `_BEAT_STOP`. Tên riêng ngắn như `Phong` không thành query khi đã có alias.
2. Ảnh bài được cộng điểm khi caption khớp lời (`editorial_candidate_score`).
3. `Ảnh: Minh Bằng` không còn bị cắt thành `Ằng`.

Xong phần code khi: pytest khoá ba ý trên. Job URL sống chưa chạy trong phiên viết bài. Tin không có clip I2V thì `render/motion.json` là `kenburns`.

### Tuần 7 — Chương 7. Đọc lại diff tuần 6

Đã nộp `docs/course/chuong-07/`. Không thêm màn hình, không biến tin thành drama. `external_terms_for_beat` đã chặn cụm tên riêng. Còn để sau: tách `brief_media.py`, và credit dài hơn sáu từ.

### Tuần 8 — Chương 8. Test

Đã nộp `docs/course/chuong-08/`. `pytest -q`: 135 passed. `npx tsc --noEmit` trong `apps/web`: sạch. CI `.github/workflows/ci.yml` chạy hai lệnh đó. Test không gọi Comfy, ElevenLabs, hay ChatGPT sống.

### Tuần 9 — Chương 9. Tài liệu nộp

Đã nộp `docs/course/chuong-09/`. Không viết lại hợp đồng. Chạy: `README.md`. Hợp đồng: `docs/REQUIREMENTS.md`, `docs/AUTH.md`. Thiếu thật: mục “Báo cáo thiếu hụt” trong `docs/course/chuong-03/README.md`. MP4 chỉ trên máy; D1 chỉ metadata.

### Tuần 10 — Bảo vệ

Tờ mang theo: `docs/course/bao-ve.md`. Ba job drama / tin / kiến thức vẫn phải render trên máy. Trong git không có MP4 đó.
