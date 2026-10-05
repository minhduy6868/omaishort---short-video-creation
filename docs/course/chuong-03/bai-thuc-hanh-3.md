# Bài thực hành 3 + Chạy Demo — omaishort

> Mọi lệnh dưới đây là **có thật** trong repo (nguồn: `docs/REQUIREMENTS.md` §13, `docs/AUTH.md` §11, `apps/api/omaishort/cli.py`, `AGENTS.md`). Không có lệnh nào bịa thêm.
> Trên Windows dùng venv của API: `apps/api/.venv/Scripts/python.exe` (AGENTS.md).

## Phần A — Kiểm chứng yêu cầu bằng test (map 3.3/3.4)

Chạy toàn bộ test đơn vị (kiểm FR/AC):

```powershell
apps\api\.venv\Scripts\python.exe -m pytest -q
```

Chỉ chạy nhóm auth + attachment (map Epic A/C/D ở 3.4):

```powershell
apps\api\.venv\Scripts\python.exe -m pytest -q tests/test_auth.py tests/test_attachments.py
```

Typecheck Studio (NFR frontend):

```powershell
cd apps\web; npx tsc --noEmit
```

**Bài tập A1:** mở `tests/test_auth.py`, đối chiếu từng test với bảng "Truy vết Story → Test" ở [3.4](3.4-user-stories-acceptance.md). Ghi ra test nào phủ AC nào.

## Phần B — Chạy Demo pipeline (map 3.2 success criteria)

Các lệnh acceptance (REQUIREMENTS §13). Chúng chạy **dry-run** không cần đăng nhập HTTP (FR8):

```powershell
# Drama: ra MP4 1080x1920 có tiếng
apps\api\.venv\Scripts\python.exe -m omaishort samples/confession-60s.md

# Knowledge topic (tiếng Việt): script.json viết trước stills, không mặt bible
apps\api\.venv\Scripts\python.exe -m omaishort samples/knowledge-topic.md --kind knowledge --language vi

# News/knowledge từ file brief mẫu, narrator-only
apps\api\.venv\Scripts\python.exe -m omaishort samples/brief-60s.md --kind knowledge --language vi
```

Hai demo còn lại cần **mạng** (README §Commands). Chạy từ `apps\api` để đường dẫn tương đối giống README:

```powershell
cd apps\api

# News — bài báo thật. Thay <...> bằng URL một bài cụ thể.
# cli.py đặc biệt hoá các host: vnexpress, tuoitre, thanhnien, dantri, vietnamnet
# (language=en + các host này => tự ép sang vi).
.\.venv\Scripts\python.exe -m omaishort "https://vnexpress.net/<đường-dẫn-bài-viết>" --kind news --language vi

# Knowledge — URL GitHub thật (URL này có sẵn trong README của repo)
.\.venv\Scripts\python.exe -m omaishort "https://github.com/mattpocock/skills" --kind knowledge --language vi
```

> ⚠️ Repo **không** lưu sẵn một URL bài báo cụ thể nào (README cũng chỉ ghi `https://vnexpress.net/...`). Hãy tự chọn một bài đang sống; nếu fetch lỗi, job **không** chết mà ghi lý do vào `script.json.note` (xem edge case ở [3.5.7.8](3.5-dac-ta-tinh-nang.md)).

**Bài tập B3 (news):** sau khi chạy news URL, mở `data/jobs/<id>/storyboard.json`. Kiểm 3 điều — đúng **5 scene**, mọi `characters` đều rỗng, và VO của beat cuối phủ **phần kết** bài chứ không dừng ở xung đột (map AC2/AC1 của US-B8).

Cờ CLI hữu ích (nguồn `cli.py`): `--kind`, `--mode`, `--genre`, `--shape {infer,default,custom}`, `--language`, `--seconds`, `--source-url`, `--logo`, `--no-bgm`, `--voice`, `--script-brief`.

Muốn chạy nhanh, bỏ hàng đợi I2V (README §Commands):

```powershell
$env:HF_I2V_ENABLED = "0"
$env:POLLINATIONS_VIDEO_ENABLED = "0"
$env:WAVESPEED_ENABLED = "0"
```

**Bài tập B1:** chạy drama với `--shape default` rồi `--shape custom` trên cùng một paste; so sánh `bible.json`/`structure.json` trong `data/jobs/<id>/` để thấy khác biệt về "tell-shape" (map §3.1 JTBD + REQUIREMENTS §1).

**Bài tập B2:** mở `data/jobs/<id>/render/motion.json` sau một job. Xác nhận giá trị là `kenburns` | `i2v` | `mixed` (kiểm FR10 "motion honesty").

## Phần C — Demo hợp đồng đầu vào (map 3.3.3)

`StoryInput` validate cả CLI lẫn HTTP. Thử phá luật để thấy schema chặn:

- Đặt `target_seconds` ngoài 15–180 → Pydantic báo lỗi (models.py `Field(ge=15, le=180)`).
- Gửi 2 attachment trùng `id` → `duplicate attachment id` (model_validator).
- Kind `news` với genre drama → tự ép về `news` (không lỗi, nhưng giá trị bị coerce).

