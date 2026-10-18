# Bài thực hành 2 — Cài môi trường và đọc prompt thật

> Lệnh có trong `apps/api/omaishort/cli.py` và `AGENTS.md`. Windows dùng `apps\api\.venv\Scripts\python.exe`.

## Phần A — Đọc prompt trước khi gọi model

1. Mở `prompts/news_script.txt`. Gạch vai, năm nhịp, khối JSON.
2. Mở `prompts/analyzer_brief.txt`. Đối chiếu bible: đúng một `narrator`, `props` rỗng.
3. Mở `apps/api/omaishort/engine/analyzer.py`, hàm `knowledge_script_user` và `write_knowledge_script`. Chỉ ra chỗ SOURCE bị cắt và chỗ provider thành `wiki`.

Không sửa prompt trong bài này. Chương 2 là đọc hợp đồng chữ, không phải thêm kỹ thuật mới.

## Phần B — Login ChatGPT web (một lần)

Từ `apps\api`:

```powershell
.\.venv\Scripts\python.exe -m omaishort --chatgpt-login
```

Cửa sổ hiện, đăng nhập, profile nằm ở `DATA_DIR/chatgpt-web`. Job kiến thức hoặc tin **sau** lần login đó ghi `script.json` với `provider` khác `wiki` khi web trả JSON hợp lệ. Nếu chưa login, `note` trong `script.json` chứa dòng kiểu `ChatGPT web not logged in`.

## Phần C — Không gọi model, vẫn kiểm parser

```powershell
apps\api\.venv\Scripts\python.exe -m pytest -q tests/test_engine.py tests/test_brief_media.py
```

Test này không mở ChatGPT, không gọi Comfy, không gọi ElevenLabs.
