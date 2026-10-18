# Chương 2 — Kỹ thuật viết câu lệnh (case study: omaishort)

Tài liệu này áp mục 2.1–2.7 của đề cương CS2028 lên **prompt đang chạy** trong repo. Nguyên tắc giống chương 3: chỉ ghi cái có trong `prompts/` và `apps/api/omaishort/providers/llm.py`. Kỹ thuật sách giáo trình nhắc nhưng code không dùng thì nằm ở mục thiếu hụt, không bịa thành tính năng.

## Mục lục

| Mục | File | Trong repo |
| --- | --- | --- |
| 2.1 Cơ bản về Prompt | [2.1-co-ban-prompt.md](2.1-co-ban-prompt.md) | Có: file prompt + user message lắp ở analyzer |
| 2.2 Các kỹ thuật prompting | [2.2-ky-thuat-prompting.md](2.2-ky-thuat-prompting.md) | Role + ràng buộc + JSON. Không có few-shot mẫu đầy đủ |
| 2.3 Các mẫu prompt | [2.3-mau-prompt.md](2.3-mau-prompt.md) | Persona, recipe 5 nhịp, template output |
| 2.4 Quản trị ngữ cảnh | [2.4-context-engineering.md](2.4-context-engineering.md) | SOURCE cắt 8000 ký tự; một hội thoại ChatGPT mỗi ngày |
| 2.5 Đầu ra có cấu trúc | [2.5-structured-output.md](2.5-structured-output.md) | JSON schema trong prompt; `response_format` chỉ khi gọi OpenAI |
| 2.6 Quy trình prompt | [2.6-prompt-workflow.md](2.6-prompt-workflow.md) | ChatGPT web → HTTP LLM → wiki / `fallback_analyze` |
| 2.7 Thực hành tốt | [2.7-best-practices.md](2.7-best-practices.md) | Prompt cấm bịa fact, cấm mô tả xưởng video |
| Bài thực hành 2 | [bai-thuc-hanh-2.md](bai-thuc-hanh-2.md) | Lệnh login và chỗ đọc `script.json` |

## Báo cáo thiếu hụt

1. **Không có thư viện prompt versioning** (không LangSmith, không file eval riêng cho từng prompt). Prompt là file text trong `prompts/`, nạp bằng `load_prompt`.
2. **Không có few-shot** (không nhét bài báo mẫu + JSON mẫu vào prompt). Hình JSON chỉ là khung khoá.
3. **Không có chain-of-thought.** Mọi prompt script/analyzer đều bắt "Return ONLY valid JSON".
4. **Không có prompt để viết PRD.** Prompt sinh lời video, không sinh tài liệu yêu cầu (đã ghi ở chương 3).