**Bài tập C1:** viết một `StoryInput(...)` trong Python REPL với `apps/api/.venv`, thử các case trên, ghi lại thông báo lỗi thật.

## Phần D — Demo "AI phân tích yêu cầu" (hoạt động học, KHÔNG phải chức năng sản phẩm)

> ⚠️ omaishort không có tính năng sinh PRD. Đây là bài tập dùng công cụ AI (ngoài sản phẩm) để tạo tài liệu Chương 3, rồi **đối chiếu ngược với code**.

**Bài tập D1:** dùng một trợ lý AI, prompt: *"Đọc `docs/REQUIREMENTS.md` và `apps/api/omaishort/main.py`, sinh User Stories + Acceptance Criteria."* Sau đó so sánh với [3.4](3.4-user-stories-acceptance.md): AI có bịa endpoint không có thật không? (kiểm "ảo giác" — Chương 1.4).

**Bài tập D2:** yêu cầu AI xuất **structured output** JSON gồm `{feature, actor, acceptance_criteria[]}` cho tính năng auth; đối chiếu với `docs/AUTH.md` §7 (FR-A1..A6). Đây là cầu nối sang Chương 2.5 (Structured Outputs).

## Phần E — Demo Studio (HTTP end-to-end, map Epic A/B/C/D ở 3.4)

Phần B chạy CLI nên **bỏ qua toàn bộ auth**. Muốn thấy các story về tài khoản / quyền sở hữu / attachment thì phải chạy Studio. Cần **hai terminal** (nguồn: README §Setup, `apps/api/run.py`, `apps/web/vite.config.ts`).

Terminal 1 — API (`127.0.0.1:8765`, từ `config.py`):

```powershell
cd apps\api
.\.venv\Scripts\python.exe run.py
```

Terminal 2 — Studio (`127.0.0.1:5173`, proxy `/auth` `/jobs` `/attachments` `/files` sang API):

```powershell
cd apps\web
npm install
npm run dev
```

Mở `http://127.0.0.1:5173`.

### Kịch bản demo theo story

| Bước trên Studio | Quan sát | Story |
| --- | --- | --- |
| 1. Chưa đăng nhập: form tạo job bị khoá | Gọi thẳng `POST /jobs` (curl) → **401** | US-B1 AC1 |
| 2. Đăng ký tài khoản **đầu tiên** | `GET /auth/me` trả `role=operator` | US-A1 AC1 |
| 3. Đăng ký tài khoản **thứ hai** | `role=creator` | US-A1 AC2 |
| 4. Upload attachment (`face` hoặc `editorial`) | Hiện trong danh sách; thử upload `.svg` → **400** | US-C1 |
| 5. Tạo job, chọn attachment vừa upload | Studio poll stage `analyze → … → render` | US-B1, US-C2 |
| 6. Xem still hiện ra trong trang | Ảnh đi qua `/files/...` bằng **cookie**, không cần token | US-D1, AUTH §9 |
| 7. Tải MP4 | `GET /jobs/{id}/download` | US-B3 AC2 |
| 8. Đăng nhập bằng tài khoản kia, mở id job của người đầu | **404** (không phải 403) | US-B2 AC1 |

**Bài tập E1:** thực hiện bước 8 và giải thích **vì sao trả 404 chứ không 403** (gợi ý: AUTH §4.5 — "Guessing another job id returns 404 so ids stay unlisted").

**Bài tập E2:** đăng nhập xong, thử mở thẳng `http://127.0.0.1:5173/files/omaishort.db`. Kết quả phải là **404** dù đã đăng nhập (US-D1 AC2). Giải thích khác biệt giữa 401 (chưa đăng nhập) và 404 (đã đăng nhập nhưng file bị cấm).

**Bài tập E3:** mở chip provider trên Studio (hoặc `GET /providers`) và đối chiếu với bảng chuỗi provider ở [3.5.6](3.5-dac-ta-tinh-nang.md). Adapter nào đang sống trên máy bạn?

> ⚠️ **Không có trong code:** repo không có script seed tài khoản mẫu hay dữ liệu demo cho Studio; phải tự đăng ký. Cũng không có test end-to-end tự động cho luồng Studio (chỉ có test API bằng `TestClient`).

---

## Bảng chấm (gợi ý)

| Tiêu chí | Đạt khi |
| --- | --- |
| Chạy được test | `pytest -q` xanh; giải thích ≥5 test map AC nào |
| Chạy được demo | Có `render/short.mp4` 1080×1920; đọc được `motion.json` |
| Chạy được Studio | Đăng ký + tạo job qua HTTP; tái hiện 404 khi xem job người khác (E1) |
| Hiểu input contract | Tái hiện ≥2 lỗi validate của `StoryInput` |
| Phân biệt sản phẩm vs bài tập | Nêu đúng: omaishort tạo video, không tạo PRD |

> ⚠️ **Không có trong code:** repo không có script chấm điểm tự động cho bài thực hành; bảng chấm trên là đề xuất, chưa phải tài sản trong repo.
