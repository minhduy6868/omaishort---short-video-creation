# Chương 3 — AI trong Phân tích Yêu cầu & Sản phẩm (case study: omaishort)

Tài liệu này áp lý thuyết Chương 3 lên **chính codebase omaishort**. Nguyên tắc biên soạn:

- **Chỉ ghi cái có thật trong code / docs của repo.** Mỗi khẳng định đều trỏ tới file nguồn.
- Cái gì lý thuyết yêu cầu nhưng **repo không có** → không bịa; liệt kê trong mục "Báo cáo thiếu hụt" bên dưới và lặp lại ở đầu mỗi phần liên quan (khối `> ⚠️ Không có trong code`).
- Nguồn sự thật gốc: [`docs/REQUIREMENTS.md`](../../REQUIREMENTS.md) (hợp đồng sản phẩm), [`docs/AUTH.md`](../../AUTH.md) (hợp đồng auth/attachment), [`docs/RESEARCH.md`](../../RESEARCH.md) (hệ sinh thái), `packages/schema/omaishort_schema/models.py` (kiểu dữ liệu), `apps/api/omaishort/*` (API + engine).

## Mục lục

| Mục | File | Trạng thái theo lý thuyết |
| --- | --- | --- |
| 3.0 Dùng AI ở từng bước 3.1→3.5 (phương pháp) | [3.0-ai-trong-tung-buoc.md](3.0-ai-trong-tung-buoc.md) | Quy trình học (AI đề xuất → repo phán quyết), không phải tính năng |
| 3.1 Khám phá Sản phẩm (Product Discovery) | [3.1-kham-pha-san-pham.md](3.1-kham-pha-san-pham.md) | Một phần (có problem + actors; thiếu nghiên cứu thị trường/KPI) |
| 3.2 Tài liệu Yêu cầu Sản phẩm (PRD) | [3.2-prd.md](3.2-prd.md) | Tổng hợp từ REQUIREMENTS/AUTH (repo chưa có file "PRD" riêng) |
| 3.3 Phân tích Yêu cầu | [3.3-phan-tich-yeu-cau.md](3.3-phan-tich-yeu-cau.md) | Đầy đủ (FR/NFR + input contract + data model có trong code) |
| 3.4 User Stories & Tiêu chí Chấp nhận | [3.4-user-stories-acceptance.md](3.4-user-stories-acceptance.md) | Suy ra từ routes + tests (repo chưa có user story dạng chuẩn) |
| 3.5 Đặc tả Tính năng (Feature Specification) | [3.5-dac-ta-tinh-nang.md](3.5-dac-ta-tinh-nang.md) | Auth/Attachment đầy đủ (AUTH.md); các tính năng khác trải trong REQUIREMENTS |
| Bài thực hành 3 + Demo | [bai-thuc-hanh-3.md](bai-thuc-hanh-3.md) | Có lệnh chạy thật (CLI dry-run, pytest, tsc) |

---

## Báo cáo thiếu hụt (những gì lý thuyết cần nhưng CODE KHÔNG CÓ)

Đây là danh sách trung thực để bạn biết ranh giới giữa "đã tài liệu hoá từ code" và "cần bổ sung mới":

1. **Không có file PRD độc lập.** `docs/REQUIREMENTS.md` tự nhận là *"product contract"* (spec kỹ thuật + số liệu), không phải PRD theo bố cục Discovery→PRD→Stories. Phần 3.2 là bản tổng hợp lại, không phải file có sẵn.
2. **Không có nghiên cứu thị trường / phân khúc khách hàng / mô hình kinh doanh.** Repo chỉ có bảng "Users" (REQUIREMENTS §2) và "Actors" (AUTH §2). Không có TAM/SAM/SOM, giá, đối thủ dưới góc độ kinh doanh (RESEARCH.md chỉ so sánh **kỹ thuật**, để "học contract, không fork").
3. **Không có product metrics/KPI** (retention, DAU, thời gian tạo video mục tiêu...). Repo chỉ có **acceptance kỹ thuật** (REQUIREMENTS §13, AUTH §11): pytest, tsc, dry-run ra MP4.
4. **Không có User Stories & Acceptance Criteria dạng chuẩn** (As a… / Given-When-Then) trong repo. Phần 3.4 **suy ra** từ endpoint thật (`apps/api/omaishort/main.py`) và test thật (`tests/test_auth.py`, `tests/test_attachments.py`) — được đánh dấu rõ là "suy ra từ code".
5. **Feature Specification chỉ đầy đủ cho Auth + Attachment** ([`docs/AUTH.md`](../../AUTH.md)). Các tính năng drama / news / knowledge / I2V được đặc tả rải trong REQUIREMENTS §6–§9 và RESEARCH, **chưa** có file feature-spec riêng cho từng cái.
6. **Không có sản phẩm hoá "AI dùng để phân tích yêu cầu".** Prompt trong `prompts/` là để **sinh nội dung video** (analyzer/planner), không phải để sinh PRD/story. Việc "dùng AI viết PRD" là hoạt động của **bài thực hành**, không phải chức năng của sản phẩm.

> Ghi chú phạm vi: omaishort là *"Story → short-video engine"* (REQUIREMENTS §pipeline). Nó **không** phải công cụ quản lý yêu cầu. Vì vậy Chương 3 ở đây là *phân tích yêu cầu CỦA omaishort*, dùng repo làm ví dụ, chứ không phải "omaishort là công cụ PRD".
