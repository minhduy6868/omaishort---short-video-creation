# Chương 1 — AI trong phát triển phần mềm (case study: omaishort)

Áp mục 1.1–1.6 của đề cương CS2028 lên pipeline đang chạy. Sản phẩm là engine local: dán chuyện hoặc URL, ra một MP4 1080×1920. Chi tiết hợp đồng nằm ở `docs/REQUIREMENTS.md`, không viết lại ở đây.

## Mục lục

| Mục | File | Trong repo |
| --- | --- | --- |
| 1.1 AI trong vòng đời | [1.1-ai-trong-vong-doi.md](1.1-ai-trong-vong-doi.md) | AI nằm ở stage analyze → render. Yêu cầu và thiết kế là tài liệu người viết |
| 1.2 AI-assisted và AI-native | [1.2-ai-assisted-vs-native.md](1.2-ai-assisted-vs-native.md) | Native: script, plan, still, TTS. Assisted: người dán bài và login ChatGPT |
| 1.3 LLM | [1.3-llm-fundamentals.md](1.3-llm-fundamentals.md) | HTTP chat, model mặc định `gpt-4o-mini`, temperature 0.4. Không train model |
| 1.4 Ảo giác | [1.4-ao-giac.md](1.4-ao-giac.md) | Job gara cháy: lời nói cháy xe, từ khoá ảnh từng ra chân dung |
| 1.5 Cửa sổ ngữ cảnh | [1.5-cua-so-ngu-canh.md](1.5-cua-so-ngu-canh.md) | SOURCE cắt 8000 ký tự. Không có RAG |
| 1.6 Hệ sinh thái | [1.6-he-sinh-thai.md](1.6-he-sinh-thai.md) | Chuỗi provider trong README. Không scrape UI Gemini/Grok |
| Bài thực hành 1 | [bai-thuc-hanh-1.md](bai-thuc-hanh-1.md) | Đọc `script.json`: `provider` và `note` |

## Báo cáo thiếu hụt

1. Không có bước AI viết yêu cầu hay chấm UI trong sản phẩm. Chương 3 và 4 ghi rõ chỗ đó là bài học, không phải tính năng.
2. Không fine-tune, không đánh giá benchmark model, không có dashboard độ tin cậy.
3. Job gara cháy (`8f5115a49cdb`) không nằm trong git. `data/jobs` bị cấm commit. Ví dụ ảo giác dựa trên triệu chứng đã ghi ở lộ trình và trên test chương 6.
